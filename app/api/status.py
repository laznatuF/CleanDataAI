# app/api/process.py
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from app.core.config import ALLOWED_EXTENSIONS
from app.application.pipeline import create_initial_process, run_ingestion_phase, run_dashboard_phase

router = APIRouter()

@router.post("/process", status_code=status.HTTP_201_CREATED)
def process_file(background: BackgroundTasks, file: UploadFile = File(...)):
    """
    [FASE 1] Sube archivo, perfila y limpia.
    Retorna status 'queued' -> luego pasará a 'waiting_dashboard'.
    NO genera dashboard en este paso para ser rápido.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No se recibió un archivo.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensión no permitida.")

    try:
        init = create_initial_process(file)
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar: {e!s}")

    process_id = init.get("id")
    
    # Lanzamos solo la Fase 1 (Ingesta + Limpieza)
    # Esto es lo que hace que sea "rápido" al principio, porque no calcula gráficos pesados.
    background.add_task(run_ingestion_phase, process_id)

    return JSONResponse(content={"id": process_id, "status": "queued"}, status_code=status.HTTP_201_CREATED)


@router.post("/process/{process_id}/dashboard", status_code=status.HTTP_202_ACCEPTED)
def generate_dashboard(process_id: str, background: BackgroundTasks):
    """
    [FASE 2] Genera Dashboard y Reporte Final a demanda.
    Se llama cuando el usuario hace clic en el botón "Generar Dashboard".
    """
    # Validamos que el ID no sea vacío, aunque el path param lo garantiza en gran medida
    if not process_id:
        raise HTTPException(status_code=400, detail="ID de proceso inválido.")

    # Lanzamos la Fase 2 (Dashboard + PDF)
    background.add_task(run_dashboard_phase, process_id)
    
    return {"ok": True, "message": "Generación de dashboard iniciada."}