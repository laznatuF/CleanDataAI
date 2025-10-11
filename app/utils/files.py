# app/utils/files.py
from __future__ import annotations
import os
from pathlib import Path
from fastapi import UploadFile, HTTPException
from typing import Iterable

ALLOWED_EXT = {".csv", ".xlsx", ".xls", ".ods"}

def _ext_ok(filename: str, allowed: Iterable[str]) -> bool:
    return any(filename.lower().endswith(e) for e in allowed)

def _get_size_bytes(file: UploadFile) -> int:
    # SpooledTemporaryFile: medimos y rebobinamos
    f = file.file
    cur = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(cur, os.SEEK_SET)
    return size

def validate_filename_and_size(file: UploadFile) -> None:
    # Tamaño máximo configurable
    max_mb = float(os.getenv("MAX_FILE_SIZE_MB", "20"))
    max_bytes = int(max_mb * 1024 * 1024)

    name = (file.filename or "").strip()
    if not name or not _ext_ok(name, ALLOWED_EXT):
        raise HTTPException(status_code=415, detail="Formato no soportado. Usa CSV, XLSX, XLS u ODS.")

    size = _get_size_bytes(file)
    if size > max_bytes:
        mb = round(size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande ({mb} MB). Límite permitido: {int(max_mb)} MB."
        )

def create_process_dir(base: Path | None = None) -> Path:
    from uuid import uuid4
    from app.core.config import RUNS_DIR
    root = base or RUNS_DIR
    proc_dir = root / str(uuid4())
    (proc_dir / "input").mkdir(parents=True, exist_ok=True)
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (proc_dir / "tmp").mkdir(parents=True, exist_ok=True)
    return proc_dir

def save_upload(file: UploadFile, proc_dir: Path) -> Path:
    path = proc_dir / "input" / (file.filename or "input.bin")
    file.file.seek(0)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return path

def write_json(path: Path, data: dict) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_json(path: Path) -> dict:
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
