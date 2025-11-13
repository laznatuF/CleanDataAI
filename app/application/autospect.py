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

def _pick_dim(df: pd.DataFrame, candidates: List[str], max_card: int = 30) -> Optional[str]:
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

# ------------------------- detección de esquema -------------------------

def _detect_roles_from_names(df: pd.DataFrame) -> Dict[str, str]:
    """Heurística por nombre cuando no vienen roles del pipeline."""
    R: Dict[str, str] = {}
    for c in df.columns:
        n = _norm(c)
        if any(k in n for k in ["fecha","date","dia","día","month","year","timestamp","periodo","período"]):
            R[c] = "fecha"
        elif any(k in n for k in ["monto","importe","amount","revenue","ventas","total","valor","price_total"]):
            R[c] = "métrica_monetaria"
        elif any(k in n for k in ["precio_unit","unit_price","precio"]):
            R[c] = "métrica_numérica"
        elif any(k in n for k in ["qty","cantidad","units"]):
            R[c] = "métrica_numérica"
        elif any(k in n for k in ["id","folio","codigo","código","nro","numero","número"]):
            R[c] = "id"
        elif any(k in n for k in ["moneda","currency"]):
            R[c] = "categórica"
        else:
            R[c] = "categórica"
    return R

def _guess_domain(cols_lower: str) -> str:
    if any(k in cols_lower for k in ["venta","ventas","cliente","producto","sku","pedido","orden","order","invoice","factura","monto","importe","precio","cantidad"]):
        return "sales"
    if any(k in cols_lower for k in ["empleado","sueldo","salary","hr","nomina","nómina","contrato"]):
        return "hr"
    if any(k in cols_lower for k in ["envio","envío","transporte","logística","logistica","tracking","paquete"]):
        return "logistics"
    return "generic"

def _derive_amount(df: pd.DataFrame, roles: Dict[str,str]) -> Tuple[Optional[str], Dict[str,str]]:
    """Encuentra columna de monto/importe; si no existe, intenta derivarla."""
    derived: Dict[str,str] = {}
    # 1) si ya hay métrica monetaria utilizable
    money = [c for c,r in roles.items() if r == "métrica_monetaria" and _nonnull_ratio(df, c) > 0]
    if money:
        # prioriza columnas que insinúen 'total'
        money = sorted(money, key=lambda c: (not re.search(r"total|importe|monto|revenue|ventas", _norm(c))), reverse=False)
        return money[0], derived

    # 2) derivar: cantidad × precio_unitario
    qty = _first(df, [c for c in df.columns if re.search(r"\b(qty|cantidad|units)\b", _norm(c))])
    unitp = _first(df, [c for c in df.columns if re.search(r"(precio_unit|unit_price|precio\b)", _norm(c))])
    if _has(df, qty) and _has(df, unitp):
        amt = "__importe_total__"
        s = _as_float_series(df[qty]) * _as_float_series(df[unitp])
        if s.notna().sum() >= max(10, int(len(df)*0.1)):
            # adjunta como columna temporal para que el renderer pueda usarla
            df[amt] = s
            derived[amt] = f"{qty} * {unitp}"
            return amt, derived

    # 3) si nada: usar la primera numérica “fuerte”
    numeric_candidates = [c for c in df.columns if _as_float_series(df[c]).notna().mean() > 0.8]
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
    Devuelve un SPEC “humano”:
      - KPIs: filas, ingresos, AOV, clientes únicos (si aplica)
      - Gráficos: tendencia mensual, Top por categoría, participación por método de pago,
                  histograma de montos, estado/estatus, Top ciudades/clientes, % nulos.
    El renderer existente (Plotly) lo puede consumir sin cambios.
    """
    roles = roles or _detect_roles_from_names(df)
    cols_lower = " ".join([_norm(c) for c in df.columns])
    domain = _guess_domain(cols_lower)

    # columnas clave
    date_col = None
    for c,r in roles.items():
        if r == "fecha":
            date_col = c; break
    if not date_col:
        # intento por nombre
        date_col = _first(df, [c for c in df.columns if re.search(r"\b(fecha|date|dia|día|timestamp|period)\b", _norm(c))])

    amt_col, derived = _derive_amount(df, roles)
    qty_col = _first(df, [c for c in df.columns if re.search(r"\b(qty|cantidad|units)\b", _norm(c))])
    price_col = _first(df, [c for c in df.columns if re.search(r"(precio_unit|unit_price|^precio\b)", _norm(c))])

    # dimensiones candidatas (orden de importancia típica en ventas)
    dim_categoria = _pick_dim(df, [c for c in df.columns if re.search(r"(categor[ií]a|category|segmento|tipo|brand)", _norm(c))])
    dim_producto  = _pick_dim(df, [c for c in df.columns if re.search(r"(producto|sku|art[ií]culo|item)", _norm(c))])
    dim_ciudad    = _pick_dim(df, [c for c in df.columns if re.search(r"(ciudad|city|comuna|region|región|estado|state)", _norm(c))])
    dim_cliente   = _pick_dim(df, [c for c in df.columns if re.search(r"(cliente|customer|comprador|buyer|user)", _norm(c))], max_card=50)
    dim_pago      = _pick_dim(df, [c for c in df.columns if re.search(r"(m[eé]todo_pago|metodo_pago|payment|forma_pago)", _norm(c))])
    dim_estado    = _pick_dim(df, [c for c in df.columns if re.search(r"(estado|estatus|status)", _norm(c))], max_card=20)

    # ---- KPIs
    kpis: List[Dict[str, Any]] = [{"title": "Filas", "op": "count_rows"}]
    if _has(df, amt_col):
        kpis.append({"title": "Ingresos (suma)", "op": "sum", "col": amt_col})
        # AOV si hay “pedido/orden”. Aproximamos con filas si no hay id de orden.
        order_id = _first(df, [c for c in df.columns if re.search(r"(id|id_orden|id_pedido|order_id|invoice)", _norm(c))])
        denom = order_id if _has(df, order_id) else None
        if denom and df[denom].nunique(dropna=True) > 0:
            # ratio aproximado: total / #ordenes únicas (renderer no calcula; lo dejamos como KPI “promedio” de la col de importe)
            # alternativa simple: “Promedio de importe por fila”
            kpis.append({"title": "Promedio (AOV aprox.)", "op": "mean", "col": amt_col})
        else:
            kpis.append({"title": "Promedio (por fila)", "op": "mean", "col": amt_col})
    if _has(df, dim_cliente):
        kpis.append({"title": "Clientes únicos", "op": "nunique", "col": dim_cliente})

    # ---- Gráficos
    charts: List[Dict[str, Any]] = []

    # 1) Tendencia mensual (ingresos o conteo)
    if _has(df, date_col):
        if _has(df, amt_col):
            charts.append({
                "id": "trend_revenue",
                "type": "line",
                "title": "Ingresos por mes",
                "x_title": "Mes",
                "y_title": "Ingresos",
                "encoding": {"x": {"field": date_col, "timeUnit": "month"},
                             "y": {"field": amt_col, "aggregate": "sum"}}
            })
        else:
            charts.append({
                "id": "trend_count",
                "type": "line",
                "title": "Conteo por mes",
                "x_title": "Mes",
                "y_title": "Filas",
                "encoding": {"x": {"field": date_col, "timeUnit": "month"},
                             "y": {"field": "__row__", "aggregate": "count"}}
            })

    # 2) Top por categoría/producto/ciudad/cliente (con ingresos o conteo)
    def _top_bar(cid: str, dim: Optional[str], title: str):
        if not _has(df, dim): return None
        if _has(df, amt_col):
            return {
                "id": cid, "type": "bar", "limit": 12,
                "title": title, "x_title": dim, "y_title": "Ingresos",
                "encoding": {"x": {"field": dim},
                             "y": {"field": amt_col, "aggregate": "sum"}}
            }
        else:
            return {
                "id": cid, "type": "bar", "limit": 12,
                "title": title, "x_title": dim, "y_title": "Conteo",
                "encoding": {"x": {"field": dim},
                             "y": {"field": "__row__", "aggregate": "count"}}
            }

    for dim, lab, cid in [
        (dim_categoria, "Top categorías", "top_cat"),
        (dim_producto,  "Top productos",  "top_prod"),
        (dim_ciudad,    "Top ciudades",   "top_city"),
        (dim_cliente,   "Top clientes",   "top_client"),
    ]:
        c = _top_bar(cid, dim, f"{lab} por {'ingresos' if _has(df, amt_col) else 'conteo'}")
        if c: charts.append(c)

    # 3) Participación por método de pago (o estado)
    if _has(df, dim_pago):
        charts.append({
            "id": "share_pago",
            "type": "pie",
            "title": "Participación por método de pago",
            "limit": 9,
            "encoding": {
                "category": {"field": dim_pago},
                "value": {"field": (amt_col if _has(df, amt_col) else "__row__"),
                          "aggregate": ("sum" if _has(df, amt_col) else "count")}
            },
        })
    if _has(df, dim_estado):
        charts.append({
            "id": "by_status",
            "type": "bar",
            "title": "Órdenes por estatus",
            "x_title": dim_estado,
            "y_title": "Conteo",
            "limit": 12,
            "encoding": {"x": {"field": dim_estado},
                         "y": {"field": "__row__", "aggregate": "count"}},
        })

    # 4) Distribución de montos (si hay importe)
    if _has(df, amt_col):
        charts.append({
            "id": "hist_amount",
            "type": "histogram",
            "title": "Distribución de importes",
            "x_title": amt_col,
            "y_title": "Frecuencia",
            "encoding": {"x": {"field": amt_col}},
        })

    # 5) Calidad de datos: % nulos por columna
    charts.append({
        "id": "nulls_pct",
        "type": "bar",
        "title": "Porcentaje de nulos por columna",
        "x_title": "__column__",
        "y_title": "% nulos",
        "limit": 40,
        "encoding": {"x": {"field": "__column__"},
                     "y": {"field": "__null_pct__", "aggregate": "none"}},
    })

    # ---- Filtros genéricos
    filters: List[Dict[str, Any]] = []
    if _has(df, date_col):
        filters.append({"field": date_col, "type": "date_range"})
    for c in [dim_categoria, dim_producto, dim_ciudad, dim_cliente, dim_pago, dim_estado]:
        if _has(df, c):
            filters.append({"field": c, "type": "categorical", "max_values": 50})

    # ---- Schema “explicable”
    schema = {
        "roles": roles,
        "primary_date": date_col,
        "primary_metric": amt_col,
        "dims": [d for d in [dim_categoria, dim_producto, dim_ciudad, dim_cliente, dim_pago, dim_estado] if d],
        "derived": derived,
        "domain": domain,
    }

    # Selección “principal” (primer tablero) – 4 gráficos con mayor valor informativo
    chosen: List[str] = []
    for cid in ["trend_revenue", "trend_count", "top_cat", "top_prod", "share_pago", "by_status", "hist_amount", "top_city"]:
        if any(c["id"] == cid for c in charts):
            chosen.append(cid)
        if len(chosen) == 4: break
    if not chosen:
        chosen = [charts[0]["id"]] if charts else []

    return {
        "title": f"Dashboard seguro · {source_name or 'dataset'}",
        "kpis": kpis,
        "filters": filters,
        "schema": schema,
        "charts": charts,
        "dashboards": [
            {"title": f"Dashboard seguro · {source_name or 'dataset'}", "charts": chosen}
        ],
    }
