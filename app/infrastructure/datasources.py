from __future__ import annotations
from pathlib import Path
from typing import Union

import pandas as pd

from app.core.config import ALLOWED_EXTENSIONS

PathLike = Union[str, Path]

def _read_csv(path: Path) -> pd.DataFrame:
   
    try_encodings = ["utf-8-sig", "utf-8", "latin-1"]
    for enc in try_encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    
    return pd.read_csv(path)

def _read_excel(path: Path) -> pd.DataFrame:

    suffix = path.suffix.lower()
    engine = None
    if suffix in {".xlsx", ".xlsm", ".xltx"}:
        engine = "openpyxl"
    elif suffix == ".xls":
        
        engine = "xlrd"
    return pd.read_excel(path, engine=engine)

def _read_ods(path: Path) -> pd.DataFrame:
  
    return pd.read_excel(path, engine="odf")

def read_dataframe(path: PathLike) -> pd.DataFrame:
    """
    Lee CSV / Excel / ODS y devuelve un DataFrame.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")

    suf = p.suffix.lower()

    if suf == ".csv":
        df = _read_csv(p)
    elif suf in {".xlsx", ".xls", ".xlsm", ".xltx"}:
        df = _read_excel(p)
    elif suf == ".ods":
        df = _read_ods(p)
    else:
        raise ValueError(f"Extensión no soportada: {suf}")

    df.columns = [str(c).strip() for c in df.columns]
    return df
