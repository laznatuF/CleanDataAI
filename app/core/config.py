from pathlib import Path
import os
import secrets

# === Rutas base ===
BASE_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BASE_DIR / "app"

# === Datos y ejecuciones (overridables por ENV)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = Path(os.getenv("RUNS_DIR", BASE_DIR / "runs"))
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# === Assets
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

APP_NAME = "CleanDataAI"

# === CORS / Frontend ===
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# === Archivos / subidas ===
ALLOWED_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".ods"})
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "20"))

# === Auth / Cookies ===
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "cleandataai_access")
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "60"))

# Flags para cookies
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"   # prod: 1
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")    # lax/none/strict

# === Límite “gratuito” sin autenticación ===
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "7"))
