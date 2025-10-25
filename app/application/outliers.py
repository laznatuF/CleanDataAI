# app/application/outliers.py
from __future__ import annotations

from typing import Tuple, Dict, List
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


def _select_numeric_columns(df: pd.DataFrame) -> List[str]:
    """
    Elige columnas numéricas con al menos 2 valores no nulos distintos.
    Evita columnas constantes o totalmente nulas.
    """
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    keep: List[str] = []
    for c in num_cols:
        s = df[c].dropna()
        if s.nunique() >= 2:
            keep.append(c)
    return keep


def apply_isolation_forest(
    df: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Aplica IsolationForest sobre columnas numéricas tipificadas.
    Añade columnas:
      - is_outlier (bool)
      - outlier_score (float; mayor => más anómalo)
      - outlier_method = "isolation_forest"

    Devuelve (df_modificado, resumen_dict).
    """
    out = df.copy()

    used_cols = _select_numeric_columns(out)
    summary: Dict = {
        "used_columns": used_cols,
        "contamination": float(contamination),
        "random_state": int(random_state),
        "outliers": 0,
        "total": int(len(out)),
        "ratio": 0.0,
        "skipped": False,
    }

    # Sin filas o sin columnas numéricas útiles: crear columnas y salir
    if len(out) == 0 or len(used_cols) == 0:
        out["is_outlier"] = False
        out["outlier_score"] = np.nan
        out["outlier_method"] = "isolation_forest"
        summary["skipped"] = True
        return out, summary

    # Extrae matriz X y trata NaNs con la mediana de cada columna
    X = out[used_cols].to_numpy()
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X)

    # Estandariza (media 0, var 1) para no sesgar por escalas distintas
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)

    # Entrena IsolationForest
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=100,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # decision_function: valores más altos => menos anómalo
    # invertimos el signo para que 'outlier_score' más alto => más anómalo
    scores = -model.decision_function(X_scaled)  # ndarray shape (n_samples,)
    preds = model.predict(X_scaled)              # 1 normal, -1 outlier
    flags = (preds == -1)

    # Anexar columnas al dataframe
    out["is_outlier"] = flags
    out["outlier_score"] = scores.astype(float)
    out["outlier_method"] = "isolation_forest"

    summary["outliers"] = int(flags.sum())
    summary["ratio"] = float(summary["outliers"] / max(1, len(out)))

    return out, summary
