# app/main.py
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import RUNS_DIR, FRONTEND_ORIGIN
from app.api.status import router as status_router
from app.api.process import router as process_router
from app.api.auth_pwless import router as auth_router  # passwordless: /api/auth/*

app = FastAPI(title="CleanDataAI")

# ---------- CORS (imprescindible allow_credentials para cookies) ----------
allowed_origins = {
    FRONTEND_ORIGIN.rstrip("/"),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,  # necesario para cookies HttpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

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
# Nota: en producción conviene servir /runs por un servidor estático o vía endpoint protegido.
app.mount("/runs", StaticFiles(directory=str(RUNS_DIR)), name="runs")

# ---------- Routers ----------
# Auth passwordless (ya viene con prefix="/api/auth")
app.include_router(auth_router)

# Rutas de negocio bajo /api
app.include_router(process_router, prefix="/api")
app.include_router(status_router,  prefix="/api")
