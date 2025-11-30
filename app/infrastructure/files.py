# app/infrastructure/files.py
from __future__ import annotations

import os
import json
import math
from pathlib import Path
from typing import Any

from fastapi import UploadFile, HTTPException

import numpy as np
import pandas as pd

from app.core.config import RUNS_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB

CHUNK_SIZE = 1024 * 1024  # 1 MB


def _sanitize_filename(name: str) -> str:
    return Path(name or "input.bin").name


def _get_size_bytes(file: UploadFile) -> int:
    f = file.file
    cur = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(cur, os.SEEK_SET)
    return size


def validate_filename_and_size(file: UploadFile) -> None:
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="No se recibió un archivo.")

    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Formato no soportado. Usa CSV, XLSX, XLS u ODS.",
        )

    max_bytes = int(float(MAX_FILE_SIZE_MB) * 1024 * 1024)
    size = _get_size_bytes(file)
    if size > max_bytes:
        mb = round(size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=413,
            detail=(
                f"Archivo demasiado grande ({mb} MB). "
                f"Límite permitido: {int(MAX_FILE_SIZE_MB)} MB."
            ),
        )


def create_process_dir(base: Path | None = None) -> Path:
    from uuid import uuid4

    root = base or RUNS_DIR
    proc_dir = root / str(uuid4())
    (proc_dir / "input").mkdir(parents=True, exist_ok=True)
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (proc_dir / "tmp").mkdir(parents=True, exist_ok=True)
    return proc_dir


def save_upload(file: UploadFile, proc_dir: Path) -> Path:
    validate_filename_and_size(file)

    safe_name = _sanitize_filename(file.filename)
    target = proc_dir / "input" / safe_name
    tmp = target.with_suffix(target.suffix + ".tmp")
    target.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = int(float(MAX_FILE_SIZE_MB) * 1024 * 1024)
    written = 0
    file.file.seek(0)

    try:
        with tmp.open("wb") as out:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Archivo supera el límite permitido "
                            f"de {int(MAX_FILE_SIZE_MB)} MB."
                        ),
                    )
                out.write(chunk)
        tmp.replace(target)
    except HTTPException:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        raise
    except Exception as e:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar el archivo: {e!s}",
        )

    return target


# ============================
# JSON seguro (NaT, NaN, etc.)
# ============================

def _json_default(obj: Any):
    """
    Conversor seguro para json.dump:
    - NaT / NA de pandas  -> None
    - numpy ints/floats   -> int/float nativos (NaN/inf -> None)
    - numpy bool_         -> bool
    - arrays / sets       -> list
    - Path                -> str
    - datetimes           -> ISO
    - resto               -> str(obj)
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
        pass

    # Números numpy
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    # Booleanos numpy y normales
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)

    # Arrays / listas / tuplas / sets
    if isinstance(obj, (np.ndarray, list, tuple, set)):
        return [_json_default(x) for x in obj]

    # Rutas
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


def write_json(path: Path, data: Any) -> None:
    """
    Escribe JSON usando escritura atómica (.tmp + replace) y conversión
    segura de tipos (evita float(NaTType)).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_json_default, indent=2)
    tmp.replace(path)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
