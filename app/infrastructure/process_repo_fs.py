# app/infrastructure/process_repo_fs.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import math

import numpy as np
import pandas as pd

from app.core.config import RUNS_DIR
from app.infrastructure.files import read_json


def status_path(proc_id: str) -> Path:
    """Ruta al status.json de un proceso."""
    return RUNS_DIR / proc_id / "status.json"


def read_status(proc_id: str) -> Dict[str, Any]:
    """
    Lee el estado del proceso desde disco.
    Devuelve {} si no existe (robusto para llamadas tempranas).
    """
    return read_json(status_path(proc_id)) or {}


def _json_default(obj):
    """
    Conversor seguro para json.dump:
    - Convierte NaT / NA de pandas a None
    - Convierte tipos de numpy a tipos nativos
    - Convierte Timestamps / datetimes a ISO
    - Hace fallback a str() si no sabe qué hacer
    """
    # None explícito
    if obj is None:
        return None

    # Pandas missing values (NaT, NA de columnas nullable)
    try:
        from pandas._libs.tslibs.nattype import NaTType
        from pandas._libs.missing import NAType

        if obj is pd.NaT or isinstance(obj, (NaTType, NAType)):
            return None
    except Exception:
        # Si fallan los imports internos, seguimos con el resto
        pass

    # Números numpy
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    # Booleanos numpy
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)

    # Arrays / listas / sets
    if isinstance(obj, (np.ndarray, list, tuple, set)):
        return list(obj)

    # Rutas -> string
    if isinstance(obj, Path):
        return str(obj)

    # Datetimes / Timestamp -> ISO
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass

    # Último recurso
    return str(obj)


def write_status(proc_id: str, data: Dict[str, Any]) -> None:
    """
    Persiste el estado usando escritura atómica (.tmp + replace),
    serializando de forma segura NaT, numpy, etc.
    """
    path = status_path(proc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_json_default)

    tmp.replace(path)

