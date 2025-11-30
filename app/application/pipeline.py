# app/application/pipeline.py
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import shutil

import pandas as pd
import numpy as np
from os.path import relpath

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
from app.application.rules import load_rules_for_process, describe_rules
from app.application.pdf import build_pdf_from_template
from app.application.semantics import infer_semantics

# [CORREGIDO] Import desde report_narrative.py
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
#         Fallbacks / Config
# ============================================================

USE_AUTOSPEC_FALLBACK = False
STRICT_DASH_CHECK = os.getenv("STRICT_DASH_CHECK", "0") == "1"

try:
    if not USE_AUTOSPEC_FALLBACK:
        from app.application.autospec import auto_dashboard_spec
    else:
        raise ImportError()
except Exception:
    # Fallback silencioso si no se encuentra el módulo
    def auto_dashboard_spec(df, roles=None, source_name=None, process_id=None):
        # Fallback mínimo para no romper si falta autospec
        return {"charts": [], "source_name": source_name, "process_id": process_id}

# ============================================================
#  Helpers
# ============================================================

STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _safe_float(x: Any, default: float = 0.0) -> float:
    """
    Convierte a float sin explotar si x es NaT, None, NaN, etc.
    """
    try:
        if x is None:
            return default
        try:
            if pd.isna(x):
                return default
        except Exception:
            # pd.isna a veces devuelve array en tipos raros; lo ignoramos
            pass
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    """
    Convierte a int sin explotar si x es NaT, None, NaN, etc.
    """
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


def create_initial_process(file) -> Dict[str, Any]:
    validate_filename_and_size(file)
    proc_dir = create_process_dir()
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
    append_history(
        proc_dir.name,
        {"type": "process_created", "file": uploaded_path.name},
    )
    return {"id": proc_dir.name, "uploaded_path": str(uploaded_path)}


def _stage(proc_id: str, stage: str):
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


def _handle_error(proc_id, status, e):
    append_history(proc_id, {"type": "process_failed", "error": str(e)})
    if not status:
        status = {"id": proc_id}
    status["status"] = "failed"
    status["error"] = str(e)
    _write(proc_id, status)


# ============================================================
#  FASE 1: INGESTA, PERFILADO Y LIMPIEZA (Rápido)
# ============================================================

def run_ingestion_phase(proc_id: str) -> None:
    """
    Ejecuta hasta generar el CSV limpio y Perfilado.
    Al final, cambia el status a 'waiting_dashboard' y PAUSA.
    """
    append_history(proc_id, {"type": "phase_1_started"})
    status = read_status(proc_id)
    status["status"] = "running"
    status["progress"] = 10
    _write(proc_id, status)

    try:
        # Carpeta de artefactos (la usaremos desde el inicio)
        artifacts = RUNS_DIR / proc_id / "artifacts"

        # 1) Ingesta
        with _stage(proc_id, "Ingesta"):
            uploaded = RUNS_DIR / proc_id / "input" / status["filename"]
            df = read_dataframe(uploaded)

            # Métricas básicas
            status["metrics"].update(
                {"rows": int(df.shape[0]), "cols": int(df.shape[1])}
            )

            # Guardamos una copia del dataset original como CSV
            try:
                orig_csv = artifacts / "dataset_original.csv"
                df.to_csv(orig_csv, index=False, encoding="utf-8")
                status.setdefault("artifacts", {})
                status["artifacts"]["dataset_original.csv"] = _rel_to_base(orig_csv)
            except Exception:
                # si falla, no rompemos la ingesta
                pass

            # Copiamos el archivo bruto al directorio de artifacts
            try:
                orig_copy = artifacts / f"input_original{uploaded.suffix.lower()}"
                if not orig_copy.exists():
                    shutil.copy2(uploaded, orig_copy)
                status.setdefault("artifacts", {})
                status["artifacts"]["input_original"] = _rel_to_base(orig_copy)
            except Exception:
                pass

            status["progress"] = 20
            _write(proc_id, status)

        # 2) Normalización de fechas
        with _stage(proc_id, "Fechas"):
            inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)

        # 3) Inferencia de tipos (Semantics)
        with _stage(proc_id, "InferenciaTipos"):
            semantic_schema = infer_semantics(df)
            roles = semantic_schema.roles
            for col in inferred_dates.keys():
                roles[col] = "fecha"
            status["metrics"]["inferred_types"] = roles
            status["progress"] = 30
            _write(proc_id, status)

        # 4) Perfilado (HTML + PDF)
        with _stage(proc_id, "Perfilado"):
            try:
                profile_path = generate_profile_html(
                    df, artifacts, TEMPLATES_DIR, roles=roles
                )
            except TypeError:
                profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR)

            status["artifacts"]["reporte_perfilado.html"] = _rel_to_base(profile_path)

            try:
                p_csv = artifacts / "reporte_perfilado.csv"
                p_pdf = artifacts / "reporte_perfilado.pdf"
                build_profile_csv_from_html(profile_path, p_csv)
                build_profile_pdf_from_html(profile_path, p_pdf)
                status["artifacts"]["reporte_perfilado.csv"] = _rel_to_base(p_csv)
                status["artifacts"]["reporte_perfilado.pdf"] = _rel_to_base(p_pdf)
            except Exception:
                pass

            for s in status["steps"]:
                if s["name"] == "Perfilado":
                    s["status"] = "ok"
            status["progress"] = 50
            _write(proc_id, status)

        # 5) Limpieza y Outliers
        status["current_step"] = "Limpieza"
        _write(proc_id, status)

        with _stage(proc_id, "Limpieza"):
            rules = load_rules_for_process(proc_id)
            df_clean, clean_summary = clean_dataframe(df, rules=rules)

            # Outliers
            with _stage(proc_id, "Outliers"):
                df_clean, out_summary = apply_isolation_forest(
                    df_clean,
                    contamination=OUTLIER_CONTAMINATION,
                    random_state=OUTLIER_RANDOM_STATE,
                )

            # Incrustamos el resumen de outliers dentro de clean_summary
            if isinstance(clean_summary, dict):
                tmp = dict(clean_summary)
                tmp["outliers"] = out_summary
                clean_summary = tmp

            cleaned_csv = artifacts / "dataset_limpio.csv"
            df_clean.to_csv(cleaned_csv, index=False, encoding="utf-8")

            # --- Normalizamos valores del resumen de outliers SIN float()/int directos ---
            out_summary = out_summary or {}

            out_count = _safe_int(out_summary.get("outliers", 0), default=0)
            out_ratio = _safe_float(out_summary.get("ratio", 0.0), default=0.0)
            out_cont = _safe_float(out_summary.get("contamination", 0.0), default=0.0)
            used_cols = out_summary.get("used_columns", []) or []

            status["metrics"].update(
                {
                    "rows_clean": int(df_clean.shape[0]),
                    "cols_clean": int(df_clean.shape[1]),
                    "clean_summary": clean_summary,
                    "outliers_count": out_count,
                    "outliers_ratio": out_ratio,
                    "outliers_used_columns": used_cols,
                    "outliers_contamination": out_cont,
                }
            )
            status["artifacts"]["dataset_limpio.csv"] = _rel_to_base(cleaned_csv)

            for s in status["steps"]:
                if s["name"] == "Limpieza":
                    s["status"] = "ok"

            # Punto de corte
            status["progress"] = 60
            status["status"] = "waiting_dashboard"  # Estado clave para el frontend
            status["current_step"] = "Listo para Dashboard"
            _write(proc_id, status)
            append_history(proc_id, {"type": "phase_1_completed"})

    except Exception as e:
        _handle_error(proc_id, status, e)


# ============================================================
#  FASE 2: DASHBOARD Y REPORTE (Pesado - On Demand)
# ============================================================

def run_dashboard_phase(proc_id: str) -> None:
    """
    Se llama SOLO cuando el usuario aprieta el botón.
    Lee el CSV limpio y genera los gráficos.
    """
    append_history(proc_id, {"type": "phase_2_started"})
    status = read_status(proc_id)

    status["status"] = "running"
    status["current_step"] = "Dashboard"
    status["progress"] = 70
    _write(proc_id, status)

    try:
        artifacts = RUNS_DIR / proc_id / "artifacts"
        clean_path = artifacts / "dataset_limpio.csv"
        if not clean_path.exists():
            raise FileNotFoundError("No existe CSV limpio. Ejecuta fase 1.")

        # Cargar dataset
        df_clean = pd.read_csv(clean_path)
        # Recuperar roles inferidos anteriormente
        roles = status["metrics"].get("inferred_types", {}) or {}

        # 6) Dashboard (Inteligente con Autospec)
        with _stage(proc_id, "Dashboard"):
            spec = auto_dashboard_spec(
                df_clean,
                roles=roles,
                source_name=status.get("filename"),
                process_id=proc_id,
            )

            auto_spec_path = artifacts / "auto_dashboard_spec.json"
            auto_spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            status["artifacts"]["auto_dashboard_spec.json"] = _rel_to_base(
                auto_spec_path
            )

            # Reporte Narrativo
            if build_narrative_report:
                try:
                    narrative_path = build_narrative_report(
                        df_clean, spec, artifacts
                    )
                    status["artifacts"]["reporte_narrativo.html"] = _rel_to_base(
                        narrative_path
                    )
                except Exception as e:
                    # Si falla el storytelling, no rompemos el dashboard principal
                    print(f"[Warning] Falló el reporte narrativo: {e}")
                    append_history(
                        proc_id,
                        {
                            "type": "warning",
                            "message": f"Storytelling fallido: {str(e)}",
                        },
                    )
            else:
                # Mensaje de debug en caso de que la importación inicial haya fallado
                print(
                    "[Warning] build_narrative_report es None. Verifica la importación de report_narrative.py"
                )

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
            status["progress"] = 90
            _write(proc_id, status)

        # 7) Reporte Integrado
        status["current_step"] = "Reporte"
        _write(proc_id, status)
        with _stage(proc_id, "Reporte"):
            missing_overall = df_clean.isna().mean().mean() * 100.0
            missing_by_col = df_clean.isna().mean().mul(100).round(2).to_dict()

            quality = {
                "rows": int(df_clean.shape[0]),
                "cols": int(df_clean.shape[1]),
                "missing_overall_pct": _safe_float(missing_overall, 0.0),
                "missing_by_col_pct": missing_by_col,
            }

            links = {
                "dataset_limpio.csv": _rel_to_base(clean_path),
                "dashboard.html": _rel_to_base(dash_path),
                "reporte_perfilado.html": status["artifacts"].get(
                    "reporte_perfilado.html", ""
                ),
                "reporte_narrativo.html": status["artifacts"].get(
                    "reporte_narrativo.html", ""
                ),
                "dataset_original.csv": status["artifacts"].get(
                    "dataset_original.csv", ""
                ),
                "input_original": status["artifacts"].get(
                    "input_original", ""
                ),
            }

            report_path = artifacts / "reporte_integrado.html"
            clean_summary = status["metrics"].get("clean_summary", {}) or {}
            build_full_report(clean_summary, quality, links, report_path)
            status["artifacts"]["reporte_integrado.html"] = _rel_to_base(
                report_path
            )

            for s in status["steps"]:
                if s["name"] == "Reporte":
                    s["status"] = "ok"

            # PDF Opcional
            if os.getenv("GENERATE_PDF", "0") == "1":
                try:
                    pdf_path = artifacts / "reporte_integrado.pdf"
                    ctx = {
                        "title": "Reporte Final",
                        "generated_at": now_iso(),
                        "process_id": proc_id,
                        "clean_summary": clean_summary,
                        "quality": quality,
                        "links": links,
                        "outliers": {
                            "total": int(quality["rows"]),
                            "outliers": status["metrics"].get(
                                "outliers_count", 0
                            ),
                        },
                    }
                    build_pdf_from_template(
                        "report.j2.html", pdf_path, ctx
                    )
                    status["artifacts"]["reporte_integrado.pdf"] = _rel_to_base(
                        pdf_path
                    )
                except Exception:
                    pass

        # 8) Final
        status["status"] = "completed"
        status["current_step"] = "Finalizado"
        status["progress"] = 100
        _write(proc_id, status)
        append_history(
            proc_id, {"type": "process_completed", "status": "completed"}
        )

    except Exception as e:
        _handle_error(proc_id, status, e)


# Alias para compatibilidad si algo llama a process_pipeline
process_pipeline = run_ingestion_phase
