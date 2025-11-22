# app/application/pipeline.py
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd
import numpy as np
from os.path import relpath  # usado en _rel_to_base fallback

from app.infrastructure.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
)
from app.infrastructure.process_repo_fs import read_status, write_status
from app.infrastructure.history_repo_fs import append_history
from app.infrastructure.datasources import read_dataframe
from app.infrastructure.profiling import generate_profile_html
from app.application.dates import normalize_dates_in_df, parse_dates_series
from app.application.cleaning import clean_dataframe
from app.application.dashboard import generate_dashboard_html
from app.application.report_full import build_full_report
from app.application.outliers import apply_isolation_forest
from app.application.rules import load_rules_for_process, describe_rules
from app.application.pdf import build_pdf_from_template

from app.services.profile_artifacts import (
    build_profile_csv_from_html,
    build_profile_pdf_from_html,
)

from app.core.config import (
    RUNS_DIR,
    BASE_DIR,
    TEMPLATES_DIR,
    OUTLIER_CONTAMINATION,
    OUTLIER_RANDOM_STATE,
)

# ============================================================
#         Fallbacks para motores de autospec / validación
# ============================================================

# Fuerza usar el fallback integrado (robusto) salvo que lo desactives.
USE_AUTOSPEC_FALLBACK = True

# Si más adelante quieres que la validación bloquee y caiga al dashboard seguro,
# exporta STRICT_DASH_CHECK=1 en el ambiente.
STRICT_DASH_CHECK = os.getenv("STRICT_DASH_CHECK", "0") == "1"

try:
    if not USE_AUTOSPEC_FALLBACK:
        # Si existe un motor externo y NO forzamos el fallback, se usará ese.
        from app.application.autospec import auto_dashboard_spec  # type: ignore
    else:
        raise ImportError()
except Exception:
    # ---------- AUTOSPEC ROBUSTO INTEGRADO ----------
    def auto_dashboard_spec(
        df: pd.DataFrame,
        roles: Dict[str, str],
        source_name: Optional[str] = None,
        process_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Genera un SPEC 'inteligente' y genérico a partir de los datos/roles:
        - Detecta fecha principal, métrica principal (dinero, precio*cantidad, numérica).
        - Selecciona dimensiones con cardinalidad útil (2..50) y prioriza nombres semánticos.
        - KPIs: filas + suma/promedio si hay métrica.
        - 4 gráficos por defecto:
            1) Serie mensual (sum/cont).
            2) % de nulos por columna.
            3) Top-N por dimensión priorizada.
            4) Heatmap Mes×Dimensión (o pie/hist si no aplica).
        - Filtros: rango de fechas + primeras dimensiones + 'moneda' si existe.
        """
        import re

        roles = roles or {}
        cols = list(df.columns)

        # ---------- Helpers ----------
        def _nonnull_ratio(c: str) -> float:
            return float(df[c].notna().mean()) if c in df.columns else 0.0

        def _is_numeric(c: str) -> bool:
            try:
                return pd.api.types.is_numeric_dtype(df[c])
            except Exception:
                return False

        def _num_from_any(s: pd.Series) -> pd.Series:
            return (
                s.astype(str)
                .str.replace(r"[^\d\-,\.]", "", regex=True)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            ).pipe(pd.to_numeric, errors="coerce")

        def _find_by_name(patterns: List[str]) -> List[str]:
            if not patterns:
                return []
            pat = re.compile("|".join(patterns), re.I)
            return [c for c in cols if pat.search(c)]

        # ---------- Fechas ----------
        date_cols = [c for c, r in roles.items() if r == "fecha"]
        if not date_cols:
            date_cols = _find_by_name([r"\bfecha\b", r"\bdate\b", r"\bfcha\b"])
        primary_date = max(date_cols, key=_nonnull_ratio) if date_cols else None

        # ---------- Métricas ----------
        money_cols = [c for c, r in roles.items() if r == "moneda"]
        money_cols = list(
            dict.fromkeys(
                money_cols
                + _find_by_name(
                    [r"\b(monto|importe|total|valor|precio|amount|revenue|sales)\b"]
                )
            )
        )

        numeric_cols = [c for c, r in roles.items() if r == "numérico"]
        numeric_cols += [c for c in cols if _is_numeric(c)]
        numeric_cols = list(dict.fromkeys(numeric_cols))

        # Heurística precio * cantidad
        qty_col = next(
            (
                c
                for c in _find_by_name(
                    [r"\b(cantidad|qty|quantity|unidades|units)\b"]
                )
                if c in df.columns
            ),
            None,
        )
        price_col = next(
            (
                c
                for c in _find_by_name(
                    [r"\b(precio|price|valor_unit|unit[_ ]?price)\b"]
                )
                if c in df.columns
            ),
            None,
        )

        derived_metric = None
        primary_metric = None
        if money_cols:
            primary_metric = money_cols[0]
        elif price_col and qty_col:
            derived_metric = "_importe_calc"
            try:
                price = _num_from_any(df[price_col])
                qty = pd.to_numeric(df[qty_col], errors="coerce")
                # ok mutar df_clean: solo añade una columna
                df[derived_metric] = price * qty
                primary_metric = derived_metric
            except Exception:
                pass
        elif qty_col:
            primary_metric = qty_col
        elif numeric_cols:
            primary_metric = numeric_cols[0]

        # ---------- Dimensiones ----------
        dim_roles = {"texto", "categórica", "bool"}
        dims: List[str] = []
        for c in cols:
            r = roles.get(c, "")
            nun = int(df[c].nunique(dropna=True)) if c in df.columns else 0
            if ((r in dim_roles) or (not _is_numeric(c))) and (2 <= nun <= 50):
                dims.append(c)

        priority = [
            "categoria",
            "category",
            "producto",
            "product",
            "cliente",
            "customer",
            "usuario",
            "user",
            "ciudad",
            "city",
            "region",
            "pais",
            "country",
            "metodo_pago",
            "medio_pago",
            "payment",
            "pago",
            "estado",
            "estatus",
            "status",
            "prioridad",
            "gerente",
            "canal",
            "tipo",
            "vendedor",
            "seller",
        ]

        def _score_dim(c: str) -> tuple:
            name = c.lower()
            prio = 0 if any(p in name for p in priority) else 1
            nun = df[c].nunique(dropna=True)
            return (prio, -min(nun, 50))

        dims = sorted(set(dims), key=_score_dim)[:6]

        # Fallback mínimo: al menos 1 dimensión textual
        if not dims:
            text_like = [c for c in cols if not _is_numeric(c)]
            if text_like:
                dims = [text_like[0]]

        # ---------- KPIs ----------
        kpis: List[Dict[str, Any]] = [{"title": "Filas", "op": "count_rows"}]
        if primary_metric:
            kpis.append(
                {"title": f"Suma de {primary_metric}", "op": "sum", "col": primary_metric}
            )
            kpis.append(
                {
                    "title": f"Promedio de {primary_metric}",
                    "op": "mean",
                    "col": primary_metric,
                }
            )

        # ---------- Gráficos ----------
        charts: List[Dict[str, Any]] = []

        # 1) Serie temporal por mes (sum o conteo)
        if primary_date:
            ts_title = f"{(primary_metric or 'Registros').capitalize()} por mes"
            charts.append(
                {
                    "id": "ts_month",
                    "type": "line",
                    "title": ts_title,
                    "x_title": "Mes",
                    "y_title": primary_metric or "Conteo",
                    "encoding": {
                        "x": {"field": primary_date, "timeUnit": "month"},
                        "y": (
                            {"field": primary_metric, "aggregate": "sum"}
                            if primary_metric
                            else {"field": primary_date, "aggregate": "count"}
                        ),
                    },
                }
            )

        # 2) Nulos por columna (siempre útil)
        charts.append(
            {
                "id": "nulls_by_col",
                "type": "bar",
                "title": "Porcentaje de nulos por columna",
                "x_title": "__column__",
                "y_title": "% nulos",
                "x_tickangle": -30,
                "limit": min(20, len(cols)),
                "encoding": {
                    "x": {"field": "__column__"},
                    "y": {"field": "__null_pct__", "aggregate": "mean"},
                },
            }
        )

        # 3) Top-N por dimensión priorizada
        if dims:
            d0 = dims[0]
            charts.append(
                {
                    "id": "top_dim",
                    "type": "bar",
                    "title": f"Top {d0} por {(primary_metric or 'conteo')}",
                    "x_title": d0,
                    "y_title": primary_metric or "Conteo",
                    "limit": 12,
                    "encoding": {
                        "x": {"field": d0},
                        "y": (
                            {"field": primary_metric, "aggregate": "sum"}
                            if primary_metric
                            else {"field": "__row__", "aggregate": "count"}
                        ),
                    },
                }
            )

        # 4) Heatmap Mes × segunda dimensión (o pie/hist)
        if primary_date and len(dims) >= 2:
            d1 = dims[1]
            charts.append(
                {
                    "id": "heatmap_month_dim",
                    "type": "heatmap",
                    "title": f"Mes × {d1}",
                    "x_title": "Mes",
                    "y_title": d1,
                    "encoding": {
                        "x": {"field": primary_date, "timeUnit": "month"},
                        "y": {"field": d1},
                        "value": (
                            {"field": primary_metric, "aggregate": "sum"}
                            if primary_metric
                            else {"field": "__row__", "aggregate": "count"}
                        ),
                    },
                }
            )
        elif dims:
            d0 = dims[0]
            charts.append(
                {
                    "id": "pie_dim",
                    "type": "pie",
                    "title": f"Participación por {d0}",
                    "limit": 9,
                    "encoding": {
                        "category": {"field": d0},
                        "value": (
                            {"field": primary_metric, "aggregate": "sum"}
                            if primary_metric
                            else {"field": "__row__", "aggregate": "count"}
                        ),
                    },
                }
            )
        else:
            hcol = primary_metric or (numeric_cols[0] if numeric_cols else None)
            if hcol:
                charts.append(
                    {
                        "id": "hist_metric",
                        "type": "histogram",
                        "title": f"Distribución de {hcol}",
                        "x_title": hcol,
                        "y_title": "Frecuencia",
                        "encoding": {"x": {"field": hcol}},
                    }
                )

        # ---------- Filtros ----------
        filters: List[Dict[str, Any]] = []
        if primary_date:
            filters.append({"field": primary_date, "type": "date_range"})
        for d in dims[:3]:
            filters.append({"field": d, "type": "categorical", "max_values": 50})
        if any(c for c in cols if c.lower() == "moneda"):
            filters.append(
                {"field": "moneda", "type": "categorical", "max_values": 50}
            )

        # ---------- Esquema ----------
        schema = {
            "roles": roles,
            "primary_date": primary_date,
            "primary_metric": primary_metric,
            "dims": dims,
        }

        title = f"Dashboard seguro · {source_name or 'Dataset'}"
        chart_ids = [c["id"] for c in charts][:4]

        return {
            "title": title,
            "kpis": kpis[:3],
            "filters": filters,
            "schema": schema,
            "charts": charts,
            "dashboards": [{"title": title, "charts": chart_ids}],
        }


# Validación opcional del dashboard + spec seguro, si existen
try:
    from app.application.spec_guard import validate_dashboard  # type: ignore
except Exception:
    validate_dashboard = None  # type: ignore

try:
    from app.application.recommender import build_generic_spec  # type: ignore
except Exception:

    def build_generic_spec(
        df: pd.DataFrame, roles: Dict[str, str], title: str = "Dashboard"
    ) -> Dict[str, Any]:
        """Fallback de layout seguro (conteos + nulos)."""
        first = df.columns[0]
        charts = [
            {
                "id": "safe_count",
                "type": "bar",
                "title": f"Conteo por {first}",
                "encoding": {"x": {"field": first}, "y": {"aggregate": "count"}},
                "limit": 12,
            },
            {
                "id": "safe_nulls",
                "type": "bar",
                "title": "Porcentaje de nulos por columna",
                "encoding": {
                    "x": {"field": "__column__"},
                    "y": {"field": "__null_pct__"},
                },
            },
        ]
        return {
            "title": title,
            "kpis": [{"title": "Filas", "op": "count_rows"}],
            "filters": [],
            "schema": {
                "roles": roles,
                "primary_date": None,
                "primary_metric": None,
                "dims": [],
            },
            "charts": charts,
            "dashboards": [{"title": title, "charts": [c["id"] for c in charts]}],
        }


# ============================================================

# Etapas mostradas en el front
STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _write(proc_id: str, status: Dict[str, Any]) -> None:
    """Normaliza y guarda status.json (progress 0..100 + updated_at)."""
    status["updated_at"] = now_iso()
    try:
        p = int(status.get("progress", 0))
    except Exception:
        p = 0
    status["progress"] = max(0, min(100, p))
    write_status(proc_id, status)


def _rel_to_base(p: Path) -> str:
    """
    Devuelve p como ruta **relativa** a BASE_DIR, robusta en Windows/Linux/Mac.
    Siempre normaliza a slashes ('/'), ideal para el front.
    """
    base_abs = Path(BASE_DIR).resolve()
    p_abs = Path(p).resolve()
    try:
        rel = p_abs.relative_to(base_abs)
        return rel.as_posix()
    except Exception:
        return relpath(str(p_abs), start=str(base_abs)).replace("\\", "/")


# ---------- Inferencia básica de tipos (RFN20) ----------
def infer_column_type(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    if s.empty:
        return "texto"
    # bool
    if s.str.lower().isin({"0", "1", "true", "false", "sí", "si", "no"}).all():
        return "bool"
    # moneda (símbolos o prefijo ISO)
    if s.str.contains(r"[$€£]|^\s*[A-Z]{2,3}\s*\d", regex=True).mean() > 0.5:
        return "moneda"
    # fecha
    dt = parse_dates_series(s)
    if dt.notna().mean() > 0.8:
        return "fecha"
    # numérico
    sn = (
        s.str.replace(r"[.\s]", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    num = pd.to_numeric(sn, errors="coerce")
    if num.notna().mean() > 0.8:
        return "numérico"
    return "texto"


def infer_types(df: pd.DataFrame) -> Dict[str, str]:
    return {c: infer_column_type(df[c]) for c in df.columns}


# --------------------------------------------------------


def create_initial_process(file) -> Dict[str, Any]:
    """
    Crea proceso, valida/guarda archivo y deja status en 'queued'.
    Estructura runs/{id}/ con artifacts/ e input/.
    """
    validate_filename_and_size(file)

    # runs/{id}
    proc_dir = create_process_dir()
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    # Guardar input en runs/{id}/input/
    uploaded_path = save_upload(file, proc_dir)

    # Estado inicial
    status: Dict[str, Any] = {
        "id": proc_dir.name,
        "filename": uploaded_path.name,
        "status": "queued",
        "progress": 0,
        "current_step": "Subir archivo",
        "steps": [
            {"name": "Subir archivo", "status": "ok"},
            {"name": "Perfilado", "status": "pending"},
            {"name": "Limpieza", "status": "pending"},
            {"name": "Dashboard", "status": "pending"},
            {"name": "Reporte", "status": "pending"},
        ],
        "metrics": {},
        "artifacts": {},
        "updated_at": now_iso(),
    }
    _write(proc_dir.name, status)

    # Bitácora: creación
    append_history(
        proc_dir.name, {"type": "process_created", "file": uploaded_path.name}
    )

    return {"id": proc_dir.name, "uploaded_path": str(uploaded_path)}


def _stage(proc_id: str, stage: str):
    """
    Context manager simple para registrar start/end + duración de una etapa.
    Uso:
        with _stage(proc_id, "Perfilado"):
            ... trabajo ...
    """

    class _Ctx:
        def __enter__(self_inner):
            self_inner.t0 = time.time()
            append_history(proc_id, {"type": "stage_start", "stage": stage})
            return self_inner

        def __exit__(self_inner, exc_type, exc, tb):
            dur_ms = int((time.time() - self_inner.t0) * 1000)
            if exc:
                append_history(
                    proc_id,
                    {
                        "type": "stage_end",
                        "stage": stage,
                        "status": "failed",
                        "duration_ms": dur_ms,
                        "error": str(exc),
                    },
                )
            else:
                append_history(
                    proc_id,
                    {
                        "type": "stage_end",
                        "stage": stage,
                        "status": "ok",
                        "duration_ms": dur_ms,
                    },
                )
            return False

    return _Ctx()


def process_pipeline(proc_id: str) -> None:
    """
    Procesa en background: queued → running → completed/failed.
    Genera:
      - reporte_perfilado.html
      - reporte_perfilado.csv
      - reporte_perfilado.pdf
      - dataset_limpio.csv (con columnas is_outlier, outlier_score, outlier_method si aplica)
      - auto_dashboard_spec.json (spec para render)
      - dashboard.html (render usando auto_spec)
      - reporte_integrado.html
      - (opcional) reporte_integrado.pdf  [si GENERATE_PDF=1]
    y actualiza status.json con métricas/resumen de limpieza.
    Registra bitácora JSONL por etapa.
    """
    append_history(proc_id, {"type": "process_started"})
    profile_path: Optional[Path] = None
    dash_path: Optional[Path] = None
    cleaned_csv: Optional[Path] = None
    auto_spec_path: Optional[Path] = None

    status: Dict[str, Any] = {}
    inferred_dates: Dict[str, Any] = {}

    try:
        # Cargar estado actual
        status = read_status(proc_id)

        # Running
        status["status"] = "running"
        status["current_step"] = "Perfilado"
        status["progress"] = 10
        _write(proc_id, status)

        # 1) Ingesta
        with _stage(proc_id, "Ingesta"):
            uploaded = RUNS_DIR / proc_id / "input" / status["filename"]
            df = read_dataframe(uploaded)
            status["metrics"].update(
                {"rows": int(df.shape[0]), "cols": int(df.shape[1])}
            )
            status["progress"] = 30
            _write(proc_id, status)
            append_history(
                proc_id,
                {
                    "type": "ingest_info",
                    "rows": int(df.shape[0]),
                    "cols": int(df.shape[1]),
                    "source": str(uploaded.name),
                },
            )

        # 2) Normalización de fechas
        with _stage(proc_id, "Fechas"):
            inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)
            append_history(
                proc_id,
                {
                    "type": "dates_normalized",
                    "columns": sorted(list(inferred_dates.keys())),
                },
            )

        # 3) Inferencia de tipos
        with _stage(proc_id, "InferenciaTipos"):
            roles = infer_types(df)
            for col in inferred_dates.keys():
                roles[col] = "fecha"
            status["metrics"]["inferred_types"] = roles
            status["progress"] = 45
            _write(proc_id, status)
            append_history(proc_id, {"type": "types_inferred", "roles": roles})

        # 4) Perfilado → HTML + CSV + PDF
        artifacts = RUNS_DIR / proc_id / "artifacts"
        with _stage(proc_id, "Perfilado"):
            # HTML (igual que antes)
            try:
                profile_path = generate_profile_html(
                    df, artifacts, TEMPLATES_DIR, roles=roles
                )
            except TypeError:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR)

            # Registrar HTML
            status["artifacts"]["reporte_perfilado.html"] = _rel_to_base(
                profile_path
            )

            # ===== CSV y PDF del MISMO perfilado =====
            try:
                perfil_csv_path = artifacts / "reporte_perfilado.csv"
                perfil_pdf_path = artifacts / "reporte_perfilado.pdf"

                build_profile_csv_from_html(profile_path, perfil_csv_path)
                build_profile_pdf_from_html(profile_path, perfil_pdf_path)

                status["artifacts"]["reporte_perfilado.csv"] = _rel_to_base(
                    perfil_csv_path
                )
                status["artifacts"]["reporte_perfilado.pdf"] = _rel_to_base(
                    perfil_pdf_path
                )
            except Exception as e:
                # Si algo falla, dejamos registro pero no rompemos el proceso
                append_history(
                    proc_id,
                    {
                        "type": "perfilado_export_error",
                        "error": str(e),
                    },
                )

            # marcar etapa OK como antes
            for s in status["steps"]:
                if s["name"] == "Perfilado":
                    s["status"] = "ok"
            status["progress"] = 55
            _write(proc_id, status)

        # 5) Limpieza → Reglas + CSV limpio + Outliers
        status["current_step"] = "Limpieza"
        status["progress"] = 60
        _write(proc_id, status)

        with _stage(proc_id, "Limpieza"):
            rules = load_rules_for_process(proc_id)
            rules_info = describe_rules(rules)
            append_history(proc_id, {"type": "rules_loaded", **rules_info})

            df_clean, clean_summary = clean_dataframe(df, rules=rules)

            with _stage(proc_id, "Outliers"):
                df_clean, out_summary = apply_isolation_forest(
                    df_clean,
                    contamination=OUTLIER_CONTAMINATION,
                    random_state=OUTLIER_RANDOM_STATE,
                )
                append_history(
                    proc_id,
                    {
                        "type": "outliers_isolation_forest",
                        "columns_used": out_summary.get("used_columns", []),
                        "contamination": out_summary.get(
                            "contamination", OUTLIER_CONTAMINATION
                        ),
                        "random_state": out_summary.get(
                            "random_state", OUTLIER_RANDOM_STATE
                        ),
                        "outliers": out_summary.get("outliers", 0),
                        "total": out_summary.get("total", 0),
                        "ratio": out_summary.get("ratio", 0.0),
                        "skipped": out_summary.get("skipped", False),
                    },
                )

            cleaned_csv = artifacts / "dataset_limpio.csv"
            df_clean.to_csv(cleaned_csv, index=False, encoding="utf-8")

            status["metrics"].update(
                {
                    "rows_clean": int(df_clean.shape[0]),
                    "cols_clean": int(df_clean.shape[1]),
                    "clean_summary": clean_summary,
                    "outliers_count": int(out_summary.get("outliers", 0)),
                    "outliers_ratio": float(out_summary.get("ratio", 0.0)),
                    "outliers_used_columns": out_summary.get("used_columns", []),
                    "outliers_contamination": float(
                        out_summary.get(
                            "contamination", OUTLIER_CONTAMINATION
                        )
                    ),
                }
            )
            status["artifacts"]["dataset_limpio.csv"] = _rel_to_base(cleaned_csv)

            for s in status["steps"]:
                if s["name"] == "Limpieza":
                    s["status"] = "ok"
            status["progress"] = 75
            _write(proc_id, status)

            append_history(proc_id, {"type": "clean_summary", **clean_summary})

        # 6) Dashboard (auto-spec + render)
        status["current_step"] = "Dashboard"
        status["progress"] = 80
        _write(proc_id, status)

        with _stage(proc_id, "Dashboard"):
            # 6.a) Generar SPEC automático (3 KPI, 4 charts, 4 filtros) con título bonito
            spec = auto_dashboard_spec(
                df_clean,
                roles=status["metrics"]["inferred_types"],
                source_name=status.get("filename"),
                process_id=proc_id,
            )

            # Validación opcional (si existe spec_guard)
            if validate_dashboard is not None:
                try:
                    health = validate_dashboard(
                        df_clean, spec, roles=status["metrics"]["inferred_types"]
                    )
                    append_history(
                        proc_id,
                        {
                            "type": "dashboard_health",
                            "score": float(getattr(health, "score", 0.0)),
                            "blocking": bool(getattr(health, "blocking", False)),
                        },
                    )
                    if STRICT_DASH_CHECK and bool(
                        getattr(health, "blocking", False)
                    ):
                        # Sólo si has activado modo estricto
                        spec = build_generic_spec(
                            df_clean,
                            roles=status["metrics"]["inferred_types"],
                            title=f"Dashboard seguro · {status.get('filename','')}",
                        )
                except Exception:
                    # Si algo falla en validación, seguimos con el spec generado
                    pass

            auto_spec_path = artifacts / "auto_dashboard_spec.json"
            auto_spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            status["artifacts"]["auto_dashboard_spec.json"] = _rel_to_base(
                auto_spec_path
            )
            append_history(
                proc_id,
                {
                    "type": "auto_dashboard_spec_built",
                    "path": _rel_to_base(auto_spec_path),
                },
            )

            # 6.b) Render del dashboard HTML usando el SPEC
            dash_path = generate_dashboard_html(
                df_clean,
                artifacts,
                csv_rel_name="dataset_limpio.csv",
                auto_spec=spec,
            )
            status["artifacts"]["dashboard.html"] = _rel_to_base(dash_path)
            for s in status["steps"]:
                if s["name"] == "Dashboard":
                    s["status"] = "ok"
            status["progress"] = 85
            _write(proc_id, status)

        # 7) Reporte integrado (HTML)
        status["current_step"] = "Reporte"
        status["progress"] = 90
        _write(proc_id, status)

        with _stage(proc_id, "Reporte"):
            quality = {
                "rows": int(df_clean.shape[0]),
                "cols": int(df_clean.shape[1]),
                "missing_overall_pct": float(
                    df_clean.isna().mean().mean() * 100.0
                ),
                "missing_by_col_pct": (
                    df_clean.isna()
                    .mean()
                    .mul(100)
                    .round(2)
                    .sort_values(ascending=False)
                    .to_dict()
                ),
            }
            links = {
                "dataset_limpio.csv": _rel_to_base(cleaned_csv)
                if cleaned_csv
                else "",
                "dashboard.html": _rel_to_base(dash_path) if dash_path else "",
                "auto_dashboard_spec.json": _rel_to_base(auto_spec_path)
                if auto_spec_path
                else "",
                "reporte_perfilado.html": _rel_to_base(profile_path)
                if profile_path
                else "",
            }
            report_path = artifacts / "reporte_integrado.html"
            build_full_report(clean_summary, quality, links, report_path)
            status["artifacts"]["reporte_integrado.html"] = _rel_to_base(
                report_path
            )
            for s in status["steps"]:
                if s["name"] == "Reporte":
                    s["status"] = "ok"

            # 7.b) (Opcional) PDF
            if os.getenv("GENERATE_PDF", "0") == "1":
                try:
                    pdf_path = artifacts / "reporte_integrado.pdf"
                    ctx = {
                        "title": "Reporte integrado",
                        "generated_at": now_iso(),
                        "process_id": proc_id,
                        "clean_summary": clean_summary,
                        "quality": quality,
                        "links": {
                            "reporte_perfilado": links.get(
                                "reporte_perfilado.html"
                            )
                            or "",
                            "dashboard": links.get("dashboard.html") or "",
                            "clean_csv": links.get("dataset_limpio.csv") or "",
                            "auto_spec": links.get(
                                "auto_dashboard_spec.json"
                            )
                            or "",
                        },
                        "outliers": {
                            "used_columns": status["metrics"].get(
                                "outliers_used_columns", []
                            ),
                            "contamination": status["metrics"].get(
                                "outliers_contamination", 0.0
                            ),
                            "outliers": status["metrics"].get(
                                "outliers_count", 0
                            ),
                            "total": int(quality["rows"]),
                            "ratio": status["metrics"].get(
                                "outliers_ratio", 0.0
                            ),
                        },
                    }
                    build_pdf_from_template("report.j2.html", pdf_path, ctx)
                    status["artifacts"]["reporte_integrado.pdf"] = _rel_to_base(
                        pdf_path
                    )
                    _write(proc_id, status)
                    append_history(
                        proc_id,
                        {
                            "type": "pdf_generated",
                            "path": _rel_to_base(pdf_path),
                        },
                    )
                except Exception as e:
                    append_history(
                        proc_id,
                        {"type": "pdf_failed", "error": str(e)},
                    )

        # 8) Final
        status["status"] = "completed"
        status["current_step"] = "Reporte"
        status["progress"] = 100
        _write(proc_id, status)

        append_history(proc_id, {"type": "process_completed", "status": "completed"})

    except Exception as e:
        # Manejo de error robusto: marca el proceso como failed y registra
        append_history(proc_id, {"type": "process_failed", "error": str(e)})

        # Si no había status cargado, crea uno mínimo
        if not status:
            status = {
                "id": proc_id,
                "status": "failed",
                "progress": 0,
                "steps": [
                    {
                        "name": s,
                        "status": "failed" if i > 0 else "ok",
                    }
                    for i, s in enumerate(STAGES)
                ],
            }

        # Marca paso actual y generales en failed
        status["status"] = "failed"
        status["error"] = str(e)
        status["progress"] = int(status.get("progress", 0))
        cur = status.get("current_step") or ""
        for s in status.get("steps", []):
            if s.get("name") == cur:
                s["status"] = "failed"
        _write(proc_id, status)
