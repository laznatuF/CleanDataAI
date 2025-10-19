# app/services/pipeline.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json

import pandas as pd

from app.utils.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
    write_json,
)
from app.services.ingestion import read_dataframe
from app.services.profiling import generate_profile_html
from app.core.config import BASE_DIR, RUNS_DIR
# ⬇️ Normalizador de fechas sin warnings y helper de inferencia
from app.services.dates import normalize_dates_in_df, parse_dates_series

# Modelo de etapas mostrado en el front
STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]


def now_iso() -> str:
    """UTC ISO 8601 con 'Z'."""
    return datetime.utcnow().isoformat() + "Z"


def _status_path(proc_id: str) -> Path:
    return RUNS_DIR / proc_id / "status.json"


def _write_status(proc_id: str, status: Dict[str, Any]) -> None:
    """Escribe status.json con updated_at y progress [0..100]."""
    status["updated_at"] = now_iso()
    try:
        p = int(status.get("progress", 0))
    except Exception:
        p = 0
    status["progress"] = max(0, min(100, p))
    write_json(_status_path(proc_id), status)


# ---------- INFERENCIA BÁSICA DE TIPOS (RFN20) ----------
def infer_column_type(series: pd.Series) -> str:
    """
    Heurística simple:
      - bool: {0,1,true,false,sí,si,no}
      - moneda: símbolos $€£ o prefijo de 2-3 letras + dígitos
      - fecha: usando parse_dates_series (sin warnings)
      - numérico: tras normalizar separadores
      - texto: fallback
    """
    s = series.dropna().astype(str).str.strip()
    if s.empty:
        return "texto"

    # bool
    if s.str.lower().isin({"0", "1", "true", "false", "sí", "si", "no"}).all():
        return "bool"

    # moneda (símbolos o patrón al inicio tipo CLP 1000)
    # (threshold >50% para considerarla moneda)
    if s.str.contains(r"[$€£]|^\s*[A-Z]{2,3}\s*\d", regex=True).mean() > 0.5:
        return "moneda"

    # fecha usando parse_dates_series (evita UserWarning)
    dt = parse_dates_series(s)
    if dt.notna().mean() > 0.8:
        return "fecha"

    # numérico (limpiando miles/punto decimal)
    sn = (
        s.str.replace(r"[.\s]", "", regex=True)  # quita puntos y espacios (miles)
         .str.replace(",", ".", regex=False)     # coma -> punto decimal
    )
    num = pd.to_numeric(sn, errors="coerce")
    if num.notna().mean() > 0.8:
        return "numérico"

    return "texto"


def infer_types(df: pd.DataFrame) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for c in df.columns:
        roles[c] = infer_column_type(df[c])
    return roles
# --------------------------------------------------------


def create_initial_process(file) -> Dict[str, Any]:
    """
    Crea proceso, valida/guarda archivo y deja status en 'queued' (RFN58).
    Estructura runs/{id}/ con artifacts/ y input/.
    """
    validate_filename_and_size(file)

    # runs/{id}
    proc_dir = create_process_dir()
    artifacts = proc_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Guardar input en runs/{id}/input/
    uploaded_path = save_upload(file, proc_dir)

    # Estado inicial
    status: Dict[str, Any] = {
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
    """
    Procesa en background: queued → running → completed/failed (RFN58).
    Genera el artefacto 'reporte_perfilado.html' y actualiza status.json.
    """
    try:
        # Cargar status inicial
        with open(_status_path(proc_id), "r", encoding="utf-8") as f:
            status = json.load(f)

        # Running
        status["status"] = "running"
        status["current_step"] = "Perfilado"
        status["progress"] = 10
        _write_status(proc_id, status)

        # 1) Ingesta
        uploaded = Path(BASE_DIR) / "runs" / proc_id / "input" / status["filename"]
        df = read_dataframe(uploaded)
        status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})
        status["progress"] = 30
        _write_status(proc_id, status)

        # 2) Normalización de fechas (ISO 8601) sin warnings (RFN15)
        #    Detecta columnas "fecha" por porcentaje de parseo y normaliza a 'YYYY-MM-DD'
        inferred_dates = normalize_dates_in_df(df, min_success_ratio=0.5)  # {"col": "date"}
        # 3) Inferencia de tipos (RFN20) tras normalizar fechas
        roles = infer_types(df)
        # Integra las columnas normalizadas como 'fecha' en el idioma del rol
        for col in inferred_dates.keys():
            roles[col] = "fecha"

        # Persistimos inferencias
        status["metrics"]["inferred_types"] = roles
        status["progress"] = 45
        _write_status(proc_id, status)

        # 4) Perfilado → HTML (RFN21)
        artifacts = Path(BASE_DIR) / "runs" / proc_id / "artifacts"
        profile_path = generate_profile_html(df, artifacts, Path(BASE_DIR) / "templates")

        # Registrar artefacto relativo a BASE_DIR
        status["artifacts"]["reporte_perfilado.html"] = str(profile_path.relative_to(BASE_DIR))

        # Marcar etapa Perfilado como ok
        for s in status["steps"]:
            if s["name"] == "Perfilado":
                s["status"] = "ok"

        # 5) Finalizar mini-hito
        status["current_step"] = "Reporte"
        status["status"] = "completed"   # alias aceptado por tus tests
        status["progress"] = 100
        _write_status(proc_id, status)

    except Exception as e:
        # Falla controlada
        fail = {
            "id": proc_id,
            "status": "failed",
            "progress": status.get("progress", 0) if "status" in locals() else 0,
            "error": str(e),
            "updated_at": now_iso(),
        }
        write_json(_status_path(proc_id), fail)
