# app/infrastructure/users.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Optional, Dict
from email_validator import validate_email, EmailNotValidError

from app.core.config import BASE_DIR

USERS_DB = Path(BASE_DIR) / "data"
USERS_DB.mkdir(parents=True, exist_ok=True)
USERS_FILE = USERS_DB / "users.json"

@dataclass
class User:
    id: str
    email: str
    name: str = ""
    plan: str = "free"   # free / pro / enterprise

def _load_users() -> Dict[str, dict]:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}

def _save_users(data: Dict[str, dict]) -> None:
    USERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _ensure_email(email: str) -> str:
    try:
        return validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as e:
        raise ValueError(str(e)) from e

def get_user_by_email(email: str) -> Optional[User]:
    email = _ensure_email(email)
    data = _load_users()
    # índice por email
    for u in data.values():
        if u.get("email") == email:
            return User(**u)
    return None

def get_user_by_id(uid: str) -> Optional[User]:
    data = _load_users()
    node = data.get(uid)
    return User(**node) if node else None

def get_or_create_user(email: str, name: str = "") -> User:
    email = _ensure_email(email)
    existing = get_user_by_email(email)
    if existing:
        # permite actualizar nombre si viene vacío antes
        if name and not existing.name:
            existing.name = name
            upsert_user(existing)
        return existing
    import uuid
    new_u = User(id=str(uuid.uuid4()), email=email, name=name or email.split("@")[0])
    upsert_user(new_u)
    return new_u

def upsert_user(u: User) -> None:
    data = _load_users()
    data[u.id] = asdict(u)
    _save_users(data)
