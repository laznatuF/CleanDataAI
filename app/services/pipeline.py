# app/services/pipeline.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import pandas as pd

from app.utils.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
    write_json,
)
from app.services.ingestion import read_dataframe
from app.services.profiling import generate_profile_html
from app.core.config import BASE_DIR

STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _status_path(proc_id: str) -> Path:
    from app.core.config import RUNS_DIR
    return RUNS_DIR / proc_id / "status.json"

def _write_status(proc_id: str, status: Dict[str, Any]) -> None:
    status["updated_at"] = now_iso()
    try:
        p = int(status.get("progress", 0))
    except Exception:
        p = 0
    status["progress"] = max(0, min(100, p))
    write_json(_status_path(proc_id), status)

# ---------- INFERENCIA BÁSICA DE TIPOS (RFN20) ----------
def infer_column_type(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    if s.empty:
        return "texto"

    # bool
    if s.str.lower().isin({"0","1","true","false","sí","si","no"}).all():
        return "bool"

    # moneda (símbolos o patrón numérico con separadores)
    if s.str.contains(r"[$€£]|^\s*[A-Z]{2,3}\s*\d", regex=True).mean() > 0.5:
        return "moneda"

    # fecha
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True, utc=False)
    if dt.notna().mean() > 0.8:
        return "fecha"

    # numérico (limpiando miles/punto decimal)
    sn = s.str.replace(r"[.\s]", "", regex=True).str.replace(",", ".", regex=False)
    num = pd.to_numeric(sn, errors="coerce")
    if num.notna().mean() > 0.8:
        return "numérico"

    return "texto"

def infer_types(df: pd.DataFrame) -> Dict[str, str]:
    roles = {}
    for c in df.columns:
        roles[c] = infer_column_type(df[c])
    return roles
# --------------------------------------------------------

def create_initial_process(file) -> Dict[str, Any]:
    """Crea proceso, valida/guarda archivo y deja status en 'queued'."""
    validate_filename_and_size(file)
    proc_dir = create_process_dir()
    artifacts = proc_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    uploaded_path = save_upload(file, proc_dir)

    status = {
        "id": proc_dir.name,
        "filename": uploaded_path.name,
        "status": "queued",                 # RFN58
        "progress": 0,
        "current_step": "Subir archivo",
        "steps": [
            {"name": "Subir archivo", "status": "ok"},
            {"name": "Perfilado",     "status": "pending"},
            {"name": "Limpieza",      "status": "pending"},
            {"name": "Dashboard",     "status": "pending"},
            {"name": "Reporte",       "status": "pending"},
        ],
        "metrics": {},
        "artifacts": {},
    }
    _write_status(proc_dir.name, status)
    return {"id": proc_dir.name, "uploaded_path": str(uploaded_path)}

def process_pipeline(proc_id: str) -> None:
    """Procesa en background: running → ok/failed (RFN2, RFN58)."""
    try:
        # loading status
        path = _status_path(proc_id)
        import json
        with open(path, "r", encoding="utf-8") as f:
            status = json.load(f)

        status["status"] = "running"
        status["current_step"] = "Perfilado"
        status["progress"] = 15
        _write_status(proc_id, status)

        # 1) Ingesta
        uploaded = Path(BASE_DIR) / "runs" / proc_id / "input" / status["filename"]
        df = read_dataframe(uploaded)
        status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})

        # Inferencia de tipos (RFN20)
        roles = infer_types(df)
        status["metrics"]["inferred_types"] = roles
        status["progress"] = 35
        _write_status(proc_id, status)

        # 2) Perfilado
        artifacts = Path(BASE_DIR) / "runs" / proc_id / "artifacts"
        profile_path = generate_profile_html(df, artifacts, Path(BASE_DIR) / "templates")
        status["artifacts"]["reporte_perfilado.html"] = str(profile_path.relative_to(BASE_DIR))

        for s in status["steps"]:
            if s["name"] == "Perfilado":
                s["status"] = "ok"

        status["current_step"] = "Reporte"
        status["status"] = "ok"
        status["progress"] = 100
        _write_status(proc_id, status)

    except Exception as e:
        status = {
            "id": proc_id,
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }
        _write_status(proc_id, status)
