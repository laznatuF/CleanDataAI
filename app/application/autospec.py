# app/application/autospec.py
from __future__ import annotations
from typing import Dict, Any, List
import pandas as pd


def auto_dashboard_spec(df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    # 1. Detección de columnas
    cols = {c.lower(): c for c in df.columns}

    def is_numeric(col_name: str) -> bool:
        return pd.api.types.is_numeric_dtype(df[col_name])

    # --- A. Detección de DINERO ---
    money = None
    total_candidates: List[str] = []
    for c_lower, orig in cols.items():
        if "total_clp" in c_lower and not any(
            skip in c_lower for skip in ["moneda", "currency", "divisa"]
        ):
            if is_numeric(orig) and df[orig].notna().any():
                total_candidates.append(orig)

    if total_candidates:
        money = total_candidates[0]
    else:
        keywords_money = [
            "monto", "importe", "total", "precio", "valor", "revenue",
            "salary", "sueldo", "remuneracion", "ingreso", "costo", "pay"
        ]
        money_candidates: List[str] = []
        for c_lower, orig in cols.items():
            if any(k in c_lower for k in keywords_money):
                if not any(skip in c_lower for skip in ["divisa", "moneda", "currency"]):
                    if is_numeric(orig) and df[orig].notna().any():
                        money_candidates.append(orig)
                    else:
                        # Buscar versiones limpias de esa columna que sí sean numéricas
                        clean_ver = [
                            x for x in df.columns
                            if x.startswith(orig) and is_numeric(x)
                        ]
                        if clean_ver:
                            money_candidates.append(clean_ver[0])
        if money_candidates:
            money = money_candidates[0]

    # --- B. Detección de Otras Dimensiones ---
    date = next(
        (cols[c] for c in cols if any(k in c for k in ["fecha", "date", "created", "time", "dob"])),
        None,
    )
    cat = next(
        (cols[c] for c in cols if any(k in c for k in ["cat", "tipo", "clase", "segmento"])),
        None,
    )
    prod = next(
        (cols[c] for c in cols if any(k in c for k in ["prod", "sku", "articulo", "item"])),
        None,
    )
    city = next(
        (cols[c] for c in cols if any(k in c for k in ["ciudad", "city", "region", "comuna", "provincia", "state", "ubicacion"])),
        None,
    )
    client = next(
        (cols[c] for c in cols if any(k in c for k in ["cli", "customer", "emp", "empleado", "nombre", "name"])),
        None,
    )
    origin = next(
        (cols[c] for c in cols if any(k in c for k in ["origen", "source", "canal"])),
        None,
    )
    qty = next(
        (cols[c] for c in cols if any(k in c for k in ["cant", "qty", "unidades"])),
        None,
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

    # 1. Mapa de Calor Ciudades (Izquierda)
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

    # 2. Histograma (Derecha)
    if money:
        charts.append({
            "id": "d2_hist",
            "type": "histogram",
            "title": "Distribución de Montos",
            "encoding": {"x": {"field": money}},
        })
        d2.append("d2_hist")

    # 3. Calendario (Abajo - Full Width)
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

    # 1. Treemap (Full Width)
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

    # 2. Scatter (Abajo)
    if money and qty:
        charts.append({
            "id": "d3_scat",
            "type": "scatter",
            "title": "Precio vs Cantidad",
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

    # --- SCHEMA para el reporte narrativo / fingerprint ---
    schema = {
        "primary_date": date,
        "primary_metric": money if money else None,
        "dims": [c for c in [city, origin, cat, prod, client] if c],
    }

    # Puedes opcionalmente pasar source_name/filename via kwargs
    source_name = kwargs.get("source_name") or kwargs.get("filename")

    return {
        "dashboards": dashboards,
        "charts": charts,
        "kpis": all_kpis,
        "schema": schema,
        "source_name": source_name,
    }
