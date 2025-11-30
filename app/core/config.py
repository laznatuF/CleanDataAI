# app/core/config.py
from __future__ import annotations

from pathlib import Path
import os
import secrets
from dotenv import load_dotenv  # <--- IMPORTANTE: Necesario para leer el .env

# ------------------------------
# Helpers
# ------------------------------
def _as_bool(val: str | int | None, default: bool = False) -> bool:
    """Convierte valores de env a bool de forma robusta."""
    if val is None:
        return default
    s = str(val).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


# ------------------------------
# Rutas base y Carga de Entorno
# ------------------------------
# Raíz del repo (contiene /app, /runs, /data, /frontend, etc.)
BASE_DIR: Path = Path(__file__).resolve().parents[2]

# Carga las variables del archivo .env que está en la raíz
# Si no haces esto, os.getenv no encontrará nada.
load_dotenv(BASE_DIR / ".env")

APP_DIR: Path = BASE_DIR / "app"

# ------------------------------
# Datos y ejecuciones (overridable por ENV)
# ------------------------------
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR: Path = Path(os.getenv("RUNS_DIR", str(BASE_DIR / "runs")))
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Assets
# ------------------------------
TEMPLATES_DIR: Path = APP_DIR / "templates"
STATIC_DIR: Path = APP_DIR / "static"

APP_NAME = "CleanDataAI"

# ------------------------------
# CORS / Frontend
# ------------------------------
# En dev solemos trabajar con Vite en 127.0.0.1:5173
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173").rstrip("/")

# ------------------------------
# Archivos / subidas
# ------------------------------
ALLOWED_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".ods"})
# Límite por defecto 20 MB (configurable por env)
MAX_FILE_SIZE_MB: float = float(os.getenv("MAX_FILE_SIZE_MB", "20"))

# ------------------------------
# Auth / Cookies
# ------------------------------
# ¡Cámbialo en producción!
SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Cookie HttpOnly que porta el access token
ACCESS_COOKIE_NAME: str = os.getenv("ACCESS_COOKIE_NAME", "cleandataai_access")

# TTL del access token (minutos)
ACCESS_TTL_MIN: int = int(os.getenv("ACCESS_TTL_MIN", "60"))

# Flags de cookies
# COOKIE_SECURE: en prod => 1 (true) si sirves por HTTPS
COOKIE_SECURE: bool = _as_bool(os.getenv("COOKIE_SECURE", "0"), default=False)
# COOKIE_SAMESITE: 'lax' (dev recomendado), 'none' (si frontend en dominio distinto con HTTPS), 'strict'
COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()

# ------------------------------
# Límite “gratuito” sin autenticación
# ------------------------------
FREE_LIMIT: int = int(os.getenv("FREE_LIMIT", "7"))

# ------------------------------
# Outliers / IsolationForest
# ------------------------------
OUTLIER_CONTAMINATION: float = float(os.getenv("OUTLIER_CONTAMINATION", "0.05"))
OUTLIER_RANDOM_STATE: int = int(os.getenv("OUTLIER_RANDOM_STATE", "42"))

# ------------------------------
# Protección de endpoints de artefactos e historial
# ------------------------------
# En dev/tests los dejamos públicos para no romper pruebas.
# En producción ponlos a 0/false para exigir sesión/JWT.
ARTIFACTS_PUBLIC: bool = _as_bool(os.getenv("ARTIFACTS_PUBLIC", "1"), default=True)
HISTORY_PUBLIC: bool = _as_bool(os.getenv("HISTORY_PUBLIC", "1"), default=True)

# ------------------------------
# IA Generativa (Groq / Llama 3)
# ------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
# Modelo recomendado: Llama 3 70B (más inteligente)
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Verificación de seguridad en consola al iniciar
if not GROQ_API_KEY:
    print("⚠️  ADVERTENCIA: No se encontró GROQ_API_KEY. El análisis narrativo usará plantillas genéricas.")
else:
    print(f"✅ IA Activada: Usando Groq con modelo {GROQ_MODEL}")