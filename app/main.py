from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import BASE_DIR

app = FastAPI(title="CleanDataIA")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/runs", StaticFiles(directory=str(BASE_DIR / "runs")), name="runs")

@app.get("/")
def root():
    return {"message": "CleanDataIA API - MVP listo para empezar"}
