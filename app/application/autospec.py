from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

def auto_dashboard_spec(df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    # 1. Detección de columnas
    cols = {c.lower(): c for c in df.columns}

    def numeric_like(col_name: str, min_ratio: float = 0.5) -> bool:
        """True si la columna es numérica o se puede convertir a numérica con buen ratio."""
        if col_name not in df.columns:
            return False
        s = df[col_name]
        if pd.api.types.is_numeric_dtype(s):
            return s.notna().any()
        try:
            x = pd.to_numeric(s, errors="coerce")
            return x.notna().mean() >= min_ratio
        except Exception:
            return False

    def pick_col(
        prefer_exact: List[str],
        keywords: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Elige columna por nombre exacto preferido, si no, por keywords."""
        for name in prefer_exact:
            key = name.lower()
            if key in cols:
                return cols[key]
        if keywords:
            return next((cols[c] for c in cols if any(k in c for k in keywords)), None)
        return None

    # --- A. Detección de DINERO (robusta + prioridad) ---
    banned_money = {
        "precio_unitario_unificado",
        "precio_unitario",
        "unit_price",
        "unitprice",
        "price",
        "precio",
    }

    # 1) Preferidos (multicanal)
    preferred_money = pick_col(
        ["total_venta_clp", "total_bruto_clp", "total_neto_clp"]
    )
    money = preferred_money if (preferred_money and numeric_like(preferred_money)) else None

    # 2) Candidatos *_clp (incluye strings convertibles)
    if not money:
        total_candidates: List[str] = []
        for c_lower, orig in cols.items():
            if (
                ("_clp" in c_lower or "total_clp" in c_lower)
                and not any(skip in c_lower for skip in ["moneda", "currency", "divisa"])
            ):
                if numeric_like(orig) and df[orig].notna().any():
                    # evita precio unitario como dinero principal si hay mejores
                    if c_lower in banned_money or "unit" in c_lower or "unitario" in c_lower:
                        continue
                    total_candidates.append(orig)

        if total_candidates:
            # orden de prioridad dentro de los *_clp
            priority = {
                "total_venta_clp": 0,
                "total_bruto_clp": 1,
                "total_neto_clp": 2,
            }
            def _rank(c: str):
                return (priority.get(c.lower(), 50), -(df[c].notna().mean() if c in df else 0))

            total_candidates.sort(key=_rank)
            money = total_candidates[0]

    # 3) Fallback por keywords (pero evitando “precio unitario”)
    if not money:
        keywords_money = [
            # primero lo que suele ser monto total
            "monto", "importe", "revenue", "ingreso", "total", "valor",
            "salary", "sueldo", "remuneracion", "costo", "pay",
            # "precio" al final (peligroso)
            "precio",
        ]
        money_candidates: List[str] = []
        for c_lower, orig in cols.items():
            if any(k in c_lower for k in keywords_money):
                if any(skip in c_lower for skip in ["divisa", "moneda", "currency"]):
                    continue
                # evita precio unitario como métrica principal
                if "unit" in c_lower or "unitario" in c_lower or c_lower in banned_money:
                    continue

                if numeric_like(orig) and df[orig].notna().any():
                    money_candidates.append(orig)
                else:
                    # Buscar versiones limpias que sí sean numéricas
                    clean_ver = [x for x in df.columns if x.startswith(orig) and numeric_like(x)]
                    if clean_ver:
                        money_candidates.append(clean_ver[0])

        if money_candidates:
            money = money_candidates[0]

    # Si igual cayó en precio unitario y existe total_* => fuerza a total
    if money and money.lower() in banned_money:
        hard = pick_col(["total_venta_clp", "total_bruto_clp", "total_neto_clp"])
        if hard and numeric_like(hard):
            money = hard

    # --- B. Detección de Otras Dimensiones (con prioridad multicanal) ---
    date = pick_col(
        ["fecha_venta", "fecha", "date", "created_at", "created", "paid_at", "time"],
        ["fecha", "date", "created", "time", "dob"],
    )
    origin = pick_col(
        ["canal_detalle", "canal", "origen", "source", "order_source", "source_name"],
        ["origen", "source", "canal"],
    )
    cat = pick_col(
        ["categoria", "category", "cat", "tipo", "clase", "segmento"],
        ["cat", "tipo", "clase", "segmento", "category", "categoria"],
    )
    prod = pick_col(
        ["producto_nombre", "producto", "item", "sku", "articulo", "lineitem_name"],
        ["producto", "prod", "sku", "articulo", "item", "lineitem"],
    )
    client = pick_col(
        ["cliente_nombre", "cliente", "customer", "comprador", "billing_name", "shipping_name"],
        ["cliente", "customer", "comprador", "buyer", "billing", "shipping"],
    )
    # fallback MUY amplio (solo si no encontró nada)
    if not client:
        client = pick_col(["name", "nombre"], ["name", "nombre", "emp", "empleado"])

    city = pick_col(
        ["ciudad_envio", "comuna_envio", "region_envio", "ciudad", "city"],
        ["ciudad", "city", "region", "comuna", "provincia", "state", "ubicacion"],
    )
    qty = pick_col(
        ["cantidad_unificada", "cantidad", "qty", "quantity", "unidades"],
        ["cant", "qty", "quantity", "unidades"],
    )

    metric = money or "__row__"
    agg = "sum" if money else "count"

    # --- C. Construcción del Dashboard ---
    dashboards: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []
    all_kpis: List[Dict[str, Any]] = []

    # KPIs Globales
    if money:
        all_kpis.append({"title": "Monto Total", "op": "sum", "col": money})
    all_kpis.append({"title": "Registros", "op": "count_rows"})
    if money:
        all_kpis.append({"title": "Promedio", "op": "mean", "col": money})

    # --- DASH 1: RESUMEN EJECUTIVO ---
    d1: List[str] = []
    if date:
        charts.append({
            "id": "d1_trend",
            "type": "line",
            "title": "Tendencia Mensual",
            "encoding": {
                "x": {"field": date},
                "y": {"field": metric, "aggregate": agg},
            },
        })
        d1.append("d1_trend")

    col_pie = cat or origin or city
    if col_pie:
        charts.append({
            "id": "d1_pie",
            "type": "pie",
            "title": f"Distribución por {col_pie}",
            "encoding": {
                "category": {"field": col_pie},
                "value": {"field": metric},
            },
        })
        d1.append("d1_pie")

    if origin:
        charts.append({
            "id": "d1_origin",
            "type": "bar",
            "title": "Distribución por Origen",
            "encoding": {
                "x": {"field": origin},
                "y": {"field": metric, "aggregate": agg},
            },
        })
        d1.append("d1_origin")

    dashboards.append({"id": "exec", "title": "1. Resumen Ejecutivo", "charts": d1})

    # --- DASH 2: ANÁLISIS DETALLADO ---
    d2: List[str] = []

    if city and date and money:
        charts.append({
            "id": "d4_city_matrix",
            "type": "heatmap_pivot",
            "title": f"Mapa de Calor: {city} vs Meses",
            "encoding": {
                "x": {"field": date},
                "y": {"field": city},
                "value": {"field": money},
            },
        })
        d2.append("d4_city_matrix")

    if money:
        charts.append({
            "id": "d2_hist",
            "type": "histogram",
            "title": "Distribución de Montos",
            "encoding": {"x": {"field": money}},
        })
        d2.append("d2_hist")

    if date:
        charts.append({
            "id": "d2_cal",
            "type": "calendar",
            "title": "Intensidad Diaria (Calendario)",
            "encoding": {
                "date": {"field": date},
                "value": {"field": metric},
            },
        })
        d2.append("d2_cal")

    dashboards.append({"id": "adv", "title": "2. Análisis Detallado", "charts": d2})

    # --- DASH 3: PRODUCTOS ---
    d3: List[str] = []

    if cat and prod:
        charts.append({
            "id": "d3_tree",
            "type": "treemap",
            "title": "Mapa de Árbol de Productos",
            "encoding": {
                "category": {"field": cat},
                "sub": {"field": prod},
                "value": {"field": metric},
            },
        })
        d3.append("d3_tree")

    if money and qty:
        title_scatter = "Precio vs Cantidad" if ("precio" in money.lower() or "unit" in money.lower()) else "Monto vs Cantidad"
        charts.append({
            "id": "d3_scat",
            "type": "scatter",
            "title": title_scatter,
            "encoding": {
                "x": {"field": money},
                "y": {"field": qty},
            },
        })
        d3.append("d3_scat")

    if d3:
        dashboards.append({"id": "prod", "title": "3. Productos", "charts": d3})

    # --- DASH 4: RANKINGS ---
    d4: List[str] = []
    target_cols = [c for c in [city, client] if c]
    for i, col_dim in enumerate(target_cols[:2]):
        charts.append({
            "id": f"rank_{i}",
            "type": "bar",
            "title": f"Top 10: {col_dim}",
            "limit": 10,
            "encoding": {
                "x": {"field": col_dim},
                "y": {"field": metric, "aggregate": agg},
            },
        })
        d4.append(f"rank_{i}")

    if d4:
        dashboards.append({"id": "rank", "title": "4. Rankings", "charts": d4})

    schema = {
        "primary_date": date,
        "primary_metric": money if money else None,
        "dims": [c for c in [city, origin, cat, prod, client] if c],
    }

    source_name = kwargs.get("source_name") or kwargs.get("filename")

    return {
        "dashboards": dashboards,
        "charts": charts,
        "kpis": all_kpis,
        "schema": schema,
        "source_name": source_name,
    }
