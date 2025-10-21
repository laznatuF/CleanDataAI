from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from app.core.config import BASE_DIR

USERS_FILE = BASE_DIR / "data" / "users.json"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_all() -> List[Dict]:
    if not USERS_FILE.exists():
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []


def _save_all(rows: List[Dict]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def get_by_email(email: str) -> Optional[Dict]:
    email_low = email.strip().lower()
    for u in _load_all():
        if str(u.get("email", "")).lower() == email_low:
            return u
    return None


def get_by_id(uid: str) -> Optional[Dict]:
    for u in _load_all():
        if u.get("id") == uid:
            return u
    return None


def upsert_user(user: Dict) -> Dict:
    rows = _load_all()
    idx = next((i for i, r in enumerate(rows) if r.get("id") == user["id"]), -1)
    user["updated_at"] = _now()
    if idx >= 0:
        rows[idx] = user
    else:
        rows.append(user)
    _save_all(rows)
    return user


def ensure_user(email: str, name: str = "") -> Dict:
    u = get_by_email(email)
    if u:
        return u
    # crear nuevo
    obj = {
        "id": uuid4().hex,
        "email": email.strip().lower(),
        "name": name or "",
        "plan": "free",
        "created_at": _now(),
        "updated_at": _now(),
        "process_count": 0,
    }
    return upsert_user(obj)
