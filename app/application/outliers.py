# app/application/outliers.py
from __future__ import annotations

from typing import Tuple, Dict, List, Any
import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Falta scikit-learn para la detección de outliers. "
        "Instala con: pip install scikit-learn"
    ) from e


def _safe_float(x: Any, default: float = 0.05) -> float:
    """Convierte a float sin explotar con NaT/NaN/None/strings raros."""
    try:
        if x is None:
            return default
        # Manejo específico para pd.NA (NAType)
        if x is pd.NA:
            return default
        try:
            if pd.isna(x):
                return default
        except Exception:
            pass
        return float(x)
    except Exception:
        return default


def _select_numeric_columns(df: pd.DataFrame) -> List[str]:
    """
    Elige columnas numéricas con al menos 2 valores no nulos distintos.
    """
    # Forzamos conversión para evitar tipos mixtos que confundan a select_dtypes
    # Solo consideramos columnas que YA son numéricas
    cols = []
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            # Validar que tenga varianza (al menos 2 valores distintos)
            if df[c].dropna().nunique() >= 2:
                cols.append(c)
    return cols


def apply_isolation_forest(
    df: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Aplica IsolationForest sobre columnas numéricas.
    BLINDADO: Convierte explícitamente todos los nulos modernos (NAType) a np.nan
    antes de pasar a Scikit-Learn.
    """
    out = df.copy()

    used_cols = _select_numeric_columns(out)

    # Contamination robusta
    cont = _safe_float(contamination, default=0.05)
    if not (0 < cont < 0.5):
        cont = 0.05

    try:
        rs = int(random_state)
    except Exception:
        rs = 42

    summary: Dict[str, Any] = {
        "used_columns": used_cols,
        "contamination": float(cont),
        "random_state": rs,
        "outliers": 0,
        "total": int(len(out)),
        "ratio": 0.0,
        "skipped": False,
    }

    if len(out) == 0 or len(used_cols) == 0:
        out["is_outlier"] = False
        out["outlier_score"] = np.nan
        out["outlier_method"] = "isolation_forest"
        summary["skipped"] = True
        return out, summary

    # --- ZONA DE SEGURIDAD CRÍTICA ---
    # Extraemos solo numéricas
    X_df = out[used_cols].copy()
    
    # 1. Reemplazamos Infinitos por NaN
    X_df = X_df.replace([np.inf, -np.inf], np.nan)
    
    # 2. CONVERSIÓN NUCLEAR:
    # Transformamos todo a float de numpy, forzando que pd.NA se vuelva np.nan
    # Esto evita el error "float() argument ... not 'NAType'"
    try:
        # Intenta conversión directa optimizada
        X = X_df.to_numpy(dtype=float, na_value=np.nan)
    except Exception:
        # Fallback lento pero seguro: convertir a objeto y luego a float forzado
        X_df = X_df.astype(object)
        X_df = X_df.where(X_df.notna(), np.nan)
        X = X_df.values.astype(float)

    # Imputación (Relleno de nulos con la mediana)
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X)

    # Estandarización
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)

    # Modelo
    model = IsolationForest(
        contamination=cont,
        random_state=rs,
        n_estimators=100,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    scores = -model.decision_function(X_scaled)
    preds = model.predict(X_scaled)
    flags = (preds == -1)

    out["is_outlier"] = flags
    out["outlier_score"] = scores.astype(float)
    out["outlier_method"] = "isolation_forest"

    summary["outliers"] = int(flags.sum())
    summary["ratio"] = float(summary["outliers"] / max(1, len(out)))

    return out, summary