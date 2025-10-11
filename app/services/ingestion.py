# app/services/ingestion.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    seen = {}
    for c in df.columns:
        # minúsculas, trim y colapso de espacios
        nc = " ".join(str(c).strip().lower().split())
        if nc in seen:
            seen[nc] += 1
            nc = f"{nc}_{seen[nc]}"
        else:
            seen[nc] = 0
        cols.append(nc)
    df.columns = cols
    return df

def read_csv_with_fallback(p: Path) -> pd.DataFrame:
    # RFN69: fallback latin-1
    try:
        return pd.read_csv(p, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding="latin-1")

def read_excel_any(p: Path) -> pd.DataFrame:
    suf = p.suffix.lower()
    if suf == ".xlsx":
        return pd.read_excel(p, engine="openpyxl")
    if suf == ".xls":
        # xlrd>=2 no soporta xls; requiere xlrd<2.0 instalado
        return pd.read_excel(p, engine="xlrd")
    if suf == ".ods":
        # requiere odfpy
        return pd.read_excel(p, engine="odf")
    raise ValueError(f"Extensión no soportada para Excel/ODS: {suf}")

def read_dataframe(p: Path) -> pd.DataFrame:
    if p.suffix.lower() == ".csv":
        df = read_csv_with_fallback(p)
    else:
        df = read_excel_any(p)

    df = _normalize_headers(df)  # RFN8–10
    return df
