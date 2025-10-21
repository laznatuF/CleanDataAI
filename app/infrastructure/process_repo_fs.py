from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

from app.core.config import RUNS_DIR

def status_path(proc_id: str) -> Path:
    return RUNS_DIR / proc_id / "status.json"

def read_status(proc_id: str) -> Dict[str, Any]:
    p = status_path(proc_id)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def write_status(proc_id: str, data: Dict[str, Any]) -> None:
    p = status_path(proc_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
