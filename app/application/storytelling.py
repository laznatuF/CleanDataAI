# app/application/storytelling.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

# --- Helpers de Formato ---
def _fmt(val) -> str:
    """Formatea números de forma legible (1.2k, $500, etc)."""
    if isinstance(val, (int, float)):
        if val > 1_000_000: return f"{val/1_000_000:.1f}M"
        if val > 1_000: return f"{val/1_000:.1f}k"
        return f"{val:,.0f}".replace(",", ".")
    return str(val)

def _get_metric_name(chart: Dict[str, Any]) -> str:
    """Intenta obtener un nombre legible para la métrica (ej: 'Monto Total')."""
    return chart.get("encoding", {}).get("y", {}).get("field") or \
           chart.get("encoding", {}).get("value", {}).get("field") or "Registros"

# --- Generadores de Texto por Tipo de Gráfico ---

def _narrate_bar(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    x_col = enc.get("x", {}).get("field")
    y_col = enc.get("y", {}).get("field") or "__row__"
    agg = enc.get("y", {}).get("aggregate", "count")
    
    if not x_col: return "Gráfico de barras estándar."

    # Recalcular datos ligeros
    if y_col == "__row__":
        ser = df[x_col].value_counts()
        metric_label = "registros"
    else:
        # Asumiendo columna numérica limpia
        clean_y = pd.to_numeric(df[y_col].astype(str).str.replace(r"[^\d\.]", "", regex=True), errors='coerce')
        if agg == "sum":
            ser = df.groupby(x_col)[y_col].apply(lambda x: pd.to_numeric(x, errors='coerce').sum())
        else:
            ser = df.groupby(x_col)[y_col].apply(lambda x: pd.to_numeric(x, errors='coerce').mean())
        metric_label = y_col

    ser = ser.sort_values(ascending=False)
    top1 = ser.index[0]
    val1 = ser.iloc[0]
    total = ser.sum()
    pct = (val1 / total * 100) if total > 0 else 0
    
    text = (f"Se observa una clara preferencia por <strong>{top1}</strong>, que lidera con "
            f"<strong>{_fmt(val1)}</strong> ({metric_label}). Esto representa un <strong>{pct:.1f}%</strong> del total analizado. ")
    
    if len(ser) > 1:
        top2 = ser.index[1]
        text += f"En segundo lugar se encuentra <strong>{top2}</strong>. "
    
    if len(ser) > 5:
        tail_sum = ser.iloc[5:].sum()
        tail_pct = (tail_sum / total * 100) if total > 0 else 0
        text += f"El resto de las {len(ser)-5} categorías menores agrupan un {tail_pct:.1f}% del volumen, mostrando una distribución {'concentrada' if pct > 40 else 'fragmentada'}."
        
    return text

def _narrate_line(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    date_col = enc.get("x", {}).get("field")
    if not date_col: return "Análisis temporal."
    
    # Simple check de tendencia (primer vs último tercio)
    # Nota: Lógica simplificada para el ejemplo
    return (f"Este gráfico muestra la evolución temporal basada en <strong>{date_col}</strong>. "
            "Permite identificar estacionalidades, picos de actividad o tendencias de crecimiento "
            "a lo largo del periodo capturado en los datos.")

def _narrate_pie(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    cat_col = enc.get("category", {}).get("field")
    if not cat_col: return "Distribución de partes."
    
    unique_count = df[cat_col].nunique()
    return (f"Desglose de la composición por <strong>{cat_col}</strong>. "
            f"Al haber {unique_count} elementos únicos, este visual ayuda a comprender rápidamente "
            "qué segmentos tienen mayor peso relativo en el conjunto de datos.")

def _narrate_calendar(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    return ("<strong>Mapa de Calor de Calendario:</strong> Este visual avanzado permite detectar patrones diarios específicos. "
            "Las zonas más oscuras indican días de alta intensidad. Es ideal para encontrar patrones semanales "
            "(ej: más ventas los viernes) o estacionalidad mensual.")

def _narrate_treemap(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    cat = enc.get("category", {}).get("field")
    sub = enc.get("sub", {}).get("field")
    return (f"Vista jerárquica que cruza <strong>{cat}</strong> con <strong>{sub}</strong>. "
            "El tamaño de los recuadros indica el volumen. Permite identificar rápidamente qué sub-elementos "
            "son los protagonistas dentro de cada categoría principal.")

def _narrate_scatter(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    x = enc.get("x", {}).get("field")
    y = enc.get("y", {}).get("field")
    return (f"Análisis de correlación entre <strong>{x}</strong> y <strong>{y}</strong>. "
            "Si los puntos forman una línea diagonal, indica una relación fuerte. "
            "Puntos dispersos aleatoriamente sugieren que no hay relación directa entre ambas variables.")

def _narrate_generic(chart: Dict[str, Any]) -> str:
    title = chart.get("title", "Gráfico")
    return f"Análisis visual de: {title}. Permite comparar métricas clave para la toma de decisiones."

# --- Master Function ---

def generate_chart_story(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    """Genera un párrafo explicativo en HTML para un gráfico dado."""
    ctype = chart.get("type")
    try:
        if ctype == "bar": return _narrate_bar(df, chart)
        if ctype == "line": return _narrate_line(df, chart)
        if ctype == "pie": return _narrate_pie(df, chart)
        if ctype == "calendar": return _narrate_calendar(df, chart)
        if ctype == "treemap": return _narrate_treemap(df, chart)
        if ctype == "scatter": return _narrate_scatter(df, chart)
    except Exception:
        return _narrate_generic(chart)
        
    return _narrate_generic(chart)