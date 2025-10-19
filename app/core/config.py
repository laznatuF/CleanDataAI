from pathlib import Path
import os
import secrets

# Raíz del repositorio
BASE_DIR = Path(__file__).resolve().parents[2]

# Directorios de datos/ejecuciones
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "CleanDataAI"

# Frontend permitido (para CORS con cookies)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# Formatos permitidos para uploads
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}

# Límite de tamaño (MB) para uploads (se puede sobrescribir por env)
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "20"))

# ---------- Auth / JWT ----------
# ¡Cámbialo en producción!
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Nombre del cookie HttpOnly donde viaja el access token
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "cleandataai_access")

# TTL del access token en minutos
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "60"))

# Límite “gratuito” sin autenticación (ejecuciones)
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "7"))
