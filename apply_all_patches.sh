#!/usr/bin/env bash
set -euo pipefail

# --- 1) app/core/config.py ---
cat > app/core/config.py <<'PY'
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
PY

# --- 2) app/api/process.py ---
cat > app/api/process.py <<'PY'
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.core.config import ALLOWED_EXTENSIONS
from app.application.pipeline import create_initial_process, process_pipeline

router = APIRouter()

@router.post("/process", status_code=201)
def process_file(background: BackgroundTasks, file: UploadFile = File(...)):
    """
    Crea un proceso (status: queued), guarda el archivo y lanza el pipeline en background.
    Devuelve el identificador del proceso.
    """
    # Validaciones básicas del upload
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No se recibió un archivo.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensión no permitida.")

    # Crear el proceso y materializar entrada
    try:
        init = create_initial_process(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar el pipeline: {e!s}")

    process_id = init.get("id")
    if not process_id:
        raise HTTPException(status_code=500, detail="No se pudo generar process_id.")

    # Ejecutar pipeline en background
    background.add_task(process_pipeline, process_id)

    return {"id": process_id, "process_id": process_id, "status": "queued"}
PY

# --- 3) app/infrastructure/files.py ---
cat > app/infrastructure/files.py <<'PY'
from __future__ import annotations

import os
import json
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import RUNS_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB

CHUNK_SIZE = 1024 * 1024  # 1 MB


def _sanitize_filename(name: str) -> str:
    return Path(name or "input.bin").name


def _get_size_bytes(file: UploadFile) -> int:
    f = file.file
    cur = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(cur, os.SEEK_SET)
    return size


def validate_filename_and_size(file: UploadFile) -> None:
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="No se recibió un nombre de archivo.")

    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Formato no soportado. Usa CSV, XLSX, XLS u ODS.")

    max_bytes = int(float(MAX_FILE_SIZE_MB) * 1024 * 1024)
    size = _get_size_bytes(file)
    if size > max_bytes:
        mb = round(size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande ({mb} MB). Límite permitido: {int(MAX_FILE_SIZE_MB)} MB."
        )


def create_process_dir(base: Path | None = None) -> Path:
    from uuid import uuid4
    root = base or RUNS_DIR
    proc_dir = root / str(uuid4())
    (proc_dir / "input").mkdir(parents=True, exist_ok=True)
    (proc_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (proc_dir / "tmp").mkdir(parents=True, exist_ok=True)
    return proc_dir


def save_upload(file: UploadFile, proc_dir: Path) -> Path:
    validate_filename_and_size(file)

    safe_name = _sanitize_filename(file.filename)
    target = proc_dir / "input" / safe_name
    tmp = target.with_suffix(target.suffix + ".tmp")
    target.parent.mkdir(parents=True, exist_ok=True)

    file.file.seek(0)
    written = 0
    max_bytes = int(float(MAX_FILE_SIZE_MB) * 1024 * 1024)

    try:
        with tmp.open("wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Archivo supera el límite permitido de {int(MAX_FILE_SIZE_MB)} MB."
                    )
                out.write(chunk)
        tmp.replace(target)
    except HTTPException:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {e!s}")

    return target


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
PY

# --- 4) app/infrastructure/datasources.py ---
cat > app/infrastructure/datasources.py <<'PY'
from __future__ import annotations
from pathlib import Path
from typing import Union

import pandas as pd

from app.core.config import ALLOWED_EXTENSIONS

PathLike = Union[str, Path]

_OPENPYXL_EXTS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
_XLRD_EXTS = {".xls"}


def _read_csv(path: Path) -> pd.DataFrame:
    try_encodings = ["utf-8-sig", "utf-8", "latin-1"]
    last_err: Exception | None = None
    for enc in try_encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
            continue
    try:
        return pd.read_csv(path)
    except Exception as e:
        raise RuntimeError(f"No fue posible leer el CSV (último error: {e!s})") from (last_err or e)


def _read_excel(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf in _OPENPYXL_EXTS:
        engine = "openpyxl"
    elif suf in _XLRD_EXTS:
        engine = "xlrd"
    else:
        engine = None
    try:
        return pd.read_excel(path, engine=engine)
    except ImportError as e:
        if engine == "openpyxl":
            raise RuntimeError("Falta 'openpyxl' para leer .xlsx/.xlsm/.xltx/.xltm.") from e
        if engine == "xlrd":
            raise RuntimeError("Falta 'xlrd' para leer .xls.") from e
        raise
    except Exception as e:
        raise RuntimeError(f"Error leyendo Excel con engine={engine!r}: {e!s}") from e


def _read_ods(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path, engine="odf")
    except ImportError as e:
        raise RuntimeError("Falta 'odfpy' para leer .ods.") from e
    except Exception as e:
        raise RuntimeError(f"Error leyendo ODS: {e!s}") from e


def read_dataframe(path: PathLike) -> pd.DataFrame:
    """
    Lee CSV / Excel / ODS y devuelve un DataFrame normalizando encabezados.
    Valida la extensión contra app.core.config.ALLOWED_EXTENSIONS.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")

    suf = p.suffix.lower()
    if suf not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Extensión no soportada: {suf}. Permitidas: {allowed}")

    if suf == ".csv":
        df = _read_csv(p)
    elif suf in (_OPENPYXL_EXTS | _XLRD_EXTS):
        df = _read_excel(p)
    elif suf == ".ods":
        df = _read_ods(p)
    else:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Extensión no soportada (guardarraíl): {suf}. Permitidas: {allowed}")

    df.columns = [str(c).strip() for c in df.columns]
    return df
PY

# --- 5) app/core/security.py ---
cat > app/core/security.py <<'PY'
from __future__ import annotations

from typing import Optional
from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired, BadTimeSignature

from app.core.config import (
    SECRET_KEY,
    ACCESS_COOKIE_NAME,
    ACCESS_TTL_MIN,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
)

_TOKEN_SALT = "cleandataai.access.v1"


def _ser() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=SECRET_KEY, salt=_TOKEN_SALT)


def create_access_token(sub: str) -> str:
    return _ser().dumps({"sub": str(sub), "purpose": "access"})


def set_access_cookie(resp: Response, token: str) -> None:
    secure_flag = True if str(COOKIE_SAMESITE).lower() == "none" else bool(COOKIE_SECURE)
    resp.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TTL_MIN * 60,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=secure_flag,
        path="/",
    )


def clear_access_cookie(resp: Response) -> None:
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")


def get_user_id_from_request(request: Request) -> Optional[str]:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _ser().loads(token, max_age=ACCESS_TTL_MIN * 60)
    except (BadSignature, BadTimeSignature, SignatureExpired):
        return None

    if data.get("purpose") != "access":
        return None

    sub = data.get("sub")
    return str(sub) if sub is not None else None
PY

# --- 6) .gitignore (añadidos útiles) ---
touch .gitignore
grep -q "__pycache__/" .gitignore || cat >> .gitignore <<'GI'
__pycache__/
*.py[cod]
.venv/
venv/
env/
runs/
data/*.tmp
frontend/node_modules/
node_modules/
*.log
*.DS_Store
GI

echo "OK: archivos principales actualizados."

# --- 7) Parches ATÓMICOS para repos FS (no pisamos tu lógica, solo helpers) ---

# 7.1) app/infrastructure/process_repo_fs.py  -> añade helper de escritura atómica si no existe
if grep -q "def _write_json_atomic" app/infrastructure/process_repo_fs.py 2>/dev/null; then
  echo "process_repo_fs.py: helper atómico ya existe."
else
  # Insertamos helper y 'import json' si falta
  sed -i '1s;^;from pathlib import Path\nimport json\n\n;' app/infrastructure/process_repo_fs.py
  cat >> app/infrastructure/process_repo_fs.py <<'PY'

def _write_json_atomic(path: Path, data: dict) -> None:
    """
    Escritura JSON atómica (.tmp + replace). No toca la lógica de negocio; solo la persistencia.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
PY
  echo "process_repo_fs.py: helper atómico insertado (recuerda usarlo donde hagas json.dump)."
fi

# 7.2) app/infrastructure/users_repo_fs.py  -> añade helper de escritura atómica si no existe
if grep -q "def _write_json_atomic" app/infrastructure/users_repo_fs.py 2>/dev/null; then
  echo "users_repo_fs.py: helper atómico ya existe."
else
  sed -i '1s;^;from pathlib import Path\nimport json\n\n;' app/infrastructure/users_repo_fs.py
  cat >> app/infrastructure/users_repo_fs.py <<'PY'

def _write_json_atomic(path: Path, data: dict) -> None:
    """
    Escritura JSON atómica (.tmp + replace) para users.json.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
PY
  echo "users_repo_fs.py: helper atómico insertado (recuerda usarlo donde hagas json.dump)."
fi

echo "Listo: aplica ahora los helpers en las funciones que persisten JSON."
