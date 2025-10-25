# app/api/process.py
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from app.core.config import ALLOWED_EXTENSIONS
from app.application.pipeline import create_initial_process, process_pipeline

router = APIRouter()

@router.post("/process", status_code=status.HTTP_201_CREATED)
def process_file(background: BackgroundTasks, file: UploadFile = File(...)):
    """
    Crea un proceso (status: queued), guarda el archivo y lanza el pipeline en background.
    Devuelve el identificador del proceso con HTTP 201 Created.
    """
    # 1) Validaciones básicas del upload
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No se recibió un archivo.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensión no permitida.")

    # 2) Crear el proceso y materializar entrada
    try:
        init = create_initial_process(file)
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

    # 4) Respuesta explícita 201 (evita que algún middleware responda 200)
    payload = {"id": process_id, "process_id": process_id, "status": "queued"}
    return JSONResponse(content=payload, status_code=status.HTTP_201_CREATED)

