from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

def _column_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Devuelve un resumen por columna: tipo, nulos, % nulos, únicos,
    y estadísticas si es numérica.
    """
    rows: list[dict[str, Any]] = []
    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        n = len(s)
        n_missing = int(s.isna().sum())
        n_unique = int(s.nunique(dropna=True))

        info: dict[str, Any] = {
            "name": col,
            "dtype": dtype,
            "n": n,
            "n_missing": n_missing,
            "missing_pct": round(100 * n_missing / n, 2) if n else 0.0,
            "n_unique": n_unique,
            "sample": s.head(5).tolist(),
        }

        if pd.api.types.is_numeric_dtype(s):
            desc = s.describe()
            info.update({
                "is_numeric": True,
                "mean": float(desc.get("mean", float("nan"))),
                "std": float(desc.get("std", float("nan"))),
                "min": float(desc.get("min", float("nan"))),
                "max": float(desc.get("max", float("nan"))),
            })
        else:
            info["is_numeric"] = False

        rows.append(info)
    return rows

def generate_profile_html(df: pd.DataFrame, out_dir: Path, templates_dir: Path) -> Path:
    """
    Renderiza 'profile.html' con métricas básicas y lo guarda como
    runs/{id}/artifacts/reporte_perfilado.html
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape()
    )
    tmpl = env.get_template("profile.html")

    ctx = {
        "n_rows": int(df.shape[0]),
        "n_cols": int(df.shape[1]),
        "columns": _column_summary(df),
    }

    out = out_dir / "reporte_perfilado.html"
    out.write_text(tmpl.render(**ctx), encoding="utf-8")
    return out
