from fastapi import APIRouter, UploadFile, File
from app.services.pipeline import run_pipeline

router = APIRouter()

@router.post("/process")
def process_file(file: UploadFile = File(...)):
    """
    - Recibe el archivo via multipart/form-data.
    - Llama al pipeline.
    - Devuelve id y estado inicial.
    """
    result = run_pipeline(file)
    return {"id": result["id"], "status": result["status"]}
