# app/api/auth_pwless.py
from __future__ import annotations

import time
from random import randint
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.config import SECRET_KEY, FRONTEND_ORIGIN, APP_NAME  # ✅ APP_NAME desde config
from app.core.security import (
    create_access_token,
    set_access_cookie,
    clear_access_cookie,
    get_user_id_from_request,
)
from app.application.users_service import (
    get_or_create_user,
    get_user_by_id,
    register_user,
    set_user_plan,
)
from app.infrastructure.mailer import send_mail  # ✅ solo send_mail desde mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])

_otp_store: Dict[str, Dict] = {}
serializer = URLSafeTimedSerializer(SECRET_KEY)

MAGIC_TTL_MIN = 10
OTP_TTL_SEC = 10 * 60


# -----------------------
# Schemas
# -----------------------
class ReqLogin(BaseModel):
    email: EmailStr
    name: Optional[str] = ""


class VerifyBody(BaseModel):
    email: Optional[EmailStr] = None
    code: Optional[str] = None
    token: Optional[str] = None


class RegisterBody(BaseModel):
    email: EmailStr
    name: Optional[str] = ""
    plan: str = "free"  # free | standard | pro


class SetPlanBody(BaseModel):
    plan: str


# -----------------------
# Helpers
# -----------------------
def _user_public(u: Dict) -> Dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "plan": u.get("plan", "free"),
    }


def _issue_cookie_for_email(resp: Response, email: str) -> Dict:
    user = get_or_create_user(str(email))
    access = create_access_token(sub=user["id"])
    set_access_cookie(resp, access)
    return _user_public(user)


# -----------------------
# Endpoints Auth pwless
# -----------------------
@router.post("/request")
def request_login(body: ReqLogin):
    user = get_or_create_user(str(body.email), body.name or "")

    code = f"{randint(0, 999999):06d}"
    _otp_store[user["email"]] = {"code": code, "exp": int(time.time()) + OTP_TTL_SEC}

    token = serializer.dumps({"email": user["email"], "purpose": "magic"})

    # ✅ Importante: tu frontend valida token en /login/token
    magic_url = f"{FRONTEND_ORIGIN.rstrip('/')}/login/token?token={token}"

    html = (
        f"<p>Hola {user.get('name','')},</p>"
        f"<p>Usa este enlace para entrar a <b>{APP_NAME}</b> sin contraseña (expira en {MAGIC_TTL_MIN} minutos):</p>"
        f"<p><a href='{magic_url}'>{magic_url}</a></p>"
        f"<p>O ingresa este código (expira en 10 minutos): "
        f"<b style='font-size:18px'>{code}</b></p>"
        f"<p>Si no solicitaste esto, ignora este correo.</p>"
    )

    send_mail(user["email"], f"Tu acceso a {APP_NAME}", html)
    return {"ok": True}


@router.post("/verify")
def verify(resp: Response, body: VerifyBody):
    # --- magic link token ---
    if body.token:
        try:
            data = serializer.loads(body.token, max_age=MAGIC_TTL_MIN * 60)
            if data.get("purpose") != "magic":
                raise HTTPException(status_code=400, detail="Token inválido")

            email = str(data.get("email") or "")
            if not email:
                raise HTTPException(status_code=400, detail="Token inválido")

            profile = _issue_cookie_for_email(resp, email)
            return {"ok": True, "user": profile}

        except SignatureExpired:
            raise HTTPException(status_code=400, detail="Token expirado")
        except BadSignature:
            raise HTTPException(status_code=400, detail="Token inválido")

    # --- OTP code ---
    if body.email and body.code:
        email_low = str(body.email).lower().strip()
        rec = _otp_store.get(email_low)

        if not rec:
            raise HTTPException(status_code=400, detail="Código no encontrado")

        if rec["exp"] < time.time():
            _otp_store.pop(email_low, None)
            raise HTTPException(status_code=400, detail="Código expirado")

        if rec["code"] != body.code:
            raise HTTPException(status_code=400, detail="Código incorrecto")

        _otp_store.pop(email_low, None)
        profile = _issue_cookie_for_email(resp, email_low)
        return {"ok": True, "user": profile}

    raise HTTPException(status_code=400, detail="Faltan datos para verificar")


@router.post("/register")
def register(resp: Response, body: RegisterBody):
    """
    Registro local (demo): crea/actualiza usuario con plan y deja sesión (cookie).
    """
    try:
        user = register_user(str(body.email), body.name or "", body.plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    access = create_access_token(sub=user["id"])
    set_access_cookie(resp, access)
    return {"ok": True, "user": _user_public(user)}


@router.post("/set-plan")
def set_plan(request: Request, body: SetPlanBody):
    """
    Simula upgrade/downgrade de plan. Requiere estar logueado (cookie).
    """
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        u = set_user_plan(uid, body.plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {"ok": True, "user": _user_public(u)}


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
    if not u:
        return {"user": None}

    return {"user": _user_public(u)}
