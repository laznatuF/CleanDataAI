# app/application/pipeline.py
from __future__ import annotations

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

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
from app.core.config import (
    RUNS_DIR,
    BASE_DIR,
    TEMPLATES_DIR,
    OUTLIER_CONTAMINATION,
    OUTLIER_RANDOM_STATE,
)

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
    # moneda
    if s.str.contains(r"[$€£]|^\s*[A-Z]{2,3}\s*\d", regex=True).mean() > 0.5:
        return "moneda"
    # fecha
    dt = parse_dates_series(s)
    if dt.notna().mean() > 0.8:
        return "fecha"
    # numérico
    sn = s.str.replace(r"[.\s]", "", regex=True).str.replace(",", ".", regex=False)
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
    append_history(proc_dir.name, {
        "type": "process_created",
        "file": uploaded_path.name,
    })

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
                append_history(proc_id, {
                    "type": "stage_end",
                    "stage": stage,
                    "status": "failed",
                    "duration_ms": dur_ms,
                    "error": str(exc),
                })
            else:
                append_history(proc_id, {
                    "type": "stage_end",
                    "stage": stage,
                    "status": "ok",
                    "duration_ms": dur_ms,
                })
            return False
    return _Ctx()


def process_pipeline(proc_id: str) -> None:
    """
    Procesa en background: queued → running → completed/failed.
    Genera:
      - reporte_perfilado.html
      - dataset_limpio.csv (con columnas is_outlier, outlier_score, outlier_method si aplica)
      - dashboard.html
      - reporte_integrado.html
      - (opcional) reporte_integrado.pdf  [si GENERATE_PDF=1]
    y actualiza status.json con métricas/resumen de limpieza.
    Registra bitácora JSONL por etapa.
    """
    append_history(proc_id, {"type": "process_started"})
    profile_path: Optional[Path] = None
    dash_path: Optional[Path] = None
    cleaned_csv: Optional[Path] = None

    try:
        # Cargar estado
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
            status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})
            status["progress"] = 30
            _write(proc_id, status)
            append_history(proc_id, {
                "type": "ingest_info",
                "rows": int(df.shape[0]),
                "cols": int(df.shape[1]),
                "source": str(uploaded.name),
            })

        # 2) Normalización de fechas
        with _stage(proc_id, "Fechas"):
            inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)
            append_history(proc_id, {
                "type": "dates_normalized",
                "columns": sorted(list(inferred_dates.keys())),
            })

        # 3) Inferencia de tipos
        with _stage(proc_id, "InferenciaTipos"):
            roles = infer_types(df)
            for col in inferred_dates.keys():
                roles[col] = "fecha"
            status["metrics"]["inferred_types"] = roles
            status["progress"] = 45
            _write(proc_id, status)
            append_history(proc_id, {"type": "types_inferred", "roles": roles})

        # 4) Perfilado → HTML
        artifacts = RUNS_DIR / proc_id / "artifacts"
        with _stage(proc_id, "Perfilado"):
            try:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR, roles=roles)
            except TypeError:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR)

            status["artifacts"]["reporte_perfilado.html"] = _rel_to_base(profile_path)
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
                append_history(proc_id, {
                    "type": "outliers_isolation_forest",
                    "columns_used": out_summary.get("used_columns", []),
                    "contamination": out_summary.get("contamination", OUTLIER_CONTAMINATION),
                    "random_state": out_summary.get("random_state", OUTLIER_RANDOM_STATE),
                    "outliers": out_summary.get("outliers", 0),
                    "total": out_summary.get("total", 0),
                    "ratio": out_summary.get("ratio", 0.0),
                    "skipped": out_summary.get("skipped", False),
                })

            cleaned_csv = artifacts / "dataset_limpio.csv"
            df_clean.to_csv(cleaned_csv, index=False, encoding="utf-8")

            status["metrics"].update({
                "rows_clean": int(df_clean.shape[0]),
                "cols_clean": int(df_clean.shape[1]),
                "clean_summary": clean_summary,
                "outliers_count": int(out_summary.get("outliers", 0)),
                "outliers_ratio": float(out_summary.get("ratio", 0.0)),
                "outliers_used_columns": out_summary.get("used_columns", []),
                "outliers_contamination": float(out_summary.get("contamination", OUTLIER_CONTAMINATION)),
            })
            status["artifacts"]["dataset_limpio.csv"] = _rel_to_base(cleaned_csv)

            for s in status["steps"]:
                if s["name"] == "Limpieza":
                    s["status"] = "ok"
            status["progress"] = 75
            _write(proc_id, status)

            append_history(proc_id, {"type": "clean_summary", **clean_summary})

        # 6) Dashboard
        status["current_step"] = "Dashboard"
        status["progress"] = 80
        _write(proc_id, status)

        with _stage(proc_id, "Dashboard"):
            dash_path = generate_dashboard_html(df_clean, artifacts, csv_rel_name="dataset_limpio.csv")
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
                "missing_overall_pct": float(df_clean.isna().mean().mean() * 100.0),
                "missing_by_col_pct": df_clean.isna()
                    .mean().mul(100).round(2)
                    .sort_values(ascending=False)
                    .to_dict(),
            }
            links = {
                "dataset_limpio.csv": _rel_to_base(cleaned_csv) if cleaned_csv else "",
                "dashboard.html": _rel_to_base(dash_path) if dash_path else "",
                "reporte_perfilado.html": _rel_to_base(profile_path) if profile_path else "",
            }
            report_path = artifacts / "reporte_integrado.html"
            build_full_report(clean_summary, quality, links, report_path)
            status["artifacts"]["reporte_integrado.html"] = _rel_to_base(report_path)
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
                            "reporte_perfilado": links.get("reporte_perfilado.html") or "",
                            "dashboard": links.get("dashboard.html") or "",
                            "clean_csv": links.get("dataset_limpio.csv") or "",
                        },
                        "outliers": {
                            "used_columns": status["metrics"].get("outliers_used_columns", []),
                            "contamination": status["metrics"].get("outliers_contamination", 0.0),
                            "outliers": status["metrics"].get("outliers_count", 0),
                            "total": int(quality["rows"]),
                            "ratio": status["metrics"].get("outliers_ratio", 0.0),
                        },
                    }
                    build_pdf_from_template("report.j2.html", pdf_path, ctx)
                    status["artifacts"]["reporte_integrado.pdf"] = _rel_to_base(pdf_path)
                    _write(proc_id, status)
                    append_history(proc_id, {"type": "pdf_generated", "path": _rel_to_base(pdf_path)})
                except Exception as e:
                    append_history(proc_id, {"type": "pdf_failed", "error": str(e)})

        # 8) Final
        status["status"] = "completed"
        status["current_step"] = "Reporte"
        status["progress"] = 100
        _write(proc_id, status)

        append_history(proc_id, {"type": "process_completed", "status": "completed"})

    except Exception as e:
        append_history(proc_id, {"type": "process_failed", "error": str(e)})
        fail = {
            "id": proc_id,
            "status": "failed",
            "progress": status.get("progress", 0) if "status" in locals() else 0,
            "error": str(e),
            "updated_at": now_iso(),
        }
        write_status(proc_id, fail)
