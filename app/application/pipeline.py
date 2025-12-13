# app/application/pipeline.py
from __future__ import annotations

import os
import time
import json
import re
import shutil
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from typing import Dict, Any, List, Optional
from os.path import relpath

import pandas as pd
import numpy as np

from app.infrastructure.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
)
from app.infrastructure.process_repo_fs import read_status, write_status
from app.infrastructure.history_repo_fs import append_history
from app.infrastructure.datasources import read_dataframe
from app.infrastructure.profiling import generate_profile_html
from app.application.dates import normalize_dates_in_df
from app.application.cleaning import clean_dataframe
from app.application.dashboard import generate_dashboard_html
from app.application.report_full import build_full_report
from app.application.outliers import apply_isolation_forest
from app.application.rules import load_rules_for_process
from app.application.semantics import infer_semantics

# Importación robusta de report_narrative
try:
    from app.application.report_narrative import build_narrative_report
except ImportError as e:
    print(f"⚠️ Error importando report_narrative: {e}")
    build_narrative_report = None

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
#         Config / Flags
# ============================================================

USE_AUTOSPEC_FALLBACK = False
STRICT_DASH_CHECK = os.getenv("STRICT_DASH_CHECK", "0") == "1"
PROFILE_EXTRAS = os.getenv("PROFILE_EXTRAS", "1") == "1"

# Preferencia de métrica principal para Dashboard
# Sugerido: total_venta_clp (GMV), total_bruto_clp o total_neto_clp
DASH_PRIMARY_METRIC = os.getenv("DASH_PRIMARY_METRIC", "total_venta_clp").strip() or "total_venta_clp"

# ============================================================
#  Autospec fallback
# ============================================================

try:
    if not USE_AUTOSPEC_FALLBACK:
        from app.application.autospec import auto_dashboard_spec
    else:
        raise ImportError()
except Exception:
    def auto_dashboard_spec(df, roles=None, source_name=None, process_id=None):
        return {"charts": [], "source_name": source_name, "process_id": process_id}

# ============================================================
#  Helpers
# ============================================================

STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        try:
            if pd.isna(x):
                return default
        except Exception:
            pass
        return float(x)
    except Exception:
        return default

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        try:
            if pd.isna(x):
                return default
        except Exception:
            pass
        return int(x)
    except Exception:
        return default

def _write(proc_id: str, status: Dict[str, Any]) -> None:
    status["updated_at"] = now_iso()
    try:
        p = int(status.get("progress", 0))
    except Exception:
        p = 0
    status["progress"] = max(0, min(100, p))
    write_status(proc_id, status)

def _rel_to_base(p: Path) -> str:
    base_abs = Path(BASE_DIR).resolve()
    p_abs = Path(p).resolve()
    try:
        rel = p_abs.relative_to(base_abs)
        return rel.as_posix()
    except Exception:
        return relpath(str(p_abs), start=str(base_abs)).replace("\\", "/")

def _ensure_steps(status: Dict[str, Any]) -> None:
    if not status.get("steps"):
        status["steps"] = [
            {"name": "Subir archivo", "status": "ok"},
            {"name": "Perfilado", "status": "pending"},
            {"name": "Limpieza", "status": "pending"},
            {"name": "Dashboard", "status": "pending"},
            {"name": "Reporte", "status": "pending"},
        ]

def _mark_step(status: Dict[str, Any], step_name: str, step_status: str) -> None:
    for s in status.get("steps", []):
        if s.get("name") == step_name:
            s["status"] = step_status

def _pick_primary_metric(df: pd.DataFrame) -> str:
    """
    Decide la métrica principal REAL de ventas para dashboard.
    Evita caer en precio_unitario_unificado.
    """
    preferred = [DASH_PRIMARY_METRIC, "total_venta_clp", "total_bruto_clp", "total_neto_clp"]
    for c in preferred:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            return c

    # Si vienen como strings numéricas
    for c in preferred:
        if c in df.columns:
            try:
                tmp = pd.to_numeric(df[c], errors="coerce")
                if tmp.notna().mean() > 0.5:
                    df[c] = tmp
                    return c
            except Exception:
                pass

    # Último recurso: primera numérica que NO sea precio unitario
    banned = {"precio_unitario_unificado", "precio_unitario", "price", "unit_price"}
    for c in df.columns:
        if c in banned:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            return c

    return "total_venta_clp"

def _force_primary_metric_in_spec(spec: Any, primary_metric: str) -> Any:
    """
    Parche robusto: si el autospec eligió precio_unitario_unificado como y/value/metric,
    lo reemplazamos por la métrica principal real.
    Evita reemplazar dentro de charts tipo scatter/bubble.
    """
    if not isinstance(spec, dict):
        return spec

    target_vals = {"precio_unitario_unificado"}
    likely_keys = {
        "y", "y_col", "y_field",
        "value", "value_col", "value_field",
        "metric", "metric_col", "metric_field",
        "measure", "measure_col", "measure_field",
        "amount", "amount_col", "amount_field",
        "sum_col", "agg_col",
    }

    def _is_scatter_like(d: dict) -> bool:
        t = str(d.get("type") or d.get("chart_type") or d.get("kind") or "").lower()
        return ("scatter" in t) or ("bubble" in t)

    def walk(obj: Any, allow_replace: bool = True) -> Any:
        if isinstance(obj, dict):
            allow = allow_replace and (not _is_scatter_like(obj))
            out = {}
            for k, v in obj.items():
                if isinstance(v, str):
                    kn = str(k).lower()
                    if (kn in likely_keys) or kn.endswith("_col") or kn.endswith("_field") or ("metric" in kn) or (kn in {"x", "y"}):
                        if allow and primary_metric and (v in target_vals or ("precio_unitario_unificado" in v)):
                            out[k] = primary_metric
                            continue
                out[k] = walk(v, allow_replace=allow)
            return out

        if isinstance(obj, list):
            return [walk(x, allow_replace=allow_replace) for x in obj]

        return obj

    spec2 = walk(spec, allow_replace=True)

    # pistas extra (inocuas si no las usa)
    spec2["primary_metric"] = primary_metric
    spec2["preferred_metric"] = primary_metric
    return spec2

# ============================================================
#  Creación de procesos
# ============================================================

def create_initial_process(file) -> Dict[str, Any]:
    """Modo original (single). Se mantiene para compatibilidad."""
    validate_filename_and_size(file)
    proc_dir = create_process_dir()
    (proc_dir / "input").mkdir(parents=True, exist_ok=True)
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    uploaded_path = save_upload(file, proc_dir)

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
    append_history(proc_dir.name, {"type": "process_created", "file": uploaded_path.name, "mode": "single"})
    return {"id": proc_dir.name, "uploaded_path": str(uploaded_path)}

def create_initial_process_multi(files: List[Any]) -> Dict[str, Any]:
    """Modo multicanal: guarda N archivos en input/ y marca mode=multi."""
    if not files:
        raise ValueError("No se recibieron archivos para el proceso multicanal.")

    proc_dir = create_process_dir()
    (proc_dir / "input").mkdir(parents=True, exist_ok=True)
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    saved_names: List[str] = []
    for f in files:
        validate_filename_and_size(f)
        uploaded_path = save_upload(f, proc_dir)
        saved_names.append(uploaded_path.name)

    main_name = saved_names[0] if saved_names else ""

    status: Dict[str, Any] = {
        "id": proc_dir.name,
        "filename": main_name,  # compat UI antigua
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
        "metrics": {"input_files": saved_names},
        "artifacts": {},
        "mode": "multi",
        "updated_at": now_iso(),
    }
    _write(proc_dir.name, status)
    append_history(proc_dir.name, {"type": "process_created", "files": saved_names, "mode": "multi"})
    return {"id": proc_dir.name, "uploaded_paths": saved_names}

# ============================================================
#  Context manager de etapas e error handler
# ============================================================

def _stage(proc_id: str, stage: str):
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
                    "error": str(exc)
                })
            else:
                append_history(proc_id, {"type": "stage_end", "stage": stage, "status": "ok", "duration_ms": dur_ms})
            return False
    return _Ctx()

def _handle_error(proc_id, status, e):
    append_history(proc_id, {"type": "process_failed", "error": str(e)})
    if not status:
        status = {"id": proc_id}
    status["status"] = "failed"
    status["error"] = str(e)
    _write(proc_id, status)

# ============================================================
#  Ingesta multicanal
# ============================================================

def _infer_channel_from_name(path: Path) -> str:
    """
    Detecta canal por nombre.
    Importante: si el archivo es ML Envíos, lo marcamos como mercado_libre_envios.
    """
    name = path.name.lower()

    is_ml = ("mercado" in name) or bool(re.search(r"(^|[^a-z])ml([^a-z]|$)", name))
    if is_ml and ("envio" in name or "envíos" in name or "shipping" in name or "shipment" in name):
        return "mercado_libre_envios"

    if "shopify" in name:
        return "shopify"

    if is_ml:
        return "mercado_libre"

    if "instagram" in name or re.search(r"(^|[^a-z])ig([^a-z]|$)", name):
        return "instagram_shop"

    return "desconocido"

def _norm_key(x: str) -> str:
    x = str(x or "").strip().lower()
    x = re.sub(r"[\s\-\/]+", "_", x)
    x = re.sub(r"__+", "_", x)
    return x

def _looks_like_ml_envios_df(df) -> bool:
    """
    Detector ESTRICTO de archivos de envíos.

    IMPORTANTE:
    - NO usamos 'estado_envio' como señal, porque export de ventas ML suele traerlo.
    - Exigimos >=2 señales "fuertes" de envíos: tracking, dirección/ciudad, carrier, fechas despacho/entrega, postal.
    """
    cols = {_norm_key(c) for c in df.columns}

    has_venta_id = any(k in cols for k in ["id_venta", "venta_id", "id_orden", "order_id", "idventa"])

    has_tracking = any(k in cols for k in [
        "tracking", "tracking_number",
        "numero_seguimiento", "numero_de_seguimiento",
        "n_seguimiento", "n_de_seguimiento"
    ])

    has_address = any(k in cols for k in [
        "direccion_envio", "direccion_destino", "direccion", "address", "shipping_address"
    ])

    has_city_region = any(k in cols for k in [
        "ciudad_envio", "ciudad_destino", "shipping_city",
        "comuna_envio", "comuna_destino",
        "region_envio", "region_destino"
    ])

    has_carrier = any(k in cols for k in [
        "transportista", "carrier", "shipping_carrier", "empresa_transporte"
    ])

    has_ship_dates = any(k in cols for k in [
        "fecha_despacho", "fecha_envio",
        "fecha_entrega", "fecha_entrega_estimada",
        "estimated_delivery", "delivery_date"
    ])

    has_postal = any(k in cols for k in [
        "codigo_postal", "zip", "postal"
    ])

    score = sum([has_tracking, has_address, has_city_region, has_carrier, has_ship_dates, has_postal])

    return bool(has_venta_id and score >= 2)

def _merge_multichannel_files(input_dir: Path) -> pd.DataFrame:
    dfs: List[pd.DataFrame] = []
    if not input_dir.exists():
        raise FileNotFoundError(f"No existe input_dir: {input_dir}")

    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        try:
            df_i = read_dataframe(p).copy()

            canal = _infer_channel_from_name(p)
            if canal == "mercado_libre" and _looks_like_ml_envios_df(df_i):
                canal = "mercado_libre_envios"

            df_i["canal"] = canal
            df_i["__source_file"] = p.name
            dfs.append(df_i)
        except Exception as e:
            print(f"⚠️ Error leyendo archivo multicanal {p.name}: {e}")

    if not dfs:
        raise FileNotFoundError("No se encontraron archivos de entrada para el modo multicanal.")

    return pd.concat(dfs, ignore_index=True, sort=False)

# ============================================================
#  UNIR ML ENVIOS + ML VENTAS (por venta_id) y eliminar filas de envíos
# ============================================================

_NULL_STRINGS = {"", "nan", "NaN", "none", "None", "null", "NULL", "nil", "NIL", "<NA>", "<na>"}

def _clean_text_series(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    s = s.replace({k: pd.NA for k in _NULL_STRINGS})
    return s

def _clean_text_series_loose(s: pd.Series) -> pd.Series:
    """
    Variante para merge: también considera placeholders tipo 'No informado...' como NA
    para permitir que envíos sobre-escriba ventas vacías.
    """
    s = _clean_text_series(s)
    try:
        mask = s.str.contains("no informado", case=False, na=False)
        s = s.mask(mask, pd.NA)
    except Exception:
        pass
    return s

def _normalize_id_series(s: pd.Series) -> pd.Series:
    """
    Normaliza IDs para merge:
    - si vienen como float "123.0" => "123"
    - trims, NA strings
    """
    if s is None:
        return pd.Series([], dtype="string")
    ss = s.astype("string").str.strip()
    ss = ss.replace({k: pd.NA for k in _NULL_STRINGS})
    ss = ss.str.replace(r"\.0$", "", regex=True)
    return ss

def _find_actual_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Encuentra la primera columna real en df cuya versión normalizada coincide con algún candidato normalizado.
    No renombra columnas.
    """
    norm_to_actual = {_norm_key(c): c for c in df.columns}
    cand_norms = [_norm_key(c) for c in candidates]
    for cn in cand_norms:
        if cn in norm_to_actual:
            return norm_to_actual[cn]
    return None

def _coalesce_text_any(df: pd.DataFrame, candidates: List[str]) -> pd.Series:
    out = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")
    for cand in candidates:
        col = _find_actual_col(df, [cand])
        if col and col in df.columns:
            out = out.fillna(_clean_text_series(df[col]))
    return out

def _first_non_null(series: pd.Series):
    s = series.dropna()
    if len(s) == 0:
        return pd.NA
    return s.iloc[0]

def _attach_ml_envios_to_ml_ventas(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty or "canal" not in df.columns:
        return {"df": df, "stats": {"has_envios": False}}

    df = df.copy()
    canal = _clean_text_series(df["canal"]).str.lower()

    mask_env = canal.eq("mercado_libre_envios")
    mask_ven = canal.eq("mercado_libre")

    # 1) Solo envíos (sin ventas) -> NO borrar envíos
    if not mask_ven.any():
        return {
            "df": df,
            "stats": {
                "has_envios": bool(mask_env.any()),
                "note": "Se subieron envíos pero no ventas; se dejan filas de envíos intactas.",
            },
        }

    # Si no hay envíos, no hay nada que anexar
    if not mask_env.any():
        return {"df": df, "stats": {"has_envios": False}}

    env = df.loc[mask_env].copy()
    ven = df.loc[mask_ven].copy()

    ven_id = _coalesce_text_any(ven, ["venta_id", "id_venta", "id venta", "id_de_venta", "idventa", "id", "id_orden", "order_id"])
    env_id = _coalesce_text_any(env, ["venta_id", "id_venta", "id venta", "id_de_venta", "idventa", "id", "id_orden", "order_id"])

    ven["venta_id"] = _normalize_id_series(ven_id)
    env["venta_id"] = _normalize_id_series(env_id)

    # 2) Si no se puede mapear venta_id -> para dashboard coherente, elimina envíos
    if ven["venta_id"].isna().all() or env["venta_id"].isna().all():
        out = df.loc[~mask_env].copy()
        return {
            "df": out,
            "stats": {
                "has_envios": True,
                "note": "No se pudo mapear venta_id; se eliminaron filas de envíos para no contaminar el dashboard.",
            },
        }

    # Campos desde envíos
    env["ciudad_envio"] = _coalesce_text_any(env, ["ciudad_envio", "ciudad_destino", "ciudad_de_destino", "destino_ciudad", "shipping_city", "city"])
    env["comuna_envio"] = _coalesce_text_any(env, ["comuna_envio", "comuna_destino", "municipio_destino", "municipio", "comuna"])
    env["region_envio"] = _coalesce_text_any(env, ["region_envio", "region_destino", "región_destino", "region"])
    env["direccion_envio"] = _coalesce_text_any(env, ["direccion_envio", "direccion_destino", "dirección_destino", "direccion", "address"])
    env["codigo_postal"] = _coalesce_text_any(env, ["codigo_postal", "código_postal", "zip", "postal_code"])
    env["estado_envio"] = _coalesce_text_any(env, ["estado_envio", "estado_del_envio", "status", "shipment_status", "estado_venta"])
    env["tracking"] = _coalesce_text_any(env, ["tracking", "tracking_number", "numero_seguimiento", "numero_de_seguimiento", "n_de_seguimiento", "n_seguimiento"])
    env["transportista"] = _coalesce_text_any(env, ["transportista", "carrier", "shipping_carrier", "empresa_transporte"])

    env_agg = (
        env.groupby("venta_id", dropna=True)
           .agg({
               "ciudad_envio": _first_non_null,
               "comuna_envio": _first_non_null,
               "region_envio": _first_non_null,
               "direccion_envio": _first_non_null,
               "codigo_postal": _first_non_null,
               "estado_envio": _first_non_null,
               "tracking": _first_non_null,
               "transportista": _first_non_null,
           })
           .reset_index()
    )

    ven_idx = ven.index
    ven_m = ven.merge(env_agg, how="left", on="venta_id", suffixes=("", "_env"))
    ven_m.index = ven_idx

    # coalesce de columnas
    enriched_cols = ["ciudad_envio","comuna_envio","region_envio","direccion_envio","codigo_postal","estado_envio","tracking","transportista"]
    for col in enriched_cols:
        col_env = f"{col}_env"
        if col_env in ven_m.columns:
            base = _clean_text_series_loose(ven_m[col]) if col in ven_m.columns else pd.Series([pd.NA]*len(ven_m), index=ven_m.index)
            ven_m[col] = base.fillna(_clean_text_series(ven_m[col_env]))
            ven_m.drop(columns=[col_env], inplace=True)

    any_field = pd.Series(False, index=ven_m.index)
    for col in enriched_cols:
        if col in ven_m.columns:
            any_field = any_field | ven_m[col].notna()

    matched = int(any_field.sum())
    coverage = float(matched / max(1, len(ven_m)) * 100.0)

    # 3) Merge OK -> elimina filas envíos y deja dataset limpio para dashboard
    others = df.loc[~(mask_env | mask_ven)].copy()
    out = pd.concat([others, ven_m], axis=0).sort_index()

    return {
        "df": out,
        "stats": {
            "has_envios": True,
            "envios_rows": int(mask_env.sum()),
            "ventas_rows": int(mask_ven.sum()),
            "matched_ventas": matched,
            "coverage_pct": round(coverage, 2),
        },
    }

# ============================================================
#  Armonización / UNIFICACIÓN (post-limpieza) - ROBUSTA
# ============================================================

def _parse_datetime_series(s: pd.Series) -> pd.Series:
    p1 = pd.to_datetime(s, errors="coerce", dayfirst=True, utc=False)
    p2 = pd.to_datetime(s, errors="coerce", dayfirst=False, utc=False)
    if p2.notna().mean() > p1.notna().mean() + 0.05:
        return p2
    return p1

def _to_numeric_like_clp(s: pd.Series) -> pd.Series:
    """
    Convierte strings tipo "$ 1.234.567", "1,234,567", "1234.56" a float.
    Maneja separadores miles y decimales de forma robusta.
    """
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")

    ss = s.astype("string").str.strip()
    ss = ss.replace({k: pd.NA for k in _NULL_STRINGS})
    ss = ss.str.replace(r"(?i)clp", "", regex=True)
    ss = ss.str.replace(r"[\s\$]", "", regex=True)

    null_lower = {k.lower() for k in _NULL_STRINGS}

    def norm_one(x: Any) -> Any:
        try:
            if pd.isna(x):
                return np.nan
        except Exception:
            pass

        x = str(x).strip()
        if x == "" or x.lower() in null_lower:
            return np.nan

        x = re.sub(r"[^\d\-\.,]", "", x)

        if "," in x and "." in x:
            if x.rfind(",") > x.rfind("."):
                x = x.replace(".", "")
                x = x.replace(",", ".")
            else:
                x = x.replace(",", "")
        elif "," in x:
            if re.search(r",\d{1,2}$", x):
                x = x.replace(",", ".")
            else:
                x = x.replace(",", "")
        elif "." in x:
            if not re.search(r"\.\d{1,2}$", x):
                x = x.replace(".", "")

        try:
            return float(x)
        except Exception:
            return np.nan

    return pd.to_numeric(ss.map(norm_one), errors="coerce")

def _coalesce_datetime(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    out = pd.Series([pd.NaT] * len(df), index=df.index)
    for c in cols:
        if c in df.columns:
            out = out.fillna(_parse_datetime_series(df[c]))
    return out

def _coalesce_numeric(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    out = pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
    for c in cols:
        if c in df.columns:
            out = out.fillna(_to_numeric_like_clp(df[c]))
    return out

def _coalesce_text(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    out = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")
    for c in cols:
        if c in df.columns:
            out = out.fillna(_clean_text_series(df[c]))
    return out

def _normalize_shopify_detail(src: pd.Series) -> pd.Series:
    s = src.astype("string").str.strip().str.lower()
    s = s.replace({k: pd.NA for k in _NULL_STRINGS})
    out = s.copy()
    out = out.where(~out.str.contains("instagram", na=False), "instagram_shop")
    out = out.where(~out.str.contains("online", na=False), "shopify_web")
    out = out.where(~out.str.contains("tienda", na=False), "shopify_web")
    out = out.fillna("shopify")
    return out

def _harmonize_multichannel_postclean(df: pd.DataFrame) -> pd.DataFrame:
    """
    UNIFICACIÓN CORRECTA (POST-LIMPIEZA):
    - Asegura producto, cantidades, precios.
    - Ciudad ML: si NO se unió con Envíos, marca "No informado (ML Ventas)".
    - Totales consistentes: total_bruto_clp, total_neto_clp y total_venta_clp (= bruto/GMV).
    """
    df = df.copy()

    canal_base = _clean_text_series(df.get("canal", pd.Series([pd.NA] * len(df)))).str.lower()

    # Seguridad: si por alguna razón quedaron filas envíos, elimínalas aquí
    mask_envios = canal_base.eq("mercado_libre_envios")
    if mask_envios.any():
        df = df.loc[~mask_envios].copy()
        canal_base = _clean_text_series(df.get("canal", pd.Series([pd.NA] * len(df)))).str.lower()

    df["venta_id"] = _normalize_id_series(_coalesce_text(df, [
        "venta_id",
        "id_venta", "id venta", "id_venta_", "id",
        "order_id", "order_number", "order number", "name", "order_name", "numero_orden", "n_mero_orden"
    ]))

    df["canal_detalle"] = _clean_text_series(df.get("canal_detalle", canal_base)).astype("string").str.lower()
    mask_shopify = canal_base.eq("shopify")

    order_source = _coalesce_text(df, ["order_source", "source_name", "source", "origen", "source name", "source_name_"])
    if mask_shopify.any():
        df.loc[mask_shopify, "canal_detalle"] = _normalize_shopify_detail(order_source.loc[mask_shopify])

    df["fecha_venta"] = _coalesce_datetime(df, ["fecha_venta", "fecha", "created_at", "paid_at", "paid at", "created at"])

    df["producto_nombre"] = _coalesce_text(df, [
        "producto_nombre",
        "t_tulo_publicaci_n", "titulo_publicacion", "título_publicación", "título publicación",
        "titulo", "título",
        "lineitem_name", "line_item_name", "line item name",
        "producto", "name_producto"
    ])

    df["cantidad_unificada"] = _coalesce_numeric(df, [
        "cantidad_unificada", "cantidad", "qty", "quantity",
        "lineitem_quantity", "line_item_quantity", "line item quantity"
    ])
    df["precio_unitario_unificado"] = _coalesce_numeric(df, [
        "precio_unitario_unificado", "precio_unitario", "precio",
        "lineitem_price", "line_item_price", "line item price", "price"
    ])

    df["cliente_nombre"] = _coalesce_text(df, [
        "cliente_nombre", "comprador", "usuario",
        "billing_name", "shipping_name", "customer", "cliente"
    ])

    df["ciudad_envio"] = _coalesce_text(df, [
        "ciudad_envio", "shipping_city", "billing_city", "ciudad", "city",
        "ciudad_destino", "comuna_destino"
    ])
    
    df["comuna_envio"] = _coalesce_text(df, ["comuna_envio", "comuna_destino", "municipio_destino", "municipio", "comuna"])
    df["region_envio"] = _coalesce_text(df, ["region_envio", "region_destino", "región_destino", "region"])
    df["direccion_envio"] = _coalesce_text(df, ["direccion_envio", "direccion_destino", "dirección_destino", "direccion", "address"])
    df["codigo_postal"] = _coalesce_text(df, ["codigo_postal", "código_postal", "zip", "postal_code"])
    df["estado_envio"] = _coalesce_text(df, ["estado_envio", "estado_env_o", "estado_del_envio", "status", "shipment_status", "estado_venta"])
    df["tracking"] = _coalesce_text(df, ["tracking", "tracking_number", "numero_seguimiento", "numero_de_seguimiento", "n_de_seguimiento", "n_seguimiento"])
    df["transportista"] = _coalesce_text(df, ["transportista", "carrier", "shipping_carrier", "empresa_transporte"])

    mask_ml = canal_base.eq("mercado_libre")
    df.loc[mask_ml & df["ciudad_envio"].isna(), "ciudad_envio"] = "No informado (ML Ventas)"

    df["comision_clp"] = _coalesce_numeric(df, ["comision_clp", "comisi_n", "comision", "fee", "commission", "comisión"])
    df["costo_envio_clp"] = _coalesce_numeric(df, ["costo_envio_clp", "costo_env_o", "costo_envio", "shipping", "shipping_cost", "envio"])
    df["impuestos_clp"] = _coalesce_numeric(df, ["impuestos_clp", "taxes", "tax", "iva", "impuesto"])
    df["descuento_clp"] = _coalesce_numeric(df, ["descuento_clp", "discount_amount", "discount", "descuento"])

    df["total_bruto_clp"] = np.nan
    df["total_neto_clp"] = np.nan

    ml_gmv = _coalesce_numeric(df, ["total_bruto", "total_bruto_clp", "total", "total_venta_clp"])
    ml_payout = _coalesce_numeric(df, ["total_neto", "total_neto_clp"])

    if mask_ml.any():
        df.loc[mask_ml, "total_bruto_clp"] = ml_gmv.loc[mask_ml]
        fallback_payout = ml_gmv - df["comision_clp"].fillna(0) - df["costo_envio_clp"].fillna(0)
        df.loc[mask_ml, "total_neto_clp"] = ml_payout.loc[mask_ml].fillna(fallback_payout.loc[mask_ml])

    shop_subtotal = _coalesce_numeric(df, ["subtotal"])
    shop_total = _coalesce_numeric(df, ["total", "total_price", "currency_total_clp"])
    shop_gmv_est = shop_total - df["costo_envio_clp"].fillna(0) - df["impuestos_clp"].fillna(0)
    line_gmv = df["precio_unitario_unificado"].fillna(0) * df["cantidad_unificada"].fillna(0)

    if mask_shopify.any():
        df.loc[mask_shopify, "total_bruto_clp"] = (
            shop_subtotal.loc[mask_shopify]
            .fillna(shop_gmv_est.loc[mask_shopify])
            .fillna(line_gmv.loc[mask_shopify])
        )
        df.loc[mask_shopify, "total_neto_clp"] = df.loc[mask_shopify, "total_bruto_clp"]
        df.loc[mask_shopify, "comision_clp"] = df.loc[mask_shopify, "comision_clp"].fillna(0.0)

    df["total_bruto_clp"] = pd.to_numeric(df["total_bruto_clp"], errors="coerce")
    df["total_neto_clp"] = pd.to_numeric(df["total_neto_clp"], errors="coerce")

    df["total_venta_clp"] = df["total_bruto_clp"]
    return df

def _build_canonical_sales_view(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla angosta para BI/Dashboard/Storytelling (multicanal).
    Incluye extras de envíos reales cuando existan.
    """
    cols = [
        "fecha_venta",
        "canal_detalle",
        "venta_id",
        "producto_nombre",
        "cantidad_unificada",
        "precio_unitario_unificado",
        "total_bruto_clp",
        "total_neto_clp",
        "total_venta_clp",
        "comision_clp",
        "costo_envio_clp",
        "impuestos_clp",
        "descuento_clp",
        "cliente_nombre",
        "ciudad_envio",
        "comuna_envio",
        "region_envio",
        "direccion_envio",
        "codigo_postal",
        "estado_envio",
        "transportista",
        "tracking",
        "__source_file",
        "canal",
    ]
    existing = [c for c in cols if c in df.columns]
    out = df[existing].copy()

    if "fecha_venta" in out.columns:
        out["fecha_venta"] = pd.to_datetime(out["fecha_venta"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")

    return out

# ============================================================
#  FASE 1: INGESTA, PERFILADO Y LIMPIEZA
# ============================================================

def run_ingestion_phase(proc_id: str) -> None:
    append_history(proc_id, {"type": "phase_1_started"})
    status = read_status(proc_id) or {"id": proc_id}
    status.setdefault("metrics", {})
    status.setdefault("artifacts", {})
    _ensure_steps(status)

    status["status"] = "running"
    status["progress"] = 10
    _write(proc_id, status)

    try:
        artifacts = RUNS_DIR / proc_id / "artifacts"
        input_dir = RUNS_DIR / proc_id / "input"
        artifacts.mkdir(parents=True, exist_ok=True)
        input_dir.mkdir(parents=True, exist_ok=True)

        mode = status.get("mode") or "single"

        with _stage(proc_id, "Ingesta"):
            if mode == "multi":
                df_raw_all = _merge_multichannel_files(input_dir)

                # debug raw
                try:
                    orig_raw = artifacts / "dataset_original_raw_multicanal.csv"
                    df_raw_all.to_csv(orig_raw, index=False, encoding="utf-8")
                    status["artifacts"]["dataset_original_raw_multicanal.csv"] = _rel_to_base(orig_raw)
                except Exception as e:
                    print(f"⚠️ Error guardando dataset_original_raw_multicanal: {e}")

                # ZIP originales
                try:
                    zip_path = artifacts / "input_original_multicanal.zip"
                    with ZipFile(zip_path, "w") as z:
                        for p in sorted(input_dir.iterdir()):
                            if p.is_file():
                                z.write(p, p.name)
                    status["artifacts"]["input_original"] = _rel_to_base(zip_path)
                except Exception as e:
                    print(f"⚠️ Error generando ZIP de originales multicanal: {e}")

                # ✅ UNIR ML Envíos -> ML Ventas y eliminar filas envíos
                attach = _attach_ml_envios_to_ml_ventas(df_raw_all)
                df_raw = attach["df"]
                status["metrics"]["ml_envios_merge"] = attach.get("stats", {})

                # dataset_original.csv ya sin filas envíos
                try:
                    orig_csv = artifacts / "dataset_original.csv"
                    df_raw.to_csv(orig_csv, index=False, encoding="utf-8")
                    status["artifacts"]["dataset_original.csv"] = _rel_to_base(orig_csv)
                except Exception as e:
                    print(f"⚠️ Error guardando dataset_original multicanal: {e}")

                df = df_raw

            else:
                uploaded = input_dir / status["filename"]
                df = read_dataframe(uploaded)

                try:
                    orig_csv = artifacts / "dataset_original.csv"
                    df.to_csv(orig_csv, index=False, encoding="utf-8")
                    status["artifacts"]["dataset_original.csv"] = _rel_to_base(orig_csv)
                except Exception:
                    pass

                try:
                    orig_copy = artifacts / f"input_original{uploaded.suffix.lower()}"
                    if not orig_copy.exists():
                        shutil.copy2(uploaded, orig_copy)
                    status["artifacts"]["input_original"] = _rel_to_base(orig_copy)
                except Exception:
                    pass

            status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})
            status["progress"] = 20
            _write(proc_id, status)

        with _stage(proc_id, "Fechas"):
            inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)

        with _stage(proc_id, "InferenciaTipos"):
            semantic_schema = infer_semantics(df)
            roles = semantic_schema.roles

            for col in inferred_dates.keys():
                roles[col] = "fecha"

            status["metrics"]["inferred_types"] = roles
            status["progress"] = 30
            _write(proc_id, status)

        with _stage(proc_id, "Perfilado"):
            try:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR, roles=roles)
            except TypeError:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR)

            if profile_path:
                status["artifacts"]["reporte_perfilado.html"] = _rel_to_base(profile_path)

                if PROFILE_EXTRAS:
                    try:
                        p_csv = artifacts / "reporte_perfilado.csv"
                        p_pdf = artifacts / "reporte_perfilado.pdf"
                        build_profile_csv_from_html(profile_path, p_csv)
                        build_profile_pdf_from_html(profile_path, p_pdf)
                        status["artifacts"]["reporte_perfilado.csv"] = _rel_to_base(p_csv)
                        status["artifacts"]["reporte_perfilado.pdf"] = _rel_to_base(p_pdf)
                    except Exception as e:
                        print(f"⚠️ Error generando CSV/PDF perfilado: {e}")

            _mark_step(status, "Perfilado", "ok")
            status["progress"] = 50
            _write(proc_id, status)

        status["current_step"] = "Limpieza"
        _write(proc_id, status)

        with _stage(proc_id, "Limpieza"):
            rules = load_rules_for_process(proc_id)
            df_clean, clean_summary = clean_dataframe(df, rules=rules)

            out_summary = {}
            with _stage(proc_id, "Outliers"):
                df_clean, out_summary = apply_isolation_forest(
                    df_clean,
                    contamination=OUTLIER_CONTAMINATION,
                    random_state=OUTLIER_RANDOM_STATE,
                )

            if isinstance(clean_summary, dict):
                tmp = dict(clean_summary)
                tmp["outliers"] = out_summary
                clean_summary = tmp

            if mode == "multi":
                try:
                    df_clean = _harmonize_multichannel_postclean(df_clean)
                except Exception as e:
                    print(f"⚠️ Error armonizando dataset multicanal (post-clean): {e}")

            cleaned_csv = artifacts / "dataset_limpio.csv"
            df_clean.to_csv(cleaned_csv, index=False, encoding="utf-8")
            status["artifacts"]["dataset_limpio.csv"] = _rel_to_base(cleaned_csv)

            if mode == "multi":
                try:
                    df_unificado = _build_canonical_sales_view(df_clean)
                    unif_path = artifacts / "dataset_unificado.csv"
                    df_unificado.to_csv(unif_path, index=False, encoding="utf-8")
                    status["artifacts"]["dataset_unificado.csv"] = _rel_to_base(unif_path)
                    status["metrics"]["rows_unificado"] = int(df_unificado.shape[0])
                    status["metrics"]["cols_unificado"] = int(df_unificado.shape[1])
                except Exception as e:
                    print(f"⚠️ Error creando dataset_unificado.csv: {e}")

            out_summary = out_summary or {}
            status["metrics"].update(
                {
                    "rows_clean": int(df_clean.shape[0]),
                    "cols_clean": int(df_clean.shape[1]),
                    "clean_summary": clean_summary,
                    "outliers_count": _safe_int(out_summary.get("outliers", 0), default=0),
                    "outliers_ratio": _safe_float(out_summary.get("ratio", 0.0), default=0.0),
                    "outliers_used_columns": out_summary.get("used_columns", []) or [],
                    "outliers_contamination": _safe_float(out_summary.get("contamination", 0.0), default=0.0),
                }
            )

            _mark_step(status, "Limpieza", "ok")
            status["progress"] = 60
            status["status"] = "waiting_dashboard"
            status["current_step"] = "Listo para Dashboard"
            _write(proc_id, status)
            append_history(proc_id, {"type": "phase_1_completed"})

    except Exception as e:
        _handle_error(proc_id, status, e)

# ============================================================
#  FASE 2: DASHBOARD Y REPORTE (On Demand)
# ============================================================

def run_dashboard_phase(proc_id: str) -> None:
    append_history(proc_id, {"type": "phase_2_started"})
    status = read_status(proc_id) or {"id": proc_id}
    status.setdefault("metrics", {})
    status.setdefault("artifacts", {})
    _ensure_steps(status)

    status["status"] = "running"
    status["current_step"] = "Dashboard"
    status["progress"] = 70
    _write(proc_id, status)

    try:
        artifacts = RUNS_DIR / proc_id / "artifacts"

        unified_path = artifacts / "dataset_unificado.csv"
        clean_path = artifacts / "dataset_limpio.csv"

        if unified_path.exists():
            df_dash = pd.read_csv(unified_path)
            csv_name_for_dash = "dataset_unificado.csv"
            csv_path_for_links = unified_path
        else:
            if not clean_path.exists():
                raise FileNotFoundError("No existe CSV limpio. Ejecuta fase 1.")
            df_dash = pd.read_csv(clean_path)
            csv_name_for_dash = "dataset_limpio.csv"
            csv_path_for_links = clean_path

        roles = status["metrics"].get("inferred_types", {}) or {}

        # reforzamos roles clave en el dashboard
        if "fecha_venta" in df_dash.columns:
            roles["fecha_venta"] = "fecha"
        if "venta_id" in df_dash.columns:
            roles["venta_id"] = "id"

        # ✅ forzamos métrica principal (evita que el autospec elija precio_unitario_unificado)
        primary_metric = _pick_primary_metric(df_dash)
        status["metrics"]["dashboard_primary_metric"] = primary_metric
        
        if primary_metric in df_dash.columns:
            df_dash[primary_metric] = pd.to_numeric(df_dash[primary_metric], errors="coerce")
        if "precio_unitario_unificado" in df_dash.columns:
            df_dash["precio_unitario_unificado"] = pd.to_numeric(df_dash["precio_unitario_unificado"], errors="coerce")
        if "cantidad_unificada" in df_dash.columns:
            df_dash["cantidad_unificada"] = pd.to_numeric(df_dash["cantidad_unificada"], errors="coerce")

        if primary_metric in df_dash.columns:
            roles[primary_metric] = "monto"
        if "precio_unitario_unificado" in df_dash.columns:
            roles["precio_unitario_unificado"] = "precio_unitario"
        if "cantidad_unificada" in df_dash.columns:
            roles["cantidad_unificada"] = "cantidad"

        with _stage(proc_id, "Dashboard"):
            spec = auto_dashboard_spec(
                df_dash,
                roles=roles,
                source_name=status.get("filename"),
                process_id=proc_id,
            )

            # ✅ parche final: reemplaza cualquier uso de precio_unitario_unificado en spec
            spec = _force_primary_metric_in_spec(spec, primary_metric)

            auto_spec_path = artifacts / "auto_dashboard_spec.json"
            auto_spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            status["artifacts"]["auto_dashboard_spec.json"] = _rel_to_base(auto_spec_path)

            if build_narrative_report:
                try:
                    narrative_path = build_narrative_report(df_dash, spec, artifacts)
                    status["artifacts"]["reporte_narrativo.html"] = _rel_to_base(narrative_path)
                except Exception as e:
                    print(f"[Warning] Falló el reporte narrativo: {e}")
                    append_history(proc_id, {"type": "warning", "message": f"Storytelling fallido: {str(e)}"})

            dash_path = generate_dashboard_html(
                df_dash,
                artifacts,
                csv_rel_name=csv_name_for_dash,
                auto_spec=spec,
            )
            status["artifacts"]["dashboard.html"] = _rel_to_base(dash_path)

            _mark_step(status, "Dashboard", "ok")
            status["progress"] = 90
            _write(proc_id, status)

        status["current_step"] = "Reporte"
        _write(proc_id, status)

        with _stage(proc_id, "Reporte"):
            missing_overall = df_dash.isna().mean().mean() * 100.0
            missing_by_col = df_dash.isna().mean().mul(100).round(2).to_dict()

            quality = {
                "rows": int(df_dash.shape[0]),
                "cols": int(df_dash.shape[1]),
                "missing_overall_pct": _safe_float(missing_overall, 0.0),
                "missing_by_col_pct": missing_by_col,
            }

            links = {
                csv_name_for_dash: _rel_to_base(csv_path_for_links),
                "dashboard.html": _rel_to_base(dash_path),
                "reporte_perfilado.html": status["artifacts"].get("reporte_perfilado.html", ""),
                "reporte_narrativo.html": status["artifacts"].get("reporte_narrativo.html", ""),
                "dataset_original.csv": status["artifacts"].get("dataset_original.csv", ""),
                "input_original": status["artifacts"].get("input_original", ""),
            }

            report_html_path = artifacts / "detalle_limpieza.html"
            clean_summary = status["metrics"].get("clean_summary", {}) or {}
            build_full_report(clean_summary, quality, links, report_html_path)

            status["artifacts"]["detalle_limpieza.html"] = _rel_to_base(report_html_path)
            status["artifacts"]["reporte_integrado.html"] = _rel_to_base(report_html_path)

            report_pdf_path = artifacts / "detalle_limpieza.pdf"
            pdf_ok = False
            try:
                build_profile_pdf_from_html(report_html_path, report_pdf_path)
                if report_pdf_path.exists():
                    pdf_ok = True
                    status["artifacts"]["detalle_limpieza.pdf"] = _rel_to_base(report_pdf_path)
                    status["artifacts"]["reporte_integrado.pdf"] = _rel_to_base(report_pdf_path)
            except Exception as e:
                print(f"⚠️ Error generando PDF detalle_limpieza: {e}")

            try:
                zip_path = artifacts / "detalle_limpieza.zip"
                with ZipFile(zip_path, "w") as z:
                    if csv_path_for_links.exists():
                        z.write(csv_path_for_links, csv_name_for_dash)

                    if unified_path.exists() and csv_name_for_dash != "dataset_unificado.csv":
                        z.write(unified_path, "dataset_unificado.csv")

                    if clean_path.exists() and csv_name_for_dash != "dataset_limpio.csv":
                        z.write(clean_path, "dataset_limpio.csv")

                    input_rel = status["artifacts"].get("input_original")
                    if input_rel:
                        input_abs = (Path(BASE_DIR) / input_rel).resolve()
                        if input_abs.exists():
                            z.write(input_abs, input_abs.name)

                    raw_rel = status["artifacts"].get("dataset_original_raw_multicanal.csv")
                    if raw_rel:
                        raw_abs = (Path(BASE_DIR) / raw_rel).resolve()
                        if raw_abs.exists():
                            z.write(raw_abs, raw_abs.name)

                    if report_html_path.exists():
                        z.write(report_html_path, "detalle_limpieza.html")

                    if pdf_ok and report_pdf_path.exists():
                        z.write(report_pdf_path, "detalle_limpieza.pdf")

                status["artifacts"]["detalle_limpieza.zip"] = _rel_to_base(zip_path)
            except Exception as e:
                print(f"⚠️ Error creando ZIP detalle_limpieza: {e}")

            _mark_step(status, "Reporte", "ok")

        status["status"] = "completed"
        status["current_step"] = "Finalizado"
        status["progress"] = 100
        _write(proc_id, status)
        append_history(proc_id, {"type": "process_completed", "status": "completed"})

    except Exception as e:
        _handle_error(proc_id, status, e)

# Alias para compatibilidad
process_pipeline = run_ingestion_phase
