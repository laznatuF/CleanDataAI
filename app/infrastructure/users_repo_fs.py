from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from app.core.config import BASE_DIR
from app.infrastructure.files import read_json, write_json


# Archivo de usuarios (fuera del paquete app/)
USERS_FILE = BASE_DIR / "data" / "users.json"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_all() -> List[Dict]:
    """
    Carga la lista de usuarios desde JSON.
    - Soporta formato lista (actual) y, por compatibilidad,
      un dict {id: user} antiguo (lo convierte a lista).
    """
    data = read_json(USERS_FILE)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def _save_all(rows: List[Dict]) -> None:
    """Escritura atómica del JSON (usa .tmp + replace)."""
    write_json(USERS_FILE, rows)


def get_by_email(email: str) -> Optional[Dict]:
    email_low = (email or "").strip().lower()
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
    """
    Inserta/actualiza un usuario por 'id'.
    Asegura 'updated_at'. No genera id nuevo aquí.
    """
    rows = _load_all()
    idx = next((i for i, r in enumerate(rows) if r.get("id") == user.get("id")), -1)
    user["updated_at"] = _now()
    if idx >= 0:
        rows[idx] = user
    else:
        rows.append(user)
    _save_all(rows)
    return user


def ensure_user(email: str, name: str = "") -> Dict:
    """
    Devuelve el usuario por email; si no existe, lo crea con plan 'free'
    y process_count = 0.
    """
    u = get_by_email(email)
    if u:
        return u

    obj = {
        "id": uuid4().hex,
        "email": (email or "").strip().lower(),
        "name": name or "",
        "plan": "free",
        "created_at": _now(),
        "updated_at": _now(),
        "process_count": 0,
    }
    return upsert_user(obj)





##MPV
