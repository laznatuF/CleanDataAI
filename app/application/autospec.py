# app/application/autospec.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re
import pandas as pd
import numpy as np

# ------------------------- utilidades -------------------------

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _has(df: pd.DataFrame, col: Optional[str]) -> bool:
    return bool(col) and col in df.columns

def _first(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for n in names:
        if n in df.columns:
            return n
    return None

def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s)

def _as_float_series(s: pd.Series) -> pd.Series:
    """Convierte a float de forma robusta (maneja $ . , y espacios)."""
    if _is_numeric(s):
        return pd.to_numeric(s, errors="coerce")
    s2 = (
        s.astype(str)
         .str.replace(r"[^\d,\.\-]", "", regex=True)
    )
    # Si hay . y , intentar decidir separador decimal por la última aparición
    def _to_one(v: str) -> Optional[float]:
        if not v:
            return None
        if "," in v and "." in v:
            if v.rfind(",") > v.rfind("."):
                v = v.replace(".", "").replace(",", ".")
            else:
                v = v.replace(",", "")
        elif "," in v and "." not in v:
            v = v.replace(",", ".")
        try:
            return float(v)
        except Exception:
            return None
    return s2.map(_to_one)

def _parse_date_series(s: pd.Series) -> pd.Series:
    # sin infer_datetime_format (deprecado) y con fallback dayfirst False
    x = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if x.notna().mean() < 0.5:
        x2 = pd.to_datetime(s, errors="coerce", dayfirst=False)
        if x2.notna().mean() > x.notna().mean():
            return x2
    return x

def _nonnull_ratio(df: pd.DataFrame, col: Optional[str]) -> float:
    if not _has(df, col): return 0.0
    return float(df[col].notna().mean())

def _cardinality(df: pd.DataFrame, col: Optional[str]) -> int:
    if not _has(df, col): return 0
    return int(df[col].nunique(dropna=True))

def _pick_dim(df: pd.DataFrame, candidates: List[str], max_card: int = 50) -> Optional[str]: # Aumentado a 50 para cubrir Deptos grandes
    for c in candidates:
        if c in df.columns:
            u = _cardinality(df, c)
            if 2 <= u <= max_card:
                return c
    # si ninguna cumple, tomar la primera que exista aunque tenga card alta
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _prettify(s: str) -> str:
    """Helper visual para títulos."""
    s = str(s).replace("_", " ").replace("-", " ")
    return s[:1].upper() + s[1:]

# ------------------------- detección de esquema -------------------------

def _detect_roles_from_names(df: pd.DataFrame) -> Dict[str, str]:
    """Heurística por nombre cuando no vienen roles del pipeline."""
    R: Dict[str, str] = {}
    for c in df.columns:
        n = _norm(c)
        if any(k in n for k in ["fecha","date","dia","día","month","year","timestamp","periodo","período","hire"]):
            R[c] = "fecha"
        elif any(k in n for k in ["monto","importe","amount","revenue","ventas","total","valor","price_total","salary","sueldo"]):
            R[c] = "métrica_monetaria"
        elif any(k in n for k in ["precio_unit","unit_price","precio"]):
            R[c] = "métrica_numérica"
        elif any(k in n for k in ["qty","cantidad","units","score","edad","age"]):
            R[c] = "métrica_numérica"
        elif any(k in n for k in ["id","folio","codigo","código","nro","numero","número","zip"]):
            R[c] = "id"
        elif any(k in n for k in ["moneda","currency"]):
            R[c] = "categórica"
        else:
            R[c] = "categórica"
    return R

def _guess_domain(cols_lower: str) -> str:
    if any(k in cols_lower for k in ["venta","ventas","cliente","producto","sku","pedido","orden","order","invoice","factura","monto","importe","precio","cantidad"]):
        return "sales"
    if any(k in cols_lower for k in ["empleado","sueldo","salary","hr","nomina","nómina","contrato","hire","department"]):
        return "hr"
    if any(k in cols_lower for k in ["envio","envío","transporte","logística","logistica","tracking","paquete"]):
        return "logistics"
    return "generic"

def _derive_amount(df: pd.DataFrame, roles: Dict[str,str]) -> Tuple[Optional[str], Dict[str,str]]:
    """Encuentra columna de monto/importe; si no existe, intenta derivarla."""
    derived: Dict[str,str] = {}
    
    # 0. Buscar columna normalizada (Creada por cleaning.py) - Prioridad máxima
    clp_col = _first(df, [c for c in df.columns if "total_clp" in c])
    if clp_col: return clp_col, derived

    # 1) si ya hay métrica monetaria utilizable
    money = [c for c,r in roles.items() if r == "métrica_monetaria" and _nonnull_ratio(df, c) > 0]
    if money:
        # prioriza columnas que insinúen 'total' o 'salario'
        money = sorted(money, key=lambda c: (not re.search(r"total|importe|monto|revenue|ventas|salary|sueldo", _norm(c))), reverse=False)
        return money[0], derived

    # 2) derivar: cantidad × precio_unitario
    qty = _first(df, [c for c in df.columns if re.search(r"\b(qty|cantidad|units)\b", _norm(c))])
    unitp = _first(df, [c for c in df.columns if re.search(r"(precio_unit|unit_price|precio\b)", _norm(c))])
    if _has(df, qty) and _has(df, unitp):
        amt = "__importe_total__"
        try:
            s = _as_float_series(df[qty]) * _as_float_series(df[unitp])
            if s.notna().sum() >= max(10, int(len(df)*0.1)):
                # adjunta como columna temporal para que el renderer pueda usarla
                df[amt] = s
                derived[amt] = f"{qty} * {unitp}"
                return amt, derived
        except: pass

    # 3) si nada: usar la primera numérica “fuerte” que no sea un ID o ZIP
    numeric_candidates = [c for c in df.columns if _as_float_series(df[c]).notna().mean() > 0.8 and "id" not in _norm(c) and "zip" not in _norm(c)]
    if numeric_candidates:
        return numeric_candidates[0], derived

    return None, derived

# ------------------------- builder de SPEC -------------------------

def auto_dashboard_spec(
    df: pd.DataFrame,
    roles: Optional[Dict[str, str]] = None,
    source_name: Optional[str] = None,
    process_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera un SPEC Inteligente y Multi-Dashboard.
    Soporta Ventas, RRHH y Genérico.
    """
    roles = roles or _detect_roles_from_names(df)
    cols_lower = " ".join([_norm(c) for c in df.columns])
    domain = _guess_domain(cols_lower)

    # 1. Columnas Clave (Mejorado para RRHH)
    date_col = None
    # Prioridad de fechas: Hire/Venta > Nacimiento > Review > Log
    prio_dates = ["hire", "contrato", "venta", "order", "fecha", "date"]
    
    date_candidates = [c for c,r in roles.items() if r == "fecha"]
    if not date_candidates:
        date_candidates = [c for c in df.columns if re.search(r"\b(fecha|date|dia|día|timestamp|period|hire)\b", _norm(c))]
    
    if date_candidates:
        # Ordenar por relevancia semántica
        date_candidates.sort(key=lambda x: next((i for i, k in enumerate(prio_dates) if k in _norm(x)), 99))
        date_col = date_candidates[0]

    amt_col, derived = _derive_amount(df, roles)
    qty_col = _first(df, [c for c in df.columns if re.search(r"\b(qty|cantidad|units)\b", _norm(c))])
    
    # 2. Dimensiones (Vocabulario Ampliado)
    # Buscamos dimensiones válidas (cardinalidad 2..50)
    valid_dims = [
        c for c in df.columns 
        if 2 <= _cardinality(df, c) <= 50 
        and not pd.api.types.is_numeric_dtype(df[c])
        and "id" not in _norm(c)
    ]
    
    # Lista de prioridad Universal (Ventas + RRHH + Geo)
    priority_vocab = [
        # Ventas
        "categoria", "category", "producto", "product", "sku", "cliente", "customer", "client",
        # RRHH
        "department", "departamento", "area", "position", "puesto", "cargo", "role",
        "sex", "gender", "genero", "marital", "civil", "performance", "source", "manager",
        # Geo
        "ciudad", "city", "pais", "country", "region", "state", "estado", "provincia",
        # General
        "status", "estatus", "type", "tipo", "payment", "pago"
    ]
    
    def _dim_rank(c: str) -> int:
        n = _norm(c)
        try: return priority_vocab.index(next(k for k in priority_vocab if k in n))
        except StopIteration: return 999

    # Ordenamos las dimensiones encontradas por importancia
    sorted_dims = sorted(valid_dims, key=_dim_rank)

    # ---- Construcción de Dashboards ----
    charts: List[Dict[str, Any]] = []
    dashboards: List[Dict[str, Any]] = []

    # --- Dashboard 1: RESUMEN (Overview) ---
    d1_ids = []

    # 1.1 Tendencia Temporal
    if date_col:
        cid = "trend_main"
        charts.append({
            "id": cid, "type": "line",
            "title": f"Evolución temporal ({_prettify(date_col)})",
            "x_title": "Fecha", "y_title": _prettify(amt_col) if amt_col else "Registros",
            "encoding": {"x": {"field": date_col, "timeUnit": "yearmonth"},
                         "y": {"field": amt_col or "__row__", "aggregate": "sum" if amt_col else "count"}}
        })
        d1_ids.append(cid)

    # 1.2 Top Dimensión Principal
    if sorted_dims:
        d0 = sorted_dims[0]
        cid = f"top_{d0}"
        charts.append({
            "id": cid, "type": "bar", "limit": 10,
            "title": f"Top por {_prettify(d0)}",
            "x_title": _prettify(d0),
            "encoding": {"x": {"field": d0},
                         "y": {"field": amt_col or "__row__", "aggregate": "sum" if amt_col else "count"}}
        })
        d1_ids.append(cid)

    # 1.3 Distribución / Torta
    if amt_col:
        cid = "hist_main"
        charts.append({
            "id": cid, "type": "histogram",
            "title": f"Distribución de {_prettify(amt_col)}",
            "x_title": amt_col, "y_title": "Frecuencia",
            "encoding": {"x": {"field": amt_col}}
        })
        d1_ids.append(cid)
    elif len(sorted_dims) > 1:
        d1 = sorted_dims[1]
        cid = f"pie_{d1}"
        charts.append({
            "id": cid, "type": "pie", "limit": 8,
            "title": f"Distribución por {_prettify(d1)}",
            "encoding": {"category": {"field": d1},
                         "value": {"field": "__row__", "aggregate": "count"}}
        })
        d1_ids.append(cid)

    # 1.4 Calidad de Datos (Ignorando nulos de 'baja/termination')
    charts.append({
        "id": "nulls_pct", "type": "bar", "limit": 20,
        "title": "Campos vacíos (Revisión)",
        "x_title": "Columna", "y_title": "% Vacío",
        "encoding": {"x": {"field": "__column__"},
                     "y": {"field": "__null_pct__", "aggregate": "none"}},
    })
    d1_ids.append("nulls_pct")

    dashboards.append({"id": "dash_overview", "title": "1. Resumen", "charts": d1_ids})

    # --- Dashboard 2: DETALLES (Categorías) ---
    d2_ids = []
    count_d2 = 0
    # Tomamos hasta 6 dimensiones adicionales
    for dim in sorted_dims:
        if f"top_{dim}" in d1_ids: continue # No repetir el principal
        if count_d2 >= 6: break

        cid = f"cat_{dim}"
        ctype = "pie" if _cardinality(df, dim) <= 5 else "bar"
        charts.append({
            "id": cid, "type": ctype, "limit": 12,
            "title": f"Desglose: {_prettify(dim)}",
            "x_title": dim,
            "encoding": {
                "category" if ctype=="pie" else "x": {"field": dim},
                "value" if ctype=="pie" else "y": {"field": amt_col or "__row__", "aggregate": "sum" if amt_col else "count"}
            }
        })
        d2_ids.append(cid)
        count_d2 += 1
    
    if d2_ids:
        dashboards.append({"id": "dash_details", "title": "2. Detalles", "charts": d2_ids})

    # --- Dashboard 3: RELACIONES (Scatter/Heatmap) ---
    d3_ids = []
    
    # 3.1 Heatmap Temporal
    if date_col:
        cid = "heatmap_time"
        charts.append({
            "id": cid, "type": "heatmap",
            "title": "Patrones de Tiempo (Mes vs Día)",
            "x_title": "Mes", "y_title": "Día",
            "encoding": {"x": {"field": date_col, "timeUnit": "month"},
                         "y": {"field": date_col, "timeUnit": "day"},
                         "value": {"field": amt_col or "__row__", "aggregate": "sum" if amt_col else "count"}}
        })
        d3_ids.append(cid)

    # 3.2 Cruce de Dimensiones
    if len(sorted_dims) >= 2:
        da, db = sorted_dims[0], sorted_dims[1]
        cid = f"cross_{da}_{db}"
        charts.append({
            "id": cid, "type": "heatmap",
            "title": f"Matriz: {_prettify(da)} vs {_prettify(db)}",
            "x_title": da, "y_title": db,
            "encoding": {"x": {"field": da}, "y": {"field": db},
                         "value": {"field": amt_col or "__row__", "aggregate": "sum" if amt_col else "count"}}
        })
        d3_ids.append(cid)

    if d3_ids:
        dashboards.append({"id": "dash_deep", "title": "3. Relaciones", "charts": d3_ids})

    # ---- Filtros & KPIs
    filters: List[Dict[str, Any]] = []
    if _has(df, date_col):
        filters.append({"field": date_col, "type": "date_range"})
    for c in sorted_dims[:3]:
        filters.append({"field": c, "type": "categorical", "max_values": 50})

    kpis: List[Dict[str, Any]] = [{"title": "Filas", "op": "count_rows"}]
    if _has(df, amt_col):
        lbl = "Total Salarios" if "salary" in _norm(amt_col) else "Ingresos (Suma)"
        kpis.append({"title": lbl, "op": "sum", "col": amt_col})
        kpis.append({"title": "Promedio", "op": "mean", "col": amt_col})
    elif sorted_dims:
        kpis.append({"title": f"{_prettify(sorted_dims[0])} Únicos", "op": "nunique", "col": sorted_dims[0]})

    # ---- Retorno
    schema = {
        "roles": roles,
        "primary_date": date_col,
        "primary_metric": amt_col,
        "dims": sorted_dims,
        "derived": derived,
        "domain": domain,
    }

    # Compatibilidad: Lista 'charts' contiene todo, 'dashboards' agrupa
    return {
        "title": f"Dashboard · {source_name or 'dataset'}",
        "kpis": kpis,
        "filters": filters,
        "schema": schema,
        "charts": charts,
        "dashboards": dashboards,
    }