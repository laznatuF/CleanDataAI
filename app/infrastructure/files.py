# app/infrastructure/files.py
from __future__ import annotations

import os
import json
from pathlib import Path
from fastapi import UploadFile, HTTPException

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
        raise HTTPException(status_code=415, detail="Formato no soportado. Usa CSV, XLSX, XLS u ODS.")

    max_bytes = int(float(MAX_FILE_SIZE_MB) * 1024 * 1024)
    size = _get_size_bytes(file)
    if size > max_bytes:
        mb = round(size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande ({mb} MB). Límite permitido: {int(MAX_FILE_SIZE_MB)} MB."
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
                        detail=f"Archivo supera el límite permitido de {int(MAX_FILE_SIZE_MB)} MB."
                    )
                out.write(chunk)
        tmp.replace(target)
    except HTTPException:
        if tmp.exists():
            try: tmp.unlink()
            except Exception: pass
        raise
    except Exception as e:
        if tmp.exists():
            try: tmp.unlink()
            except Exception: pass
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {e!s}")

    return target


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
