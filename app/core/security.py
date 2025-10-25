# app/core/security.py
from __future__ import annotations

from typing import Optional
from fastapi import Request, Response
from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    BadTimeSignature,
    SignatureExpired,
)

from app.core.config import (
    SECRET_KEY,
    ACCESS_COOKIE_NAME,
    ACCESS_TTL_MIN,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
)

# Sal para distinguir propósito (rotar si cambias semánticas)
_TOKEN_SALT = "cleandataai.access.v1"


def _ser() -> URLSafeTimedSerializer:
    """Serializer firmado y con sal para tokens de acceso."""
    return URLSafeTimedSerializer(secret_key=SECRET_KEY, salt=_TOKEN_SALT)


# -----------------------------
# Creación y verificación token
# -----------------------------
def create_access_token(sub: str) -> str:
    """Crea un token firmado; la expiración se valida al 'loads' con max_age."""
    return _ser().dumps({"sub": str(sub), "purpose": "access"})


def verify_access_token(token: str) -> Optional[str]:
    """
    Devuelve user_id (sub) si el token es válido y no expiró; si no, None.
    """
    try:
        data = _ser().loads(token, max_age=ACCESS_TTL_MIN * 60)
        if data.get("purpose") != "access":
            return None
        sub = data.get("sub")
        return str(sub) if sub is not None else None
    except (BadSignature, BadTimeSignature, SignatureExpired):
        return None


# -----------------------------
# Cookies (HttpOnly)
# -----------------------------
def set_access_cookie(resp: Response, token: str) -> None:
    """
    Guarda el token en cookie HttpOnly.
    Si COOKIE_SAMESITE == 'none', forzamos secure=True (requerido por los navegadores).
    En otros casos usamos COOKIE_SECURE.
    """
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
    """Elimina la cookie de acceso."""
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")


def get_user_id_from_request(request: Request) -> Optional[str]:
    """
    Extrae user_id desde la cookie de acceso si es válida.
    """
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    return verify_access_token(token)


# -----------------------------
# Authorization: Bearer
# -----------------------------
def _get_bearer_token(request: Request) -> Optional[str]:
    """
    Extrae el token Bearer del header Authorization.
    Formato esperado: 'Authorization: Bearer <token>'.
    """
    auth = request.headers.get("Authorization", "").strip()
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_user_id_from_auth_header(request: Request) -> Optional[str]:
    """
    Valida Authorization: Bearer y devuelve user_id si es válido; si no, None.
    """
    token = _get_bearer_token(request)
    if not token:
        return None
    return verify_access_token(token)


# -----------------------------
# Helper combinado
# -----------------------------
def get_user_id_any(request: Request) -> Optional[str]:
    """
    Intenta autenticar primero por Authorization: Bearer y luego por cookie HttpOnly.
    Útil en endpoints que aceptan ambos mecanismos.
    """
    uid = get_user_id_from_auth_header(request)
    if uid:
        return uid
    return get_user_id_from_request(request)
