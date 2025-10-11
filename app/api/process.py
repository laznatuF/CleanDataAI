# app/api/process.py
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.services.pipeline import create_initial_process, process_pipeline

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}

def _normalize_status(s: str | None) -> str:
    s = (s or "").strip().lower()
    if s in {"ok", "done", "success", "completed", "finished"}: return "ok"
    if s in {"running", "in_progress", "processing"}:          return "running"
    if s in {"failed", "error"}:                               return "failed"
    if s in {"queued", "pending"}:                             return "queued"
    return "pending" if not s else s

@router.post("/process")
def process_file(background: BackgroundTasks, file: UploadFile = File(...)):
    """
    Crea proceso (status: queued), guarda archivo y lanza el pipeline en background.
    Devuelve el identificador de proceso.
    """
    try:
        init = create_initial_process(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar el pipeline: {e!s}")

    process_id = init.get("id")
    if not process_id:
        raise HTTPException(status_code=500, detail="No se pudo generar process_id.")

    # Background (RFN2, RFN58)
    background.add_task(process_pipeline, process_id)

    return {"id": process_id, "process_id": process_id, "status": "queued"}
