from fastapi import APIRouter, HTTPException
from app.core.config import RUNS_DIR
from app.utils.files import read_json

router = APIRouter()

@router.get("/status/{process_id}")
def get_status(process_id: str):
    """
    - Devuelve el estado guardado para ese proceso (si existe).
    """
    status_path = RUNS_DIR / process_id / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Proceso no encontrado")
    return read_json(status_path)
