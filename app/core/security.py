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
