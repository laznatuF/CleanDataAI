# app/api/help.py
from __future__ import annotations

from datetime import datetime
from html import escape as html_escape

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.core.config import APP_NAME, SUPPORT_EMAIL, FRONTEND_ORIGIN
from app.infrastructure.mailer import send_mail

router = APIRouter(prefix="/api/help", tags=["help"])


class HelpRequest(BaseModel):
    # ✅ Pydantic v2 (FastAPI 0.111)
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    category: str = Field(..., min_length=1, max_length=30)
    subject: str | None = Field(default=None, max_length=150)
    message: str = Field(..., min_length=10, max_length=5000)

    @field_validator("subject", mode="before")
    @classmethod
    def empty_subject_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


@router.post("", summary="Enviar mensaje de soporte")
async def send_help(req: HelpRequest, bg: BackgroundTasks, request: Request):
    if not SUPPORT_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="Soporte no disponible temporalmente. Intenta más tarde.",
        )

    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    origin = request.headers.get("origin") or FRONTEND_ORIGIN or "desconocido"
    ua = request.headers.get("user-agent", "desconocido")

    mail_subject = f"[{APP_NAME}] Nuevo mensaje de soporte ({req.category})"

    html = f"""
    <h2>{html_escape(APP_NAME)} – Nuevo mensaje de soporte</h2>
    <p><strong>Fecha:</strong> {html_escape(created_at)}</p>
    <p><strong>Origen:</strong> {html_escape(origin)}</p>
    <p><strong>User-Agent:</strong> {html_escape(ua)}</p>
    <hr />
    <p><strong>Nombre:</strong> {html_escape(req.name)}</p>
    <p><strong>Email:</strong> {html_escape(str(req.email))}</p>
    <p><strong>Tipo:</strong> {html_escape(req.category)}</p>
    <p><strong>Asunto:</strong> {html_escape(req.subject) if req.subject else "(sin asunto)"}</p>
    <hr />
    <p><strong>Mensaje:</strong></p>
    <pre style="font-family: monospace; white-space: pre-wrap; margin: 0;">{html_escape(req.message)}</pre>
    """

    bg.add_task(send_mail, SUPPORT_EMAIL, mail_subject, html)
    return {"ok": True}


# ✅ compat: /api/help/
@router.post("/", include_in_schema=False)
async def send_help_slash(req: HelpRequest, bg: BackgroundTasks, request: Request):
    return await send_help(req, bg, request)
