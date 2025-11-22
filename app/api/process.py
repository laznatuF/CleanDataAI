# app/api/process.py
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from app.core.config import ALLOWED_EXTENSIONS
from app.application.pipeline import create_initial_process, process_pipeline

router = APIRouter()


@router.post("/process", status_code=status.HTTP_201_CREATED)
def process_file(
    background: BackgroundTasks,
    files: List[UploadFile] | None = File(
        default=None,
        description="Uno o más archivos (campo 'files')",
    ),
    file: UploadFile | None = File(
        default=None,
        description="Compatibilidad: un solo archivo (campo 'file')",
    ),
):
    """
    Crea un proceso (status: queued), guarda uno o varios archivos
    y lanza el pipeline en background.
    Devuelve el identificador del proceso con HTTP 201 Created.
    """
    real_files: List[UploadFile] = []
    if files:
        real_files.extend(files)
    if file is not None:
        real_files.append(file)

    if not real_files:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo.")

    # Validaciones básicas por archivo
    for f in real_files:
        if not f or not f.filename:
            raise HTTPException(status_code=400, detail="Archivo sin nombre.")
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Extensión no permitida en {f.filename}.",
            )

    # 2) Crear el proceso y materializar entradas
    try:
        init = create_initial_process(real_files)
    except HTTPException:
        # Errores de validación/negocio se propagan tal cual
        raise
    except Exception as e:
        # Error inesperado
        raise HTTPException(status_code=500, detail=f"Error al iniciar el pipeline: {e!s}")

    process_id = init.get("id")
    if not process_id:
        raise HTTPException(status_code=500, detail="No se pudo generar process_id.")

    # 3) Ejecutar pipeline en background
    background.add_task(process_pipeline, process_id)

    # 4) Respuesta explícita 201
    payload = {"id": process_id, "process_id": process_id, "status": "queued"}
    return JSONResponse(content=payload, status_code=status.HTTP_201_CREATED)
