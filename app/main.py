# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import RUNS_DIR
from app.api.status import router as status_router
from app.api.process import router as process_router

app = FastAPI(title="CleanDataAI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.mount("/runs", StaticFiles(directory=str(RUNS_DIR)), name="runs")

# CLAVE: prefijo /api
app.include_router(process_router, prefix="/api")
app.include_router(status_router,  prefix="/api")
