# app/api/history.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse

from app.core.config import HISTORY_PUBLIC
from app.core.security import get_user_id_from_request
from app.infrastructure.history_repo_fs import read_history, history_file_for_download

router = APIRouter()

def _ensure_allowed_or_auth(request: Request) -> None:
    """
    Si HISTORY_PUBLIC=1: no exige auth.
    Si HISTORY_PUBLIC=0: requiere cookie de sesión válida.
    """
    if HISTORY_PUBLIC:
        return
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail="No autenticado.")


def _load_rows(process_id: str) -> List[Dict]:
    try:
        rows = read_history(process_id)
    except FileNotFoundError:
        rows = []
    if rows is None:
        rows = []
    return rows


@router.get("/history/{process_id}")
def get_history_public(process_id: str, request: Request, download: int = 0):
    """
    Por defecto devuelve JSON con forma { "items": [...] } (compat con tests).
    Si download=1 devuelve el archivo NDJSON (para descarga directa).
    """
    _ensure_allowed_or_auth(request)

    if download:
        path = history_file_for_download(process_id)
        if not path.exists():
            # Compat: si no hay archivo, devolvemos JSON vacío (no 404)
            return JSONResponse({"items": []})
        return FileResponse(
            path,
            media_type="application/x-ndjson",
            filename=f"history_{process_id}.jsonl",
        )

    rows = _load_rows(process_id)
    return JSONResponse({"items": rows})


@router.get("/api/history/{process_id}")
def get_history_api(process_id: str, request: Request, download: int = 0):
    """
    Misma lógica que /history/{id}, pero bajo /api/.
    """
    _ensure_allowed_or_auth(request)

    if download:
        path = history_file_for_download(process_id)
        if not path.exists():
            return JSONResponse({"items": []})
        return FileResponse(
            path,
            media_type="application/x-ndjson",
            filename=f"history_{process_id}.jsonl",
        )

    rows = _load_rows(process_id)
    return JSONResponse({"items": rows})
