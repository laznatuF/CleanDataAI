from __future__ import annotations
from fastapi import UploadFile
from app.utils.files import (
    validate_filename_and_size,
    create_process_dir,
    save_upload,
    write_json,
)
from app.services.ingestion import read_dataframe
from app.services.profiling import generate_profile_html
from app.core.config import BASE_DIR

def run_pipeline(file: UploadFile) -> dict:
    # 1) Validación de seguridad extensión + tamaño
    validate_filename_and_size(file)

    # 2) Carpeta del proceso (runs/{id}/artifacts)
    proc_dir = create_process_dir()
    artifacts = proc_dir / "artifacts"

    # 3) Guardar archivo original
    uploaded_path = save_upload(file, proc_dir)

    # 4) Estado inicial
    status = {
        "id": proc_dir.name,
        "filename": uploaded_path.name,
        "steps": ["upload"],
        "metrics": {},
        "artifacts": {},
        "status": "running",
    }
    write_json(proc_dir / "status.json", status)

    # 5) Ingesta -> DataFrame
    df = read_dataframe(uploaded_path)
    status["steps"].append("ingesta")
    status["metrics"].update({"rows": int(df.shape[0]), "cols": int(df.shape[1])})

    # 6) Perfilado -> HTML
    profile_path = generate_profile_html(df, artifacts, BASE_DIR / "templates")
    status["steps"].append("perfilado")
    status["artifacts"]["reporte_perfilado.html"] = str(profile_path.relative_to(BASE_DIR))

    # 7) Fin de mini-hito
    status["status"] = "completed"
    write_json(proc_dir / "status.json", status)
    return status

