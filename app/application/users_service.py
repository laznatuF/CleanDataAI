# app/application/users_service.py
from __future__ import annotations

from typing import Optional, Dict

from app.infrastructure import users_repo_fs as repo

# Planes permitidos (alineado con tu frontend: free | standard | pro)
ALLOWED_PLANS = {"free", "standard", "pro"}


def _normalize_plan(plan: str) -> str:
    """
    Normaliza aliases y valida planes.
    Acepta equivalencias típicas (normal/estándar -> standard).
    """
    p = (plan or "").strip().lower()

    aliases = {
        "normal": "standard",
        "estandar": "standard",
        "estándar": "standard",
        "basic": "standard",
        "starter": "standard",
        "premium": "pro",
    }
    p = aliases.get(p, p)

    if p not in ALLOWED_PLANS:
        raise ValueError(f"Plan inválido: {plan}")

    return p


def get_or_create_user(email: str, name: str = "") -> Dict:
    """
    Compat: usado por auth_pwless.py.
    Si no existe, crea con plan=free.
    """
    return repo.ensure_user(email, name)


def get_user_by_id(uid: str) -> Optional[Dict]:
    return repo.get_by_id(uid)


def register_user(email: str, name: str = "", plan: str = "free") -> Dict:
    """
    Registro local (demo):
    - crea o recupera el usuario (ensure_user)
    - setea/actualiza name + plan
    - persiste en users.json
    """
    u = repo.ensure_user(email, name)

    # Actualiza nombre si viene (aunque sea "")
    u["name"] = (name or "").strip()

    # Setea plan validado
    u["plan"] = _normalize_plan(plan)

    return repo.upsert_user(u)


def set_user_plan(uid: str, plan: str) -> Optional[Dict]:
    """
    Cambia el plan de un usuario existente y persiste.
    """
    u = repo.get_by_id(uid)
    if not u:
        return None

    u["plan"] = _normalize_plan(plan)
    return repo.upsert_user(u)


def increment_process_count(uid: str) -> None:
    """
    Incrementa el contador de procesos del usuario.
    """
    u = repo.get_by_id(uid)
    if not u:
        return
    u["process_count"] = int(u.get("process_count", 0)) + 1
    repo.upsert_user(u)
