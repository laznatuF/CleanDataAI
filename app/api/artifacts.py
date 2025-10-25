# app/api/artifacts.py
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.core.config import RUNS_DIR, ARTIFACTS_PUBLIC
from app.core.security import get_user_id_from_request
from app.infrastructure.process_repo_fs import read_status

router = APIRouter()


def _ensure_allowed_or_auth(request: Request) -> None:
    """
    Si ARTIFACTS_PUBLIC=1: no exige auth.
    Si ARTIFACTS_PUBLIC=0: requiere cookie de sesión válida.
    """
    if ARTIFACTS_PUBLIC:
        return
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail="No autenticado.")


def _artifact_real_path(process_id: str, name: str) -> Path:
    """
    Resuelve la ruta física del artefacto y valida que exista.
    """
    # Primero confirmamos que el artefacto está registrado en status.json
    st = read_status(process_id)
    arts = (st.get("artifacts") or {}) if isinstance(st, dict) else {}
    rel = arts.get(name)
    if not rel:
        # como fallback, intentamos directamente en artifacts/ por compat local
        candidate = RUNS_DIR / process_id / "artifacts" / name
        if not candidate.exists():
            raise HTTPException(status_code=404, detail="Artefacto no registrado o no existe.")
        return candidate

    # Si viene relativo al proyecto, lo resolvemos
    p = Path(rel)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parents[2] / p).resolve()

    if not p.exists():
        # fallback directo dentro de artifacts/ (por si cambió BASE_DIR)
        candidate = RUNS_DIR / process_id / "artifacts" / name
        if candidate.exists():
            return candidate
        raise HTTPException(status_code=404, detail="Archivo de artefacto no encontrado en disco.")

    return p


def _guess_media_type(name: str) -> str:
    """
    Forzamos 'text/csv' para .csv (Windows puede mapear a 'application/vnd.ms-excel').
    Para HTML, 'text/html'. Resto: mimetypes -> octet-stream.
    """
    suf = Path(name).suffix.lower()
    if suf == ".csv":
        return "text/csv"
    if suf in {".html", ".htm"}:
        return "text/html"
    ctype, _ = mimetypes.guess_type(name)
    return ctype or "application/octet-stream"


def _file_response(path: Path, name: str, download: bool = False) -> FileResponse:
    media_type = _guess_media_type(name)
    # filename activa Content-Disposition (attachment/inline según download)
    # En Starlette, FileResponse pone 'attachment' solo si pasas 'filename' y 'headers'.
    # Usamos Content-Disposition manual cuando download=1.
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=None if not download else name,
        headers=headers or None,
    )


@router.get("/artifacts/{process_id}/{name}")
def get_artifact_public(process_id: str, name: str, request: Request, download: int = 0):
    """
    Variante pública (habilitada cuando ARTIFACTS_PUBLIC=1). Si ARTIFACTS_PUBLIC=0 exige sesión.
    """
    _ensure_allowed_or_auth(request)
    path = _artifact_real_path(process_id, name)
    return _file_response(path, name, download=bool(download))


# También funcionará montado con prefix="/api" desde main.py
@router.get("/api/artifacts/{process_id}/{name}")
def get_artifact_api(process_id: str, name: str, request: Request, download: int = 0):
    _ensure_allowed_or_auth(request)
    path = _artifact_real_path(process_id, name)
    return _file_response(path, name, download=bool(download))
