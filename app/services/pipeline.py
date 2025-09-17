from __future__ import annotations
from fastapi import UploadFile
from app.utils.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
    write_json,
)

def run_pipeline(file: UploadFile) -> dict:
    # 1) Validación de seguridad (extensión + tamaño)
    validate_filename_and_size(file)

    # 2) Carpeta del proceso (runs/{id}/artifacts)
    proc_dir = create_process_dir()
    artifacts = proc_dir / "artifacts"  # reservado para reportes u otros outputs

    # 3) Guardar archivo original
    uploaded_path = save_upload(file, proc_dir)

    # 4) Estado mínimo (guardado en runs/{id}/status.json)
    status = {
        "id": proc_dir.name,
        "filename": uploaded_path.name,
        "steps": ["upload"],   # iremos agregando pasos aquí (perfilado, etc.)
        "metrics": {},         # se llenará más adelante
        "artifacts": {},       # rutas a reportes/CSV limpios, etc.
        "status": "uploaded",
    }
    write_json(proc_dir / "status.json", status)
    return status
