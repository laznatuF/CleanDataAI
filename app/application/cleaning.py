# app/application/cleaning.py
from __future__ import annotations

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd


def _mode(series: pd.Series):
    try:
        m = series.mode(dropna=True)
        if len(m) > 0:
            return m.iloc[0]
    except Exception:
        pass
    return np.nan


def _apply_impute_by_column(df: pd.DataFrame, rules: Dict[str, Any]) -> Dict[str, int]:
    """
    Aplica imputación por columna según reglas:
      rules:
        impute:
          by_column:
            monto:   {strategy: mean}
            genero:  {strategy: mode}
            pais:    {strategy: value, value: "CL"}
          default:
            numeric: mean|mode|value
            text:    mode|value|none
            value:   <valor si strategy==value>

    Devuelve dict con conteo de imputaciones por columna.
    """
    counts: Dict[str, int] = {}
    impute = rules.get("impute") if isinstance(rules, dict) else None
    if not isinstance(impute, dict):
        return counts

    by_col = impute.get("by_column", {})
    default = impute.get("default", {})
    if not isinstance(by_col, dict):
        by_col = {}
    if not isinstance(default, dict):
        default = {}

    # Helper para estrategia
    def _fill(col: str, strat: str, val: Any | None = None) -> int:
        s = df[col]
        na_mask = s.isna()
        if not na_mask.any():
            return 0

        if strat == "mean":
            try:
                fillv = pd.to_numeric(s, errors="coerce").mean()
            except Exception:
                fillv = np.nan
        elif strat == "mode":
            fillv = _mode(s)
        elif strat == "value":
            fillv = val
        elif strat in ("none", "skip", None):
            return 0
        else:
            # estrategia desconocida: no tocar
            return 0

        new_s = s.copy()
        new_s[na_mask] = fillv
        df[col] = new_s
        return int(na_mask.sum())

    # 1) Reglas explícitas por columna
    for col, cfg in by_col.items():
        if col not in df.columns or not isinstance(cfg, dict):
            continue
        strat = str(cfg.get("strategy", "")).lower().strip()
        if strat == "value":
            cnt = _fill(col, "value", cfg.get("value"))
        else:
            cnt = _fill(col, strat)
        if cnt:
            counts[col] = counts.get(col, 0) + cnt

    # 2) Reglas por defecto
    def_num = str(default.get("numeric", "")).lower().strip()
    def_txt = str(default.get("text", "")).lower().strip()
    def_val = default.get("value")

    for col in df.columns:
        if col in by_col:
            continue
        s = df[col]
        if s.isna().any():
            if pd.api.types.is_numeric_dtype(s):
                if def_num:
                    cnt = _fill(col, def_num, def_val if def_num == "value" else None)
                    if cnt:
                        counts[col] = counts.get(col, 0) + cnt
            else:
                if def_txt:
                    cnt = _fill(col, def_txt, def_val if def_txt == "value" else None)
                    if cnt:
                        counts[col] = counts.get(col, 0) + cnt

    return counts


def clean_dataframe(df: pd.DataFrame, rules: Dict[str, Any] | None = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Limpieza mínima:
      - Trim de strings
      - Conversión leve de booleanos tipo "sí/no", "true/false", "0/1"
      - Normalización de fechas básica (si ya vienen en formato str ISO-like)
      - (Reglas) Imputación por media/moda/valor fijo
      - (Reglas) Deduplicación por claves si se especifica; si no, drop_duplicates global
    Devuelve (df_limpio, clean_summary).
    """
    out = df.copy()

    # 0) Trim de objetos
    for c in out.select_dtypes(include=["object"]).columns:
        out[c] = out[c].astype(str).str.strip().replace({"": np.nan})

    # 1) Booleans comunes
    bool_map = {"true": True, "false": False, "1": True, "0": False, "sí": True, "si": True, "no": False}
    for c in out.columns:
        if out[c].dropna().astype(str).str.lower().isin(bool_map.keys()).all():
            out[c] = out[c].astype(str).str.lower().map(bool_map)

    # 2) Fechas básicas (si parecen ISO-like)
    for c in out.columns:
        s = out[c]
        if s.dropna().astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").mean() > 0.6:
            out[c] = pd.to_datetime(s, errors="coerce").dt.date.astype(str)

    summary: Dict[str, Any] = {}

    # 3) Reglas de imputación (RFN11–14)
    rules = rules or {}
    impute_counts = _apply_impute_by_column(out, rules)
    if impute_counts:
        summary["imputed"] = impute_counts

    # 4) Deduplicación (RFN19 parcial + RFN52 con conteo) — por claves si vienen en reglas
    dedup_cfg = rules.get("dedup", {}) if isinstance(rules, dict) else {}
    keys = dedup_cfg.get("keys", []) if isinstance(dedup_cfg, dict) else []
    before = len(out)
    if isinstance(keys, list) and len(keys) > 0:
        out = out.drop_duplicates(subset=[k for k in keys if k in out.columns], keep="first")
        summary["dedup_keys_used"] = [k for k in keys if k in out.columns]
    else:
        out = out.drop_duplicates(keep="first")
        summary["dedup_keys_used"] = []
    after = len(out)
    summary["dropped_duplicates"] = int(before - after)

    return out, summary
