from pathlib import Path
import os
import secrets

# === Rutas base ===
# Raíz del repositorio (el directorio que contiene /app, /runs, /frontend, etc.)
BASE_DIR = Path(__file__).resolve().parents[2]

# Directorio de la app (donde viven /api, /application, /domain, /infrastructure, /templates, /static)
APP_DIR = BASE_DIR / "app"

# Datos y ejecuciones
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Directorios de assets de la app
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

APP_NAME = "CleanDataAI"

# === CORS / Frontend ===
# Dominios permitidos para el frontend (cookies HttpOnly)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# === Archivos / subidas ===
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}
# Límite de tamaño en MB (el backend valida y puede sobreescribirse por env)
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "20"))

# === Auth / JWT ===
# ¡Cámbialo en producción!
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Cookie HttpOnly donde viaja el access token
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "cleandataai_access")

# TTL del access token en minutos
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "60"))

# === Límite “gratuito” sin autenticación ===
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "7"))
