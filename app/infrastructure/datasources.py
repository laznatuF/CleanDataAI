from __future__ import annotations
from pathlib import Path
from typing import Union

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
            raise RuntimeError("Falta 'xlrd' para leer .xls.") from e
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

    df.columns = [str(c).strip() for c in df.columns]
    return df
