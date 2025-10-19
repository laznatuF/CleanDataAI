# app/main.py
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import RUNS_DIR
from app.api.status import router as status_router
from app.api.process import router as process_router

app = FastAPI(title="CleanDataAI")

# CORS abierto (ajusta en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

# ---------- Saludos/meta ----------
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

# Saludo bajo /api/ (para el ping del frontend)
@app.get("/api/", tags=["meta"])
def api_root():
    return {
        "name": "CleanDataAI API",
        "status": "ok",
        "time": _now_iso(),
        "message": "API disponible",
        "base": "/api",
    }

# Alias /api/health → /health
@app.get("/api/health", tags=["meta"])
def api_health_alias():
    return {"ok": True, "time": _now_iso()}

# ---------- Estáticos ----------
# EXPUESTO SOLO PARA DESARROLLO (mejor proteger en prod)
app.mount("/runs", StaticFiles(directory=str(RUNS_DIR)), name="runs")

# ---------- Routers de negocio bajo /api ----------
app.include_router(process_router, prefix="/api")
app.include_router(status_router,  prefix="/api")
