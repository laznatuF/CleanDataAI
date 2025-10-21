from __future__ import annotations
from typing import Optional, Dict

from app.infrastructure import users_repo_fs as repo


def get_or_create_user(email: str, name: str = "") -> Dict:
    return repo.ensure_user(email, name)


def get_user_by_id(uid: str) -> Optional[Dict]:
    return repo.get_by_id(uid)


def increment_process_count(uid: str) -> None:
    u = repo.get_by_id(uid)
    if not u:
        return
    u["process_count"] = int(u.get("process_count", 0)) + 1
    repo.upsert_user(u)
