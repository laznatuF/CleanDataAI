from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from app.infrastructure.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
)

from app.infrastructure.process_repo_fs import read_status, write_status
from app.infrastructure.datasources import read_dataframe
from app.infrastructure.profiling import generate_profile_html
from app.application.dates import normalize_dates_in_df, parse_dates_series
from app.core.config import RUNS_DIR, BASE_DIR, TEMPLATES_DIR

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


# ---------- Inferencia básica de tipos (RFN20) ----------
def infer_column_type(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    if s.empty:
        return "texto"
    # bool
    if s.str.lower().isin({"0", "1", "true", "false", "sí", "si", "no"}).all():
        return "bool"
    # moneda (símbolos o prefijo tipo CLP 1000)
    if s.str.contains(r"[$€£]|^\s*[A-Z]{2,3}\s*\d", regex=True).mean() > 0.5:
        return "moneda"
    # fecha usando helper sin warnings
    dt = parse_dates_series(s)
    if dt.notna().mean() > 0.8:
        return "fecha"
    # numérico (limpiando miles/comas)
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
    Estructura runs/{id}/ con artifacts/ y input/.
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

    return {"id": proc_dir.name, "uploaded_path": str(uploaded_path)}


def process_pipeline(proc_id: str) -> None:
    """
    Procesa en background: queued → running → completed/failed.
    Genera el artefacto 'reporte_perfilado.html' y actualiza status.json.
    """
    try:
        # Cargar estado
        status = read_status(proc_id)

        # Running
        status["status"] = "running"
        status["current_step"] = "Perfilado"
        status["progress"] = 10
        _write(proc_id, status)

        # 1) Ingesta
        uploaded = RUNS_DIR / proc_id / "input" / status["filename"]
        df = read_dataframe(uploaded)
        status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})
        status["progress"] = 30
        _write(proc_id, status)

        # 2) Normalización de fechas + detección (RFN15)
        inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)

        # 3) Inferencia de tipos (RFN20)
        roles = infer_types(df)
        for col in inferred_dates.keys():
            roles[col] = "fecha"  # aseguramos rol 'fecha' en normalizadas

        status["metrics"]["inferred_types"] = roles
        status["progress"] = 45
        _write(proc_id, status)

        # 4) Perfilado → HTML (usa TEMPLATES_DIR dentro de /app)
        artifacts = RUNS_DIR / proc_id / "artifacts"
        try:
            profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR, roles=roles)
        except TypeError:
            # Compatibilidad por si tu función no acepta roles aún
            profile_path = generate_profile_html(df, artifacts, TEMPLATES_DIR)

        status["artifacts"]["reporte_perfilado.html"] = str(
            profile_path.relative_to(BASE_DIR)
        )

        # Marcar etapa Perfilado como OK
        for s in status["steps"]:
            if s["name"] == "Perfilado":
                s["status"] = "ok"

        # 5) Finalizar
        status["current_step"] = "Reporte"
        status["status"] = "completed"
        status["progress"] = 100
        _write(proc_id, status)

    except Exception as e:
        # Falla controlada
        fail = {
            "id": proc_id,
            "status": "failed",
            "progress": status.get("progress", 0) if "status" in locals() else 0,
            "error": str(e),
            "updated_at": now_iso(),
        }
        write_status(proc_id, fail)

