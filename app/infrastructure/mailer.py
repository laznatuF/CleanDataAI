# app/infrastructure/mailer.py
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from pathlib import Path

# Opcional pero recomendado: asegura lectura de .env incluso si mailer se importa antes que config.py
try:
    from dotenv import load_dotenv  # type: ignore
    BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(BASE_DIR / ".env", override=False)
except Exception:
    # Si no hay python-dotenv o falla, seguimos con env del sistema
    pass


def _as_bool(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _only_email(value: str) -> str:
    """
    Acepta 'Nombre <correo@x>' o 'correo@x' y retorna solo el email.
    Esto evita romper el envelope-from de sendmail().
    """
    _, addr = parseaddr(value or "")
    return (addr or value or "").strip()


def _get_settings():
    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = int((os.getenv("SMTP_PORT", "").strip() or "0"))

    SMTP_USER = os.getenv("SMTP_USER", "").strip()
    SMTP_PASS = os.getenv("SMTP_PASS", "").strip()

    APP_NAME = os.getenv("APP_NAME", "CleanDataAI").strip()
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", APP_NAME).strip()

    # MAIL_FROM puede venir como "Nombre <correo@...>" → dejamos solo el correo real
    MAIL_FROM_RAW = os.getenv("MAIL_FROM", SMTP_USER or "noreply@cleandata.ai").strip()
    MAIL_FROM = _only_email(MAIL_FROM_RAW) or (SMTP_USER or "noreply@cleandata.ai").strip()

    # Si quieres forzar modo dev aunque haya SMTP, pon MAIL_DEV=1
    MAIL_DEV = _as_bool(os.getenv("MAIL_DEV", "").strip())

    return {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASS": SMTP_PASS,
        "MAIL_FROM": MAIL_FROM,
        "MAIL_FROM_NAME": MAIL_FROM_NAME,
        "APP_NAME": APP_NAME,
        "MAIL_DEV": MAIL_DEV,
    }


def _from_header(mail_from: str, mail_from_name: str, app_name: str) -> str:
    return formataddr((mail_from_name or app_name or "CleanDataAI", mail_from))


def send_mail(to: str, subject: str, html: str) -> None:
    """
    Envía correo HTML por SMTP (Gmail recomendado con App Password).
    Si no hay SMTP_HOST/SMTP_PORT o MAIL_DEV=1, imprime en consola (modo dev).
    """
    cfg = _get_settings()

    to = (to or "").strip()
    to_email = _only_email(to)
    if not to_email:
        raise ValueError("Destinatario vacío (to).")

    SMTP_HOST = cfg["SMTP_HOST"]
    SMTP_PORT = cfg["SMTP_PORT"]
    SMTP_USER = cfg["SMTP_USER"]
    SMTP_PASS = cfg["SMTP_PASS"]

    MAIL_FROM = cfg["MAIL_FROM"]
    MAIL_FROM_NAME = cfg["MAIL_FROM_NAME"]
    APP_NAME = cfg["APP_NAME"]
    MAIL_DEV = cfg["MAIL_DEV"]

    # DEV fallback
    if MAIL_DEV or not SMTP_HOST or not SMTP_PORT:
        print("\n=== DEV MAIL ===")
        print("To:", to_email)
        print("Subject:", subject)
        print(html)
        print("=== /DEV MAIL ===\n")
        return

    # Si hay usuario pero no hay pass, mejor fallar explícito (igual fallaría en login)
    if SMTP_USER and not SMTP_PASS:
        raise ValueError("SMTP_PASS está vacío. En Gmail debes usar App Password (no tu contraseña normal).")

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = _from_header(MAIL_FROM, MAIL_FROM_NAME, APP_NAME)
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.ehlo()

        # STARTTLS (Gmail 587)
        if SMTP_USER:
            s.starttls()
            s.ehlo()
            s.login(SMTP_USER, SMTP_PASS)

        # envelope-from debe ser solo email (MAIL_FROM)
        s.sendmail(MAIL_FROM, [to_email], msg.as_string())
