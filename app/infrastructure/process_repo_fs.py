from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from app.core.config import RUNS_DIR
from app.infrastructure.files import read_json, write_json


def status_path(proc_id: str) -> Path:
    """Ruta al status.json de un proceso."""
    return RUNS_DIR / proc_id / "status.json"


def read_status(proc_id: str) -> Dict[str, Any]:
    """
    Lee el estado del proceso desde disco.
    Devuelve {} si no existe (robusto para llamadas tempranas).
    """
    return read_json(status_path(proc_id)) or {}


def write_status(proc_id: str, data: Dict[str, Any]) -> None:
    """
    Persiste el estado usando escritura atómica (.tmp + replace).
    """
    write_json(status_path(proc_id), data)
