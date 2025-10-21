# app/infrastructure/mailer.py
from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText

MAIL_FROM = os.getenv("MAIL_FROM", "noreply@cleandata.ai")
SMTP_HOST  = os.getenv("SMTP_HOST", "")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "0") or 0)
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
APP_NAME   = os.getenv("APP_NAME", "CleanDataAI")

def send_mail(to: str, subject: str, html: str):
    # DEV: si no hay SMTP, imprime en consola
    if not SMTP_HOST:
        print("\n=== DEV MAIL ===")
        print("To:", to)
        print("Subject:", subject)
        print(html)
        print("=== /DEV MAIL ===\n")
        return

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = to

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        if SMTP_USER:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(MAIL_FROM, [to], msg.as_string())
