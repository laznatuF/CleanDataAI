# app/main.py
from __future__ import annotations

import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import (
    RUNS_DIR,
    FRONTEND_ORIGIN,
    ARTIFACTS_PUBLIC,
    HISTORY_PUBLIC,
)

from app.api.status import router as status_router
from app.api.process import router as process_router
from app.api.auth_pwless import router as auth_router       # /api/auth/*
from app.api.artifacts import router as artifacts_router    # /artifacts* (definido en router)
from app.api.history import router as history_router        # /history*   (definido en router)
from app.api.private_demo import router as private_demo_router
from app.api.help import router as help_router              # /api/help (prefix dentro del router)

app = FastAPI(title="CleanDataAI")


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ---------- CORS (imprescindible allow_credentials para cookies) ----------
def _norm_origin(o: str) -> str:
    return (o or "").strip().rstrip("/")


allowed_origins = {
    _norm_origin(FRONTEND_ORIGIN),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
allowed_origins = {o for o in allowed_origins if o}  # filtra vacíos

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,  # necesario para cookies HttpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Meta ----------
@app.get("/", tags=["meta"])
def root():
    return {
        "name": "CleanDataAI API",
        "status": "ok",
        "time": _now_iso(),
        "message": "Bienvenido a CleanDataAI",
    }


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True, "time": _now_iso()}


@app.get("/api/", tags=["meta"])
def api_root():
    return {
        "name": "CleanDataAI API",
        "status": "ok",
        "time": _now_iso(),
        "message": "API disponible",
        "base": "/api",
    }


@app.get("/api/health", tags=["meta"])
def api_health_alias():
    return {"ok": True, "time": _now_iso()}


# ---------- Estáticos (solo desarrollo) ----------
# En producción NO expongas /runs; sirve artefactos vía /api/artifacts/*
if os.getenv("EXPOSE_RUNS_STATIC", "1") == "1":
    app.mount("/runs", StaticFiles(directory=str(RUNS_DIR)), name="runs")


# ---------- Routers ----------
# Auth passwordless (router ya trae prefix="/api/auth")
app.include_router(auth_router)

# Rutas de negocio bajo /api
app.include_router(process_router, prefix="/api")    # /api/process
app.include_router(status_router, prefix="/api")     # /api/status

# Endpoints “protegidos” (o al menos bajo /api)
app.include_router(artifacts_router, prefix="/api")  # /api/artifacts/{id}/{name}
app.include_router(history_router, prefix="/api")    # /api/history/{id}[...]

app.include_router(private_demo_router, prefix="/api")

# Help / soporte (router ya trae prefix="/api/help")
app.include_router(help_router)

# Endpoints públicos (solo si los flags lo permiten; útiles en dev/tests)
if ARTIFACTS_PUBLIC:
    app.include_router(artifacts_router)             # /artifacts/{id}/{name}
if HISTORY_PUBLIC:
    app.include_router(history_router)               # /history/{id}[...]
