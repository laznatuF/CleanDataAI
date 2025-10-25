# app/infrastructure/datasources.py
from __future__ import annotations
from pathlib import Path
from typing import Union, List
import re

import pandas as pd

from app.core.config import ALLOWED_EXTENSIONS

PathLike = Union[str, Path]

_OPENPYXL_EXTS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
_XLRD_EXTS = {".xls"}


def _read_csv(path: Path) -> pd.DataFrame:
    try_encodings = ["utf-8-sig", "utf-8", "latin-1"]
    last_err: Exception | None = None
    for enc in try_encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
            continue
    try:
        return pd.read_csv(path)
    except Exception as e:
        raise RuntimeError(f"No fue posible leer el CSV (último error: {e!s})") from (last_err or e)


def _read_excel(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf in _OPENPYXL_EXTS:
        engine = "openpyxl"
    elif suf in _XLRD_EXTS:
        engine = "xlrd"
    else:
        engine = None
    try:
        return pd.read_excel(path, engine=engine)
    except ImportError as e:
        if engine == "openpyxl":
            raise RuntimeError("Falta 'openpyxl' para leer .xlsx/.xlsm/.xltx/.xltm.") from e
        if engine == "xlrd":
            raise RuntimeError("Falta 'xlrd==1.2.0' para leer .xls.") from e
        raise
    except Exception as e:
        raise RuntimeError(f"Error leyendo Excel con engine={engine!r}: {e!s}") from e


def _read_ods(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path, engine="odf")
    except ImportError as e:
        raise RuntimeError("Falta 'odfpy' para leer .ods.") from e
    except Exception as e:
        raise RuntimeError(f"Error leyendo ODS: {e!s}") from e


# ---------- Normalización de encabezados (RFN8, RFN9, RFN10) ----------
def _slug_header(raw: str) -> str:
    """
    - trim y colapso de espacios
    - minúsculas
    - convierte a snake_case (solo [a-z0-9_])
    """
    s = str(raw or "").strip()
    s = re.sub(r"\s+", " ", s)         # colapsa espacios internos
    s = s.lower()
    s = s.replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "_", s)  # elimina símbolos raros
    s = re.sub(r"_+", "_", s).strip("_")
    return s or ""


def _unique_headers(cols: List[str]) -> List[str]:
    """
    Asegura unicidad: duplica como col, col_2, col_3, ...
    Encabezados vacíos -> col_1, col_2, ...
    """
    out: List[str] = []
    seen: dict[str, int] = {}
    empty_count = 0
    for i, c in enumerate(cols, 1):
        base = _slug_header(c)
        if not base:
            empty_count += 1
            base = f"col_{empty_count}"
        n = seen.get(base, 0) + 1
        seen[base] = n
        out.append(base if n == 1 else f"{base}_{n}")
    return out
# ---------------------------------------------------------------------


def read_dataframe(path: PathLike) -> pd.DataFrame:
    """
    Lee CSV / Excel / ODS y devuelve un DataFrame normalizando encabezados.
    Valida la extensión contra app.core.config.ALLOWED_EXTENSIONS.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")

    suf = p.suffix.lower()
    if suf not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Extensión no soportada: {suf}. Permitidas: {allowed}")

    if suf == ".csv":
        df = _read_csv(p)
    elif suf in (_OPENPYXL_EXTS | _XLRD_EXTS):
        df = _read_excel(p)
    elif suf == ".ods":
        df = _read_ods(p)
    else:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Extensión no soportada (guardarraíl): {suf}. Permitidas: {allowed}")

    # Normalización de columnas (RFN8, RFN9, RFN10)
    df.columns = _unique_headers([str(c) for c in df.columns])
    return df
