# app/api/auth_pwless.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from random import randint
from typing import Optional, Dict
import time

from app.core.config import SECRET_KEY, FRONTEND_ORIGIN
from app.core.security import (
    create_access_token,     # ← usamos token + set_access_cookie
    set_access_cookie,
    clear_access_cookie,
    get_user_id_from_request,
)
from app.services.users import get_or_create_user, get_user_by_id
from app.services.mailer import send_mail, APP_NAME

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Memoria (dev). En prod usar Redis/DB.
_otp_store: Dict[str, Dict] = {}  # email -> {"code": "123456", "exp": epoch}
serializer = URLSafeTimedSerializer(SECRET_KEY)

MAGIC_TTL_MIN = 10
OTP_TTL_SEC   = 10 * 60

class ReqLogin(BaseModel):
    email: EmailStr
    name: Optional[str] = ""

class VerifyBody(BaseModel):
    email: Optional[EmailStr] = None
    code: Optional[str] = None
    token: Optional[str] = None  # token de enlace mágico

def _issue_cookie_for_email(resp: Response, email: str):
    user = get_or_create_user(email)
    access = create_access_token(sub=user.id)
    set_access_cookie(resp, access)
    return {"id": user.id, "email": user.email, "name": user.name, "plan": user.plan}

@router.post("/request")
def request_login(body: ReqLogin):
    user = get_or_create_user(body.email, body.name or "")
    # OTP 6 dígitos
    code = f"{randint(0, 999999):06d}"
    _otp_store[user.email] = {"code": code, "exp": int(time.time()) + OTP_TTL_SEC}

    # Enlace mágico firmado
    token = serializer.dumps({"email": user.email, "purpose": "magic"})
    magic_url = f"{FRONTEND_ORIGIN.rstrip('/')}/login?token={token}"

    html = f"""
      <p>Hola {user.name or user.email},</p>
      <p>Usa este enlace para entrar a <b>{APP_NAME}</b> (expira en {MAGIC_TTL_MIN} minutos):</p>
      <p><a href="{magic_url}">{magic_url}</a></p>
      <p>O ingresa este código (expira en 10 minutos): <b style="font-size:18px">{code}</b></p>
      <p>Si no solicitaste esto, ignora este correo.</p>
    """
    send_mail(user.email, f"Tu acceso a {APP_NAME}", html)
    return {"ok": True}

@router.post("/verify")
def verify(resp: Response, body: VerifyBody):
    # 1) Verificación via token (enlace mágico)
    if body.token:
        try:
            data = serializer.loads(body.token, max_age=MAGIC_TTL_MIN * 60)
            if data.get("purpose") != "magic":
                raise HTTPException(status_code=400, detail="Token inválido")
            email = data.get("email")
            profile = _issue_cookie_for_email(resp, email)
            return {"ok": True, "user": profile}
        except SignatureExpired:
            raise HTTPException(status_code=400, detail="Token expirado")
        except BadSignature:
            raise HTTPException(status_code=400, detail="Token inválido")

    # 2) Verificación via OTP
    if body.email and body.code:
        rec = _otp_store.get(str(body.email))
        if not rec:
            raise HTTPException(status_code=400, detail="Código no encontrado")
        if rec["exp"] < time.time():
            _otp_store.pop(str(body.email), None)
            raise HTTPException(status_code=400, detail="Código expirado")
        if rec["code"] != body.code:
            raise HTTPException(status_code=400, detail="Código incorrecto")
        _otp_store.pop(str(body.email), None)
        profile = _issue_cookie_for_email(resp, str(body.email))
        return {"ok": True, "user": profile}

    raise HTTPException(status_code=400, detail="Faltan datos para verificar")

@router.post("/logout")
def logout(resp: Response):
    clear_access_cookie(resp)
    return {"ok": True}

@router.get("/me")
def me(request: Request):
    uid = get_user_id_from_request(request)
    if not uid:
        return {"user": None}
    u = get_user_by_id(uid)
    return {"user": {"id": u.id, "email": u.email, "name": u.name, "plan": u.plan}}
