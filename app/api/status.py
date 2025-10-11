# app/api/status.py
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from app.core.config import RUNS_DIR
from app.utils.files import read_json

router = APIRouter()

STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"]

SLUG_TO_TITLE = {
    "ingesta": "Subir archivo",
    "subir": "Subir archivo",
    "upload": "Subir archivo",
    "perfilado": "Perfilado",
    "profiling": "Perfilado",
    "limpieza": "Limpieza",
    "cleaning": "Limpieza",
    "dashboard": "Dashboard",
    "reporte": "Reporte",
    "report": "Reporte",
}

FINISHED = {"ok", "done", "success", "completed", "finished"}
RUNNING = {"running", "in_progress", "processing"}
FAILED = {"failed", "error"}
PENDING = {"pending", "queued", "waiting"}

def normalize_status(s: Optional[str]) -> str:
    s = (s or "").strip().lower()
    if s in FINISHED: return "ok"
    if s in RUNNING:  return "running"
    if s in FAILED:   return "failed"
    if s in PENDING or not s: return "pending"
    return s

def normalize_name(name: Optional[str]) -> str:
    n = (name or "").strip()
    key = n.lower()
    return SLUG_TO_TITLE.get(key, n)

def upgrade_steps(raw_steps: Any, current_step: Optional[str] = None) -> List[Dict[str, str]]:
    current_title = normalize_name(current_step) if current_step else None
    if isinstance(raw_steps, list) and raw_steps and isinstance(raw_steps[0], dict):
        mapped: Dict[str, str] = {}
        for item in raw_steps:
            name = normalize_name(item.get("name") or item.get("step") or item.get("title"))
            status = normalize_status(item.get("status"))
            mapped[name] = status
        out: List[Dict[str, str]] = []
        for stage in STAGES:
            st = mapped.get(stage, "pending")
            if stage == current_title and st == "pending":
                st = "running"
            out.append({"name": stage, "status": st})
        return out

    if isinstance(raw_steps, list) and (not raw_steps or isinstance(raw_steps[0], str)):
        finished_titles = {normalize_name(x) for x in (raw_steps or [])}
        out: List[Dict[str, str]] = []
        for stage in STAGES:
            if stage in finished_titles:
                out.append({"name": stage, "status": "ok"})
            elif current_title and stage == current_title:
                out.append({"name": stage, "status": "running"})
            else:
                out.append({"name": stage, "status": "pending"})
        return out

    return [
        {
            "name": stage,
            "status": "running" if current_title and stage == current_title else "pending",
        }
        for stage in STAGES
    ]

def infer_progress(steps: List[Dict[str, str]]) -> int:
    if not steps: return 0
    score = 0.0
    for s in steps:
        st = s.get("status")
        if st == "ok": score += 1.0
        elif st == "running": score += 0.5
    return max(0, min(100, int(round(100 * score / len(steps)))))

@router.get("/status/{process_id}")
def get_status(process_id: str):
    status_path = RUNS_DIR / process_id / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Proceso no encontrado")

    data = read_json(status_path) or {}
    data["status"] = normalize_status(data.get("status"))
    if data.get("current_step"):
        data["current_step"] = normalize_name(data["current_step"])
    data["steps"] = upgrade_steps(data.get("steps"), current_step=data.get("current_step"))

    if "progress" not in data or data.get("progress") is None:
        data["progress"] = infer_progress(data["steps"])
    try:
        p = int(data["progress"])
        data["progress"] = max(0, min(100, p))
    except Exception:
        data["progress"] = infer_progress(data["steps"])
    return data
