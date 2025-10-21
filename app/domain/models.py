from __future__ import annotations
from pydantic import BaseModel, EmailStr
from typing import Optional


class User(BaseModel):
    id: str
    email: EmailStr
    name: str = ""
    plan: str = "free"         # free | pro | enterprise (ejemplo)
    created_at: str
    updated_at: str
    process_count: int = 0     # cuántas ejecuciones ha hecho


class ProcessStatus(BaseModel):
    id: str
    filename: str
    status: str                 # queued | running | completed | failed
    progress: int               # 0..100
    current_step: str
    steps: list
    metrics: dict = {}
    artifacts: dict = {}
    updated_at: str
    error: Optional[str] = None
