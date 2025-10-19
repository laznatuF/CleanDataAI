# app/core/security.py
from __future__ import annotations

from typing import Optional
from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.config import SECRET_KEY, ACCESS_COOKIE_NAME, ACCESS_TTL_MIN

# Serializer para firmar/verificar tokens
def _ser() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SECRET_KEY)

# Crea un “access token” firmado con su propósito
def create_access_token(sub: str) -> str:
    # No lleva “exp” dentro; la expiración se chequea con max_age al decodificar
    return _ser().dumps({"sub": sub, "purpose": "access"})

# Guarda el token en cookie HttpOnly
def set_access_cookie(resp: Response, token: str) -> None:
    max_age = ACCESS_TTL_MIN * 60
    # Ajusta secure=True en producción con HTTPS
    resp.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )

# Borra la cookie de acceso
def clear_access_cookie(resp: Response) -> None:
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")

# Extrae y valida el user_id (sub) desde la cookie del request
def get_user_id_from_request(request: Request) -> Optional[str]:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _ser().loads(token, max_age=ACCESS_TTL_MIN * 60)
        if data.get("purpose") != "access":
            return None
        return str(data.get("sub"))
    except (BadSignature, SignatureExpired):
        return None
