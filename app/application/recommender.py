# app/application/recommender.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import math, re
import numpy as np
import pandas as pd

# opcional pero recomendado
try:
    from sklearn.feature_selection import mutual_info_regression
    _HAS_SK = True
except Exception:
    _HAS_SK = False

_MONEY_NAMES = {"monto","importe","amount","revenue","ventas","price","precio","total","valor","salary","sueldo","pay","wage"}
_MEAN_HINTS  = {"price","precio","rate","ratio","porcentaje","percent","avg","average","promedio","unit"}
_ID_HINTS    = {"id","codigo","code","uuid","nro","numero"}

def _prettify(s: str) -> str:
    s = re.sub(r"[_\-]+", " ", str(s)).strip()
    return s[:1].upper() + s[1:]

def _moneyish_name(name: str) -> bool:
    n = name.lower()
    return any(t in n for t in _MONEY_NAMES)

def _is_bool_series(s: pd.Series) -> bool:
    ser = s.dropna().astype(str).str.lower()
    if ser.empty: return False
    allowed = {"0","1","true","false","t","f","si","sí","no","y","n"}
    return ser.isin(allowed).mean() > 0.9

def _is_id_series(s: pd.Series, name: str) -> bool:
    name_l = name.lower()
    nunique = s.astype(str).nunique(dropna=True)
    n = len(s)
    looks_name = any(h in name_l for h in _ID_HINTS)
    return looks_name or (n >= 20 and nunique >= 0.98 * n)

def _to_numeric_money(s: pd.Series) -> pd.Series:
    s2 = (s.astype(str)
            .str.replace(r"[^\d\-,\.]", "", regex=True)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False))
    return pd.to_numeric(s2, errors="coerce")

def _cardinality_ok(s: pd.Series, n: int) -> bool:
    u = s.astype(str).nunique(dropna=True)
    return 2 <= u <= min(50, max(2, int(0.25*n)))

def _entropy(p: np.ndarray) -> float:
    p = p[p>0]
    return float(-(p*np.log2(p)).sum()) if len(p) else 0.0

def _agg_for_metric(name: str) -> str:
    n = name.lower()
    if any(h in n for h in _MEAN_HINTS):
        return "mean"
    # si parece dinero o ventas → sum
    if _moneyish_name(n) or any(k in n for k in ["ventas","revenue","amount","monto","importe","total"]):
        return "sum"
    return "sum"

def _dim_score(df: pd.DataFrame, dim: str, metric: Optional[str]) -> float:
    """Balance + relación con la métrica (si existe)."""
    s = df[dim].astype(str)
    p = s.value_counts(normalize=True, dropna=False).values
    score = _entropy(p)  # 0..log2(k)
    if metric is not None:
        m = pd.to_numeric(df[metric], errors="coerce")
        if m.notna().any():
            g = pd.DataFrame({"d": s, "m": m}).dropna()
            if not g.empty:
                if _HAS_SK:
                    X = pd.get_dummies(g["d"], drop_first=True)
                    try:
                        mi = float(mutual_info_regression(X, g["m"], discrete_features=True).mean())
                        score += mi
                    except Exception:
                        pass
                else:
                    means = g.groupby("d")["m"].mean()
                    score += float(means.var()) / (1.0 + float(g["m"].var()))
    return score

@dataclass
class SchemaIn:
    roles: Dict[str,str]
    primary_date: Optional[str]
    primary_metric: Optional[str]
    dims: List[str]
    units: Dict[str,str]
    domain: str
    confidence: Dict[str,float]

def choose_objectives(df: pd.DataFrame, roles: Dict[str,str]) -> Tuple[Optional[str], Optional[str], List[str], Dict[str,str]]:
    n = len(df)

    date_cols = [c for c,r in roles.items() if r=="fecha"]
    primary_date = max(date_cols, key=lambda c: df[c].notna().mean()) if date_cols else None

    def _bad_metric(c: str) -> bool:
        return roles.get(c) in {"id","bool","fecha","categórica"} or _is_id_series(df[c], c)

    money_cols = [c for c,r in roles.items() if r=="métrica_monetaria" and not _bad_metric(c)]
    num_cols   = [c for c,r in roles.items() if r=="métrica_numérica" and not _bad_metric(c)]

    primary_metric = None
    if money_cols:
        primary_metric = max(money_cols, key=lambda c: df[c].notna().mean())
    elif num_cols:
        cand = [c for c in num_cols if df[c].astype(str).nunique(dropna=True) < 0.9*n]
        primary_metric = (cand or num_cols)[0]

    cat_cols  = [c for c,r in roles.items() if r=="categórica"]
    bool_cols = [c for c,r in roles.items() if r=="bool"]
    dims = [c for c in cat_cols if _cardinality_ok(df[c], n)]
    if not dims:
        dims = bool_cols[:1] or (cat_cols[:1] if cat_cols else [])
    if dims:
        dims = sorted(dims, key=lambda c: _dim_score(df, c, primary_metric), reverse=True)[:2]

    units: Dict[str,str] = {}
    if "moneda" in df.columns:
        u = df["moneda"].dropna().astype(str).str.upper().unique().tolist()
        if len(u)==1:
            units["currency"] = u[0]

    return primary_date, primary_metric, dims, units

def auto_dashboard_spec(df: pd.DataFrame,
                        roles: Dict[str,str],
                        source_name: Optional[str] = None,
                        process_id: Optional[str] = None) -> Dict[str,Any]:
    title = f"Dashboard · {source_name}" if source_name else "Dashboard"

    primary_date, primary_metric, dims, units = choose_objectives(df, roles)

    kpis: List[Dict[str,Any]] = [{"title":"Filas","op":"count_rows"}]
    if primary_metric:
        kpis.append({"title": f"Suma de {_prettify(primary_metric)}", "op":"sum", "col": primary_metric})
        kpis.append({"title": f"Promedio de {_prettify(primary_metric)}", "op":"mean", "col": primary_metric})
    elif dims:
        kpis.append({"title": f"Categorías en {_prettify(dims[0])}", "op":"nunique", "col": dims[0]})

    filters: List[Dict[str,Any]] = []
    if primary_date:
        filters.append({"field": primary_date, "type":"date_range"})
    for c,r in roles.items():
        if r in {"categórica","bool"}:
            filters.append({"field": c, "type":"categorical","max_values": 50})

    charts: List[Dict[str,Any]] = []
    ids: List[str] = []
    def add(ch: Dict[str,Any]): ids.append(ch["id"]); charts.append(ch)

    # 1) Serie temporal
    if primary_date:
        if primary_metric:
            agg = _agg_for_metric(primary_metric)
            add({
                "id":"ts",
                "type":"line",
                "title": f"{_prettify(primary_metric)} por mes",
                "encoding":{"x":{"field": primary_date, "timeUnit":"month"},
                            "y":{"field": primary_metric, "aggregate": agg}},
                "x_title":"Mes","y_title":_prettify(primary_metric)
            })
        else:
            add({
                "id":"ts_count",
                "type":"line",
                "title": "Conteo por mes",
                "encoding":{"x":{"field": primary_date, "timeUnit":"month"},
                            "y":{"field":"__row__", "aggregate":"count"}},
                "x_title":"Mes","y_title":"Conteo"
            })

    # 2) Top-N por mejor dim
    if dims:
        dim = dims[0]
        if primary_metric:
            agg = _agg_for_metric(primary_metric)
            add({
                "id":"top_dim",
                "type":"bar",
                "title": f"Top { _prettify(dim) } por { _prettify(primary_metric) }",
                "encoding":{"x":{"field": dim},
                            "y":{"field": primary_metric, "aggregate": agg}},
                "x_title": dim, "y_title": primary_metric, "limit": 12
            })
        else:
            add({
                "id":"top_dim_count",
                "type":"bar",
                "title": f"Top { _prettify(dim) } (conteo)",
                "encoding":{"x":{"field": dim},
                            "y":{"field":"__row__", "aggregate":"count"}},
                "x_title": dim, "y_title": "Conteo", "limit": 12
            })

        # 3) Donut si categorías ≤ 8
        if df[dim].astype(str).nunique(dropna=True) <= 8:
            add({
                "id":"share_dim",
                "type":"pie",
                "title": f"Participación por { _prettify(dim) }",
                "encoding":{"category":{"field": dim},
                            "value":{"field": primary_metric or "__row__",
                                     "aggregate": _agg_for_metric(primary_metric) if primary_metric else "count"}},
                "limit": 8
            })

    # 4) Histograma
    if primary_metric:
        add({
            "id":"hist",
            "type":"histogram",
            "title": f"Distribución de { _prettify(primary_metric) }",
            "encoding":{"x":{"field": primary_metric}},
            "x_title": primary_metric, "y_title":"Frecuencia"
        })

    # Fallback si quedó vacío
    if not charts:
        # toma cualquier categórica/booleana
        cat_any = next((c for c,r in roles.items() if r in {"categórica","bool"}), None)
        if cat_any:
            add({
                "id":"fallback_count",
                "type":"bar",
                "title": f"Conteo por { _prettify(cat_any) }",
                "encoding":{"x":{"field": cat_any}, "y":{"field":"__row__","aggregate":"count"}},
                "x_title": cat_any, "y_title":"Conteo", "limit": 12
            })

    return {
        "schema":{"roles": roles, "primary_date": primary_date, "primary_metric": primary_metric,
                  "dims": dims, "units": units, "domain": "auto"},
        "kpis": kpis,
        "filters": filters,
        "charts": charts,
        "dashboards":[{"title": title, "charts": ids}]
    }
