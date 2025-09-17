from pathlib import Path
import pandas as pd

def read_dataframe(path: Path) -> pd.DataFrame:
    """
    Lee el archivo en un DataFrame.
    - CSV: intenta UTF-8 y cae a latin-1 si hace falta.
    - Excel: .xlsx/.xls con engine por defecto de pandas.
    - ODS: usa engine='odf' (requiere odfpy).
    """
    ext = path.suffix.lower()
    if ext == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")
    elif ext in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    elif ext == ".ods":
        return pd.read_excel(path, engine="odf")
    else:
        raise ValueError(f"Extensión no soportada: {ext}")
