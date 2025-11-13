# app/application/ml/features.py
import re, numpy as np, pandas as pd
from typing import Dict, Any, List

CURRENCY_RE = re.compile(r'[$€£]|CLP|USD|EUR|MXN|ARS|BRL|PEN', re.I)
BOOL_SET = {'0','1','true','false','t','f','si','sí','no','y','n'}

def head_features(name: str) -> Dict[str, Any]:
    s = name.lower()
    keys_amt = ["monto","importe","amount","revenue","ventas","price","precio","total","valor","salary","sueldo"]
    return {
        "name_len": len(s),
        "has_id": int("id" in s or s.endswith("_id") or s.startswith("id_")),
        "has_pct": int("pct" in s or "%" in s or "porc" in s or "percent" in s),
        "has_amt": int(any(k in s for k in keys_amt)),
        "digits_ratio": sum(ch.isdigit() for ch in s) / max(1,len(s)),
        "underscores": s.count("_"),
    }

def value_features(series: pd.Series, sample=800) -> Dict[str, Any]:
    s = series.dropna().astype(str)
    if len(s) > sample: s = s.sample(sample, random_state=0)
    # numérico “relajado”
    num = pd.to_numeric(
        s.str.replace(r"[.\s]", "", regex=True).str.replace(",", ".", regex=False),
        errors="coerce"
    )
    is_num_ratio = num.notna().mean()
    money_ratio = s.str.contains(CURRENCY_RE).mean()
    bool_ratio  = s.str.lower().isin(BOOL_SET).mean()
    # fecha dos intentos
    t0 = pd.to_datetime(s, errors="coerce", dayfirst=False)
    t1 = pd.to_datetime(s, errors="coerce", dayfirst=True)
    date_ratio = max(t0.notna().mean(), t1.notna().mean())
    return {
        "nunique_ratio": s.nunique(dropna=True) / max(1,len(s)),
        "is_num_ratio": is_num_ratio,
        "money_ratio": money_ratio,
        "bool_ratio": bool_ratio,
        "date_ratio": date_ratio,
        "mean_len": s.str.len().mean() if len(s) else 0,
    }

def column_features(name: str, series: pd.Series) -> Dict[str, Any]:
    f = {}
    f.update(head_features(name))
    f.update(value_features(series))
    return f

def dataset_header_text(columns: List[str]) -> str:
    # Texto unificado de headers para TF-IDF/embeddings
    return " | ".join(str(c).lower() for c in columns)

def role_hist_features(roles: Dict[str,str]) -> Dict[str,int]:
    from collections import Counter
    c = Counter(roles.values())
    keys = ["fecha","métrica_monetaria","métrica_numérica","categórica","bool","id","geo","texto"]
    return {f"role_count_{k}": c.get(k,0) for k in keys}
