from __future__ import annotations
from pathlib import Path
from fastapi import UploadFile, HTTPException
import shutil
import uuid
import os
import json

from app.core.config import RUNS_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB

def validate_filename_and_size(file: UploadFile) -> None:
    """
    - Rechaza extensiones que no estén en ALLOWED_EXTENSIONS.
    - Rechaza archivos mayores a MAX_FILE_SIZE_MB (por seguridad demo).
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extensión no permitida: {ext}")

    # Calcula tamaño (UploadFile usa un stream; lo movemos al final y volvemos)
    pos = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(pos)
    if size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande para la demo.")

def create_process_dir() -> Path:
    """
    - Genera un UUID como id de proceso.
    - Crea runs/{id}/artifacts/
    """
    process_id = str(uuid.uuid4())
    proc_dir = RUNS_DIR / process_id
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    return proc_dir

def save_upload(file: UploadFile, dest_dir: Path) -> Path:
    """
    - Guarda el archivo subido en la carpeta del proceso.
    """
    out = dest_dir / file.filename
    file.file.seek(0)  # por si alguien leyó el stream antes
    with out.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return out

def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
