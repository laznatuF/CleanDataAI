# app/api/private_demo.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.security import get_user_id_from_auth_header

router = APIRouter(tags=["private-demo"])

def require_bearer_user(request: Request) -> str:
    """
    Requiere Authorization: Bearer <token>.
    Devuelve user_id si válido o lanza 401.
    """
    uid = get_user_id_from_auth_header(request)
    if not uid:
        # WWW-Authenticate: Bearer → para que clientes sepan qué enviar
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return uid

@router.get("/private-demo")
def private_demo(user_id: str = Depends(require_bearer_user)):
    return {
        "ok": True,
        "user_id": user_id,
        "message": "Acceso concedido vía Authorization: Bearer.",
    }
