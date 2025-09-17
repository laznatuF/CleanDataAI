from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import BASE_DIR
from app.api.process import router as process_router
from app.api.status import router as status_router

app = FastAPI(title="CleanDataIA")

# Sirve /static y /runs desde la raíz (porque BASE_DIR apunta a la raíz)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/runs", StaticFiles(directory=str(BASE_DIR / "runs")), name="runs")

# Conectar endpoints
app.include_router(process_router)
app.include_router(status_router)

@app.get("/")
def root():
    return {"message": "CleanDataIA API - MVP listo para empezar"}

