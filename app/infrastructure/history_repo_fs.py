# app/infrastructure/history_repo_fs.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import RUNS_DIR

HISTORY_FILENAME = "history.jsonl"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def history_path(proc_id: str) -> Path:
    """
    Ruta del JSONL de bitácora para un proceso: runs/{id}/history.jsonl
    """
    return RUNS_DIR / proc_id / HISTORY_FILENAME


def append_history(proc_id: str, event: Dict[str, Any]) -> None:
    """
    Agrega un evento a runs/{id}/history.jsonl como una línea JSON.
    """
    p = history_path(proc_id)
    p.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(event)
    payload.setdefault("ts", _now_iso())

    line = json.dumps(payload, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_history(proc_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lee y parsea el history.jsonl. Si limit>0, devuelve los últimos N eventos.
    """
    p = history_path(proc_id)
    if not p.exists():
        return []

    items: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                # línea corrupta; se ignora
                continue

    if limit and limit > 0:
        return items[-limit:]
    return items


def history_file_for_download(proc_id: str) -> Path:
    """
    Devuelve la ruta del archivo history.jsonl para descarga directa.
    """
    return history_path(proc_id)
