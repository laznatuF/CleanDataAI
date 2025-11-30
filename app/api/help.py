# app/api/help.py
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.config import APP_NAME, SUPPORT_EMAIL, FRONTEND_ORIGIN
from app.infrastructure.mailer import send_mail

router = APIRouter(prefix="/api/help", tags=["help"])

class HelpRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    category: str = Field(..., min_length=1, max_length=30)
    subject: str | None = Field(None, min_length=1, max_length=150)
    message: str = Field(..., min_length=10, max_length=5000)

    class Config:
        # Para pydantic v1: recorta espacios en blanco iniciales/finales
        anystr_strip_whitespace = True

@router.post("/", summary="Enviar mensaje de soporte")
async def send_help(req: HelpRequest, bg: BackgroundTasks):
    """
    Recibe el formulario de ayuda y envía un correo al buzón de soporte.
    """

    if not SUPPORT_EMAIL:
        # Si no hay SUPPORT_EMAIL configurado algo anda mal
        raise HTTPException(
            status_code=500,
            detail="Soporte no disponible temporalmente. Intenta más tarde.",
        )

    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    subject = f"[{APP_NAME}] Nuevo mensaje de soporte ({req.category})"

    # HTML sencillo con los datos del formulario
    html = f"""
    <h2>{APP_NAME} – Nuevo mensaje de soporte</h2>
    <p><strong>Fecha:</strong> {created_at}</p>
    <p><strong>Origen:</strong> {FRONTEND_ORIGIN or "desconocido"}</p>
    <hr />
    <p><strong>Nombre:</strong> {req.name}</p>
    <p><strong>Email:</strong> {req.email}</p>
    <p><strong>Tipo:</strong> {req.category}</p>
    <p><strong>Asunto:</strong> {req.subject or "(sin asunto)"}</p>
    <hr />
    <p><strong>Mensaje:</strong></p>
    <pre style="font-family: monospace; white-space: pre-wrap;">
{req.message}
    </pre>
    """

    # Enviar en background para no bloquear la respuesta
    bg.add_task(send_mail, SUPPORT_EMAIL, subject, html)

    return {"ok": True}
