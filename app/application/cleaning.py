# app/application/cleaning.py
from __future__ import annotations

from typing import Dict, Any, Tuple, List
import re
import numpy as np
import pandas as pd


# Tasas de cambio referenciales para normalización
DEFAULT_EXCHANGE_RATES = {
    "USD": 950.0,  # Dólar a Peso (aprox)
    "EUR": 1020.0, # Euro a Peso (aprox)
    "CLP": 1.0,    # Base
    "$": 1.0,      # Asumimos moneda local si es símbolo solo
}


def _mode(series: pd.Series):
    try:
        m = series.mode(dropna=True)
        if len(m) > 0:
            return m.iloc[0]
    except Exception:
        pass
    return np.nan


def _fix_split_names_and_shift(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """
    [NUEVO] Detecta y corrige el error de "Nombre dividido por coma".
    Si columnas como 'DateofHire' o 'Salary' tienen texto (Raza, Nombre),
    fusiona col 0+1 y desplaza todo a la izquierda.
    """
    out = df.copy()
    cols = list(out.columns)
    if len(cols) < 3:
        return out, False

    # Heurística: Buscamos una columna que se llame FECHA o DINERO pero tenga TEXTO puro
    suspicious_col_idx = -1
    for i, col in enumerate(cols):
        c_lower = col.lower()
        if "date" in c_lower or "fecha" in c_lower or "salary" in c_lower or "sueldo" in c_lower:
            # Muestreamos para ver si tiene basura (letras puras)
            sample = out[col].dropna().astype(str).head(50)
            # Si >50% son letras (y no fechas ni números), es sospechoso
            # Regex: solo letras y espacios, sin números
            is_text = sample.str.match(r'^[a-zA-Z\s]+$').mean() > 0.5
            if is_text:
                suspicious_col_idx = i
                break
    
    # Si encontramos desplazamiento (y hay espacio a la izquierda para fusionar)
    if suspicious_col_idx > 1:
        # 1. Fusionar Col 0 y Col 1 (Apellido, Nombre)
        c0, c1 = cols[0], cols[1]
        out[c0] = out[c0].astype(str) + ", " + out[c1].astype(str)
        
        # 2. Desplazar todo a la izquierda desde la col 1
        for i in range(1, len(cols) - 1):
            out[cols[i]] = out[cols[i+1]]
            
        # 3. Eliminar la última columna (que ahora sobra)
        out = out.drop(columns=[cols[-1]])
        
        return out, True

    return out, False


def _parse_money_value(val: Any) -> Tuple[float | None, str | None]:
    """Toma valor sucio ($ 10.000) y devuelve (10000.0, '$')."""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return None, None

    # 1. Extraer moneda
    curr_match = re.search(r'([A-Z]{3}|[\$\€\£\¥])', s)
    currency = curr_match.group(0) if curr_match else None

    # 2. Limpiar número
    clean_str = re.sub(r'[^\d.,-]', '', s)
    if not clean_str:
        return None, currency

    try:
        # Heurística decimal
        if ',' in clean_str and '.' in clean_str:
            if clean_str.rfind(',') > clean_str.rfind('.'): # 1.000,00
                clean_str = clean_str.replace('.', '').replace(',', '.')
            else: # 1,000.00
                clean_str = clean_str.replace(',', '')
        elif ',' in clean_str:
            if clean_str.count(',') > 1: # 1,000,000
                clean_str = clean_str.replace(',', '')
            elif len(clean_str) - clean_str.rfind(',') <= 3: # 10,5
                clean_str = clean_str.replace(',', '.')
            else:
                clean_str = clean_str.replace(',', '')
        
        num = float(clean_str)
        return num, currency
    except ValueError:
        return None, currency


def _clean_money_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """Detecta columnas de dinero sucio y crea _numerico + _divisa."""
    out = df.copy()
    new_cols_created = []
    money_pattern = re.compile(r'[\$\€\£]|USD|EUR|CLP|MXN|ARS', re.IGNORECASE)

    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]): continue

        sample = out[col].dropna().astype(str).head(20)
        if sample.empty: continue
        
        if sample.apply(lambda x: bool(money_pattern.search(x))).mean() > 0.3:
            parsed = out[col].apply(_parse_money_value)
            col_num = f"{col}_numerico"
            col_div = f"{col}_divisa"
            
            out[col_num] = parsed.apply(lambda x: x[0])
            divisas = parsed.apply(lambda x: x[1])
            
            if divisas.notna().any():
                out[col_div] = divisas
                new_cols_created.append(col_div)
            new_cols_created.append(col_num)

    return out, new_cols_created


def _normalize_currency(df: pd.DataFrame, col_amount: str, col_currency: str) -> pd.Series:
    """Convierte a moneda base (CLP) según tasa."""
    def convert(row):
        amt = row[col_amount]
        curr = str(row[col_currency]).upper().strip()
        if pd.isna(amt): return np.nan
        rate = DEFAULT_EXCHANGE_RATES.get(curr, 1.0)
        if curr == "$": rate = 1.0 
        return amt * rate
    return df.apply(convert, axis=1)


def _apply_impute_by_column(df: pd.DataFrame, rules: Dict[str, Any]) -> Dict[str, int]:
    """Imputación estándar."""
    counts: Dict[str, int] = {}
    impute = rules.get("impute") or {}
    by_col = impute.get("by_column", {}) or {}
    default = impute.get("default", {}) or {}

    def _fill(col, strat, val=None):
        s = df[col]
        if not s.isna().any(): return 0
        if strat == "mean":
            try: fillv = pd.to_numeric(s, errors="coerce").mean()
            except: fillv = np.nan
        elif strat == "mode": fillv = _mode(s)
        elif strat == "value": fillv = val
        else: return 0
        
        df[col] = s.fillna(fillv)
        return int(s.isna().sum())

    for col, cfg in by_col.items():
        if col not in df: continue
        strat = str(cfg.get("strategy", "")).lower().strip()
        cnt = _fill(col, "value", cfg.get("value")) if strat == "value" else _fill(col, strat)
        if cnt: counts[col] = counts.get(col, 0) + cnt

    def_num = str(default.get("numeric", "")).lower().strip()
    def_txt = str(default.get("text", "")).lower().strip()
    
    for col in df.columns:
        if col in by_col: continue
        s = df[col]
        if s.isna().any():
            if pd.api.types.is_numeric_dtype(s):
                if def_num: 
                    cnt = _fill(col, def_num, default.get("value") if def_num=="value" else None)
                    if cnt: counts[col] = counts.get(col, 0) + cnt
            elif def_txt:
                cnt = _fill(col, def_txt, default.get("value") if def_txt=="value" else None)
                if cnt: counts[col] = counts.get(col, 0) + cnt

    return counts


def clean_dataframe(df: pd.DataFrame, rules: Dict[str, Any] | None = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Limpieza completa:
      1. Reparación estructural (Shift de columnas) [NUEVO]
      2. Trim de espacios
      3. Conversión Booleana
      4. Normalización de Fechas
      5. Inteligencia de Monedas
      6. Imputación
      7. Deduplicación
    """
    out = df.copy()
    summary: Dict[str, Any] = {}

    # 0) Reparación Estructural (RR.HH. Fix)
    # Detectamos si hay columnas desplazadas por comas en el nombre
    out, shifted = _fix_split_names_and_shift(out)
    if shifted:
        summary["structural_repair"] = "Merged column 0+1 and shifted left"

    # 1) Trim de objetos
    trimmed_cols = []
    for c in out.select_dtypes(include=["object"]).columns:
        out[c] = out[c].astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})
        trimmed_cols.append(c)
    summary["trimmed_cols"] = trimmed_cols

    # 2) Booleans comunes
    bool_map = {"true": True, "false": False, "1": True, "0": False, "sí": True, "si": True, "no": False}
    bool_cols = []
    for c in out.columns:
        if out[c].dropna().astype(str).str.lower().isin(bool_map.keys()).all():
            out[c] = out[c].astype(str).str.lower().map(bool_map)
            bool_cols.append(c)
    summary["bool_cols"] = bool_cols

    # 3) Fechas básicas
    date_cols = []
    for c in out.columns:
        s = out[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s): continue
        # Regex relajado para fechas
        if s.dropna().astype(str).str.match(r"^\d{2,4}[-/]\d{1,2}[-/]\d{1,4}").mean() > 0.6:
            out[c] = pd.to_datetime(s, errors="coerce").dt.date.astype(str)
            date_cols.append(c)
    summary["date_cols"] = date_cols

    # 4) Limpieza de Monedas + Normalización (Ventas Fix)
    out, money_cols_created = _clean_money_columns(out)
    summary["money_cols_extracted"] = money_cols_created

    normalized_cols = []
    for col in out.columns:
        if col.endswith("_numerico"):
            base_name = col.replace("_numerico", "")
            col_divisa = f"{base_name}_divisa"
            if col_divisa in out.columns:
                col_unified = f"{base_name}_total_clp"
                out[col_unified] = _normalize_currency(out, col, col_divisa)
                normalized_cols.append(col_unified)
    
    if normalized_cols:
        summary["currency_normalized_cols"] = normalized_cols

    # 5) Reglas de imputación
    rules = rules or {}
    impute_counts = _apply_impute_by_column(out, rules)
    if impute_counts: summary["imputed"] = impute_counts

    # 6) Deduplicación
    dedup_cfg = rules.get("dedup", {}) if isinstance(rules, dict) else {}
    keys = dedup_cfg.get("keys", []) if isinstance(dedup_cfg, dict) else []
    before = len(out)
    if isinstance(keys, list) and len(keys) > 0:
        subset = [k for k in keys if k in out.columns]
        out = out.drop_duplicates(subset=subset, keep="first")
        summary["dedup_keys_used"] = subset
    else:
        out = out.drop_duplicates(keep="first")
        summary["dedup_keys_used"] = []
    
    after = len(out)
    summary["dropped_duplicates"] = int(before - after)

    return out, summary