# app/api/process.py
from __future__ import annotations
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from app.infrastructure.process_repo_fs import read_status
from app.core.config import ALLOWED_EXTENSIONS
from app.application.pipeline import (
    create_initial_process,
    create_initial_process_multi,
    run_ingestion_phase,
    run_dashboard_phase,
)

router = APIRouter()


@router.post("/process", status_code=status.HTTP_201_CREATED)
def process_file(background: BackgroundTasks, file: UploadFile = File(...)):
    """
    [FASE 1] Sube archivo, perfila y limpia.
    Retorna status 'queued' -> luego pasará a 'waiting_dashboard'.
    NO genera dashboard en este paso para ser rápido.
    (MODO 1 ARCHIVO – se mantiene tal cual)
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No se recibió un archivo.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensión no permitida.")

    try:
        init = create_initial_process(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar: {e!s}")

    process_id = init.get("id")

    # Lanzamos solo la Fase 1 (Ingesta + Limpieza)
    background.add_task(run_ingestion_phase, process_id)

    return JSONResponse(
        content={"id": process_id, "status": "queued", "mode": "single"},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/process/multi", status_code=status.HTTP_201_CREATED)
def process_files_multi(
    background: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """
    [FASE 1 - MULTICANAL] Sube varios archivos (Shopify, ML, etc.),
    los unifica en un solo dataset y luego limpia/perfila.
    """
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No se recibieron archivos.")

    bad_ext: List[str] = []
    for f in files:
        if not f.filename:
            raise HTTPException(
                status_code=400, detail="Uno de los archivos no tiene nombre."
            )
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            bad_ext.append(f.filename)

    if bad_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no permitida en: {', '.join(bad_ext)}",
        )

    try:
        init = create_initial_process_multi(files)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al iniciar proceso multicanal: {e!s}",
        )

    process_id = init.get("id")

    # Fase 1 (Ingesta + Limpieza) en background, igual que el modo single
    background.add_task(run_ingestion_phase, process_id)

    return JSONResponse(
        content={"id": process_id, "status": "queued", "mode": "multi"},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/process/{process_id}/dashboard", status_code=status.HTTP_202_ACCEPTED)
def generate_dashboard(process_id: str, background: BackgroundTasks):
    """
    [FASE 2] Genera Dashboard y Reporte Final a demanda.
    Se llama cuando el usuario hace clic en el botón "Generar Dashboard".
    Funciona igual tanto para modo single como para modo multi.
    """
    if not process_id:
        raise HTTPException(status_code=400, detail="ID de proceso inválido.")

    background.add_task(run_dashboard_phase, process_id)

    return {"ok": True, "message": "Generación de dashboard iniciada."}


@router.get("/status/{process_id}", status_code=status.HTTP_200_OK)
def get_status(process_id: str):
    """
    Devuelve el estado actual de un proceso.
    Lo usa el frontend en getStatus(id) -> GET /api/status/{id}
    """
    try:
        status_data = read_status(process_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Proceso no encontrado")

    return status_data
