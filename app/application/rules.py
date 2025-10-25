# app/application/rules.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import json

from app.core.config import RUNS_DIR, BASE_DIR

# Intentamos soportar YAML si está instalado; si no, funcionará solo JSON
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def _safe_read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("El JSON de reglas debe ser un objeto (dict) en la raíz.")
    return data


def _safe_read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError(
            f"Se encontró {path.name} pero PyYAML no está instalado. "
            f"Instala con: pip install pyyaml"
        )
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("El YAML de reglas debe ser un objeto (dict) en la raíz.")
    return data


def _find_rules_file(proc_id: str) -> Tuple[Optional[Path], Optional[str]]:
    """
    Busca reglas en orden:
      1) runs/{id}/input/rules.yaml
      2) runs/{id}/input/rules.yml
      3) runs/{id}/input/rules.json
      4) BASE_DIR/data/rules.yaml / rules.yml / rules.json (fallback global)
    Devuelve (path, fmt) donde fmt ∈ {"yaml","json"} o (None, None) si no hay.
    """
    candidates = [
        (RUNS_DIR / proc_id / "input" / "rules.yaml", "yaml"),
        (RUNS_DIR / proc_id / "input" / "rules.yml",  "yaml"),
        (RUNS_DIR / proc_id / "input" / "rules.json", "json"),
        (BASE_DIR / "data" / "rules.yaml", "yaml"),
        (BASE_DIR / "data" / "rules.yml",  "yaml"),
        (BASE_DIR / "data" / "rules.json", "json"),
    ]
    for p, fmt in candidates:
        if p.exists():
            return p, fmt
    return None, None


def load_rules_for_process(proc_id: str) -> Dict[str, Any]:
    """
    Carga reglas YAML/JSON para el proceso. Si no existen, devuelve {}.
    Es tolerante a errores: levanta excepciones claras si el formato es inválido.
    """
    path, fmt = _find_rules_file(proc_id)
    if not path:
        return {}
    if fmt == "json":
        return _safe_read_json(path)
    else:
        return _safe_read_yaml(path)


def describe_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Devuelve un resumen simple de las reglas (para logs/bitácora).
    """
    impute_by_col = rules.get("impute", {}).get("by_column", {}) if isinstance(rules.get("impute"), dict) else {}
    dedup_keys = rules.get("dedup", {}).get("keys", []) if isinstance(rules.get("dedup"), dict) else []
    fmt_dates = rules.get("format", {}).get("dates", {}) if isinstance(rules.get("format"), dict) else {}
    fmt_date_cols = fmt_dates.get("columns", []) if isinstance(fmt_dates, dict) else []
    return {
        "has_rules": bool(rules),
        "impute_columns": sorted(list(impute_by_col.keys())) if isinstance(impute_by_col, dict) else [],
        "dedup_keys": dedup_keys if isinstance(dedup_keys, list) else [],
        "date_columns": fmt_date_cols if isinstance(fmt_date_cols, list) else [],
    }
