# app/services/dates.py
from __future__ import annotations
from typing import Dict
import pandas as pd

# Formatos aceptados (añade/quita según tu realidad)
ACCEPTED_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d")


def parse_dates_series(s: pd.Series) -> pd.Series:
    """
    Intenta parsear una Series de strings/objetos a datetime usando una lista finita de formatos.
    Devuelve una Series dtype datetime64[ns] con NaT cuando no calza ningún formato.
    """
    # Normalizamos strings vacíos a NaN y recortamos espacios
    s2 = s.astype("string").str.strip().replace({"": None})
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")

    # Vamos probando los formatos permitidos; el primero que calce gana
    mask_left = s2.notna()
    for fmt in ACCEPTED_DATE_FORMATS:
        m = mask_left & out.isna()
        if not m.any():
            break
        out.loc[m] = pd.to_datetime(s2.loc[m], format=fmt, errors="coerce")

    return out


def normalize_dates_in_df(df: pd.DataFrame, min_success_ratio: float = 0.5) -> Dict[str, str]:
    """
    Recorre columnas de texto/objeto e intenta parsearlas como fecha con parse_dates_series.
    Si ≥ min_success_ratio de los valores NO nulos se parsea, la columna se considera fecha y
    se normaliza a string ISO 'YYYY-MM-DD'.

    Devuelve un dict {col: "date"} con las columnas que fueron normalizadas.
    """
    inferred: Dict[str, str] = {}

    for col in df.columns:
        s = df[col]
        # Solo intentamos en columnas tipo texto/objeto
        if not (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)):
            continue

        dt = parse_dates_series(s)
        ok = int(dt.notna().sum())
        total = int(s.notna().sum())
        if total == 0:
            continue

        ratio = ok / total
        if ratio >= min_success_ratio:
            # Normalizamos a ISO (sin zona horaria)
            df[col] = dt.dt.strftime("%Y-%m-%d")
            inferred[col] = "date"

    return inferred
