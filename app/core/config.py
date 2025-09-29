from pathlib import Path
import os  

# Si static/, templates/ y runs/ están en la raíz del repo:
BASE_DIR = Path(__file__).resolve().parents[2]

RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "CleanDataAI"

# Formatos permitidos para los uploads
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}

# Límite de tamaño (MB) para archivos subidos. Se puede sobreescribir con env var.
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "15"))
