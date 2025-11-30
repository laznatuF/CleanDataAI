# app/application/storytelling.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import json

from app.core.config import GROQ_API_KEY, GROQ_MODEL

try:
    from groq import Groq
except ImportError:
    Groq = None


# ==========================================
# 1. CLIENTE GROQ (Lazy Load)
# ==========================================
def _get_groq_client():
    if not Groq:
        print("⚠️ Error: Librería 'groq' no instalada. Ejecuta 'pip install groq'.")
        return None

    if not GROQ_API_KEY:
        print("⚠️ Error: GROQ_API_KEY no encontrada en variables de entorno (.env).")
        return None

    return Groq(api_key=GROQ_API_KEY)


# ==========================================
# HELPERS NUMÉRICOS
# ==========================================

def _fmt_number(value: float, decimals: int = 0) -> str:
    """
    Formatea números con separador de miles y decimales.
    Usa formato estándar 1,234.5 (no se localiza a es-ES para evitar dependencias).
    """
    if pd.isna(value):
        return "-"
    return f"{value:,.{decimals}f}"


def _safe_numeric(series: pd.Series) -> pd.Series:
    """Convierte de forma segura a numérico."""
    return pd.to_numeric(series, errors="coerce")


# ==========================================
# 2. CONTEXTO GLOBAL DEL DATASET
# ==========================================

def get_dataset_fingerprint(df: pd.DataFrame, spec: Dict[str, Any]) -> str:
    """
    Analiza el CSV completo y los KPIs para crear un 'Contexto Estratégico'.
    Esto le da a la IA la visión global antes de escribir sobre un gráfico específico.
    """
    # 1. KPIs Globales del Dashboard
    kpis = spec.get("kpis", [])
    kpi_text: List[str] = []
    for k in kpis:
        val: str | float = "-"
        col = k.get("col")
        op = k.get("op")

        if op == "count_rows":
            val = _fmt_number(len(df))
        elif col and col in df.columns:
            series = _safe_numeric(df[col])
            if op == "sum":
                val = _fmt_number(series.sum())
            elif op == "mean":
                val = _fmt_number(series.mean(), decimals=2)
            elif op == "nunique":
                val = _fmt_number(df[col].nunique())
        kpi_text.append(f"- {k.get('title', 'Métrica')}: {val}")

    # 2. Análisis Temporal (si existe fecha)
    schema = spec.get("schema", {})
    date_col: Optional[str] = schema.get("primary_date")
    metric_col: Optional[str] = schema.get("primary_metric")
    trend_text = "No se detectó serie temporal clara."

    if date_col and date_col in df.columns:
        try:
            cols = [date_col]
            if metric_col and metric_col in df.columns:
                cols.append(metric_col)
            df_t = df[cols].copy()

            df_t[date_col] = pd.to_datetime(df_t[date_col], errors="coerce")
            df_t = df_t.dropna(subset=[date_col]).sort_values(date_col)

            if not df_t.empty:
                start = df_t[date_col].iloc[0]
                end = df_t[date_col].iloc[-1]
                duration = (end - start).days
                trend_text = f"Periodo analizado: del {start.date()} al {end.date()} ({duration} días)."

                if metric_col and metric_col in df_t.columns:
                    s_num = _safe_numeric(df_t[metric_col])
                    v_start = s_num.head(3).mean()
                    v_end = s_num.tail(3).mean()
                    if v_start > 0 and not pd.isna(v_end):
                        growth = ((v_end - v_start) / v_start) * 100
                        trend_text += (
                            f" Tendencia global: "
                            f"{'crecimiento' if growth >= 0 else 'caída'} "
                            f"del {_fmt_number(growth, 1)}%."
                        )
        except Exception as e:
            trend_text += f" (Error calculando tendencias: {str(e)})"

    # 3. Concentración (Pareto) sobre la primera dimensión
    pareto_text = ""
    dims: List[str] = schema.get("dims", []) or []
    if dims and metric_col and metric_col in df.columns and dims[0] in df.columns:
        dim = dims[0]
        try:
            grouped = df.groupby(dim)[metric_col].sum().sort_values(ascending=False)
            grouped = _safe_numeric(grouped)
            total_val = grouped.sum()
            if total_val > 0:
                top_3_val = grouped.head(3).sum()
                top_3_pct = (top_3_val / total_val) * 100
                top_3_labels = ", ".join([str(idx) for idx in grouped.head(3).index])
                pareto_text = (
                    f"Concentración: el Top 3 de '{dim}' "
                    f"({top_3_labels}) representa el {_fmt_number(top_3_pct, 1)}% del total."
                )
        except Exception:
            pareto_text = ""

    parts = [
        "CONTEXTO GLOBAL DEL NEGOCIO:",
        *kpi_text,
        trend_text,
    ]
    if pareto_text:
        parts.append(pareto_text)

    return "\n".join(parts)


# ==========================================
# 3. PREPARACIÓN LOCAL DEL GRÁFICO (MATEMÁTICA EXACTA)
# ==========================================

def _summarize_categorical_distribution(
    series: pd.Series,
    values: Optional[pd.Series] = None,
    max_items: int = 5,
    value_label: str = "valor",
) -> str:
    """
    Calcula tabla de categorías + participación porcentual.
    Devuelve un resumen tipo:
    'Total X. Top categorías: Ropa 41.3% (12,345); Tecnología 32.1% (9,567); Otros 8.7% (2,345)'
    """
    if values is not None:
        v = _safe_numeric(values)
        grouped = v.groupby(series).sum().sort_values(ascending=False)
        metric_desc = f"sobre '{value_label}'"
    else:
        grouped = series.value_counts(dropna=False)
        metric_desc = "por frecuencia de registros"

    grouped = grouped.dropna()
    total = grouped.sum()
    if total <= 0 or grouped.empty:
        return "No se pudo calcular una distribución categórica significativa."

    n_cats = len(grouped)
    top = grouped.head(max_items)
    chunks: List[str] = []

    for cat, val in top.items():
        pct = (val / total) * 100
        # Ejemplo que recibirá la IA: Ropa: 41.3% (12,345)
        chunks.append(f"{cat}: {_fmt_number(pct, 1)}% ({_fmt_number(val)})")

    if n_cats > max_items:
        rest_val = grouped.iloc[max_items:].sum()
        rest_pct = (rest_val / total) * 100
        chunks.append(f"Otros: {_fmt_number(rest_pct, 1)}% ({_fmt_number(rest_val)})")

    return (
        f"Distribución categórica {metric_desc}. "
        f"Total acumulado: {_fmt_number(total)}. "
        f"Categorías analizadas: {n_cats}. "
        f"Detalle principales categorías: " + "; ".join(chunks)
    )


def _summarize_line_series(
    df: pd.DataFrame,
    x: str,
    y: Optional[str],
) -> str:
    """Resumen numérico de una serie temporal."""
    if x not in df.columns:
        return f"Columna temporal '{x}' no encontrada en el dataset."

    df_t = df.copy()
    df_t[x] = pd.to_datetime(df_t[x], errors="coerce")
    df_t = df_t.dropna(subset=[x]).sort_values(x)

    if df_t.empty:
        return f"No se encontraron fechas válidas en '{x}'."

    if y and y in df_t.columns:
        df_t[y] = _safe_numeric(df_t[y])
        df_t = df_t.dropna(subset=[y])
        if df_t.empty:
            return f"Serie temporal '{y}' por '{x}' sin valores numéricos válidos."
    else:
        # Si no hay métrica explícita, contamos registros por periodo
        df_t["_count"] = 1
        y = "_count"
        df_t = df_t.groupby(x)[y].sum().reset_index()

    start_date = df_t[x].iloc[0].date()
    end_date = df_t[x].iloc[-1].date()
    n_points = len(df_t)

    s = df_t[y]
    first_val = s.iloc[0]
    last_val = s.iloc[-1]
    min_val = s.min()
    max_val = s.max()
    avg_val = s.mean()
    change_abs = last_val - first_val
    if first_val not in (0, None) and not pd.isna(first_val):
        change_pct = (change_abs / first_val) * 100
    else:
        change_pct = np.nan

    return (
        f"Serie temporal '{y}' sobre '{x}'. "
        f"Periodo: {start_date} a {end_date} con {n_points} puntos. "
        f"Valor inicial: {_fmt_number(first_val)}; valor final: {_fmt_number(last_val)} "
        f"({'+' if change_abs >= 0 else ''}{_fmt_number(change_abs)} / "
        f"{_fmt_number(change_pct, 1)}%). "
        f"Mínimo: {_fmt_number(min_val)}; máximo: {_fmt_number(max_val)}; "
        f"promedio: {_fmt_number(avg_val, 2)}."
    )


def _summarize_numeric_distribution(series: pd.Series, col_name: str) -> str:
    """Resumen estadístico compacto para histogramas."""
    s = _safe_numeric(series).dropna()
    if s.empty:
        return f"No hay datos numéricos válidos para '{col_name}'."
    desc = {
        "mínimo": s.min(),
        "p25": s.quantile(0.25),
        "mediana": s.median(),
        "p75": s.quantile(0.75),
        "máximo": s.max(),
        "promedio": s.mean(),
        "desv_std": s.std(),
        "conteo": s.count(),
    }
    parts = [
        f"{k}: {_fmt_number(v, 2) if k != 'conteo' else _fmt_number(v)}"
        for k, v in desc.items()
    ]
    return f"Distribución estadística de '{col_name}'. " + "; ".join(parts)


def _summarize_chart_data(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    """
    Extrae los datos específicos que muestra el gráfico para enviarlos a la IA.
    Aquí es donde se calcula la 'matemática exacta' (porcentajes, totales, etc.).
    """
    enc = chart.get("encoding", {})
    x = enc.get("x", {}).get("field")
    y = enc.get("y", {}).get("field")
    # A veces 'value' se usa en lugar de 'y' (ej. Pie / Treemap / Heatmap)
    val_col = y or enc.get("value", {}).get("field")
    title = chart.get("title", "Gráfico")

    if not x and chart.get("type") not in ["pie", "treemap", "heatmap_pivot", "calendar"]:
        return f"Gráfico '{title}' sin ejes de datos claros."

    chart_type = chart.get("type", "generic")

    try:
        if chart_type in ["bar", "pie", "treemap"]:
            # Para pie / treemap solemos tener category + value
            cat_field = enc.get("category", {}).get("field", x)
            if cat_field not in df.columns:
                return f"Columna categórica '{cat_field}' no encontrada en el dataset."
            if val_col and val_col in df.columns:
                return _summarize_categorical_distribution(
                    df[cat_field],
                    df[val_col],
                    max_items=5,
                    value_label=val_col,
                )
            # Conteo de frecuencia si no hay métrica numérica
            return _summarize_categorical_distribution(
                df[cat_field],
                values=None,
                max_items=5,
                value_label="frecuencia",
            )

        elif chart_type == "line":
            if not x:
                return f"Gráfico de línea '{title}' sin eje X."
            return _summarize_line_series(df, x, val_col)

        elif chart_type == "histogram":
            if x and x in df.columns:
                return _summarize_numeric_distribution(df[x], x)
            return f"Columna '{x}' no encontrada para histograma."

        elif chart_type == "heatmap_pivot":
            # Mapa de calor ciudad vs fecha/mes
            x_field = enc.get("x", {}).get("field")
            y_field = enc.get("y", {}).get("field")
            v_field = val_col
            if not (x_field and y_field and v_field):
                return "Heatmap sin ejes o valor claros."
            if not (x_field in df.columns and y_field in df.columns and v_field in df.columns):
                return "Columnas del heatmap no encontradas en el dataset."

            # Solo un pequeño resumen: cuántas combinaciones, top celda, etc.
            tmp = df[[x_field, y_field, v_field]].copy()
            tmp[v_field] = _safe_numeric(tmp[v_field])
            tmp = tmp.dropna(subset=[v_field])
            if tmp.empty:
                return "No hay datos válidos para el mapa de calor."

            pivot_sum = tmp.pivot_table(
                index=y_field,
                columns=x_field,
                values=v_field,
                aggfunc="sum",
            )
            total = pivot_sum.to_numpy().sum()
            if total <= 0:
                return "Mapa de calor sin valores positivos significativos."

            # Celda máxima
            max_val = pivot_sum.max().max()
            # Encontrar coordenadas de esa celda
            max_pos = pivot_sum.stack().idxmax()
            max_y, max_x = max_pos
            return (
                f"Mapa de calor de '{y_field}' vs '{x_field}' sobre '{v_field}'. "
                f"Total agregado: {_fmt_number(total)}. "
                f"Mayor concentración en ({max_y}, {max_x}) con {_fmt_number(max_val)}."
            )

        elif chart_type == "calendar":
            date_field = enc.get("date", {}).get("field")
            value_field = enc.get("value", {}).get("field", val_col)
            if not date_field or date_field not in df.columns:
                return "Calendario sin columna de fecha válida."
            tmp = df[[date_field]].copy()
            tmp[date_field] = pd.to_datetime(tmp[date_field], errors="coerce")
            tmp = tmp.dropna(subset=[date_field])
            if value_field and value_field in df.columns:
                tmp[value_field] = _safe_numeric(df[value_field])
                tmp = tmp.dropna(subset=[value_field])
            if tmp.empty:
                return "No hay datos válidos para el calendario."

            start = tmp[date_field].min().date()
            end = tmp[date_field].max().date()
            if value_field and value_field in tmp.columns:
                total = tmp[value_field].sum()
                return (
                    f"Calendario diario desde {start} hasta {end}. "
                    f"Total acumulado de '{value_field}': {_fmt_number(total)}."
                )
            else:
                count_days = tmp[date_field].nunique()
                total_rows = len(tmp)
                return (
                    f"Calendario diario desde {start} hasta {end}. "
                    f"{_fmt_number(count_days)} días con datos y "
                    f"{_fmt_number(total_rows)} registros."
                )

        elif chart_type == "scatter":
            x_field = enc.get("x", {}).get("field")
            y_field = enc.get("y", {}).get("field")
            if not x_field or not y_field:
                return "Gráfico de dispersión sin ejes claros."
            if not (x_field in df.columns and y_field in df.columns):
                return "Columnas del scatter no encontradas en el dataset."

            tmp = df[[x_field, y_field]].copy()
            tmp[x_field] = _safe_numeric(tmp[x_field])
            tmp[y_field] = _safe_numeric(tmp[y_field])
            tmp = tmp.dropna()
            if tmp.empty:
                return "No hay datos numéricos válidos para el scatter."

            corr = tmp[x_field].corr(tmp[y_field])
            return (
                f"Dispersión entre '{x_field}' y '{y_field}'. "
                f"Registros válidos: {_fmt_number(len(tmp))}. "
                f"Correlación aproximada: {_fmt_number(corr, 2)}."
            )

        # Fallback genérico: tratamos como categórico
        cat_field = x if x in df.columns else None
        if not cat_field:
            return f"Gráfico '{title}' sin columnas reconocibles."
        if val_col and val_col in df.columns:
            return _summarize_categorical_distribution(
                df[cat_field],
                df[val_col],
                max_items=5,
                value_label=val_col,
            )
        return _summarize_categorical_distribution(
            df[cat_field],
            None,
            max_items=5,
            value_label="frecuencia",
        )

    except Exception as e:
        return f"No se pudieron extraer datos detallados del gráfico '{title}': {e}"


# ==========================================
# 4. CEREBRO IA (Consultor Senior)
# ==========================================

def generate_chart_story(
    df: pd.DataFrame,
    chart: Dict[str, Any],
    full_spec: Optional[Dict[str, Any]] = None,
) -> str:
    client = _get_groq_client()

    # Check de fallo inicial
    if not client:
        return (
            f"Análisis visual de: <b>{chart.get('title')}</b>. "
            "<br><span style='color:red; font-size:0.8em;'>(Error: Falta API Key de Groq o librería no instalada)</span>"
        )

    # Preparar Prompt
    global_context = (
        get_dataset_fingerprint(df, full_spec)
        if full_spec is not None
        else "Sin contexto global disponible."
    )
    local_data = _summarize_chart_data(df, chart)
    title = chart.get("title", "Gráfico")

    system_prompt = (
        "Actúa como un Consultor de Negocios Senior (Nivel McKinsey/BCG). Estás escribiendo un reporte ejecutivo.\n"
        "Recibirás:\n"
        "1. CONTEXTO GLOBAL: La salud general del dataset (KPIs, tendencias macro).\n"
        "2. DATOS DEL GRÁFICO: Un resumen numérico exacto de la visualización (con porcentajes y totales calculados en Python).\n\n"
        "TU OBJETIVO: Escribir un párrafo de análisis (aprox 60-80 palabras) que INTERPRETE los datos.\n"
        "REGLAS:\n"
        "- NO describas obviedades ('La barra más alta es X'). Di POR QUÉ importa ('X lidera el mercado, representando el 40% del total').\n"
        "- Usa etiquetas HTML <b> para resaltar cifras y nombres clave.\n"
        "- Conecta el hallazgo local con el contexto global si es posible.\n"
        "- Usa un tono profesional, directo y perspicaz en Español neutro."
    )

    user_msg = (
        f"--- CONTEXTO GLOBAL ---\n{global_context}\n\n"
        f"--- GRÁFICO A ANALIZAR ---\n"
        f"Título: {title}\n"
        f"Datos extraídos (ya calculados con Python): {local_data}\n\n"
        "Dame el análisis estratégico:"
    )

    try:
        resp = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            model=GROQ_MODEL,
            temperature=0.3,  # Bajo para ser preciso y no alucinar
            max_tokens=300,
        )
        return resp.choices[0].message.content

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error Groq AI: {error_msg}")
        # Devolvemos el error visible en el PDF para que puedas depurar
        return (
            f"Análisis visual de: <b>{title}</b>.<br>"
            f"<span style='color:red; font-size:0.8em; background:#fee;'>Error de IA: {error_msg}</span>"
        )


# ==========================================
# 5. CONCLUSIÓN FINAL (Para el final del reporte)
# ==========================================

def generate_executive_conclusion(df: pd.DataFrame, spec: Dict[str, Any]) -> str:
    """Genera un párrafo final de cierre para todo el reporte."""
    client = _get_groq_client()
    if not client:
        return ""

    context = get_dataset_fingerprint(df, spec)
    prompt = (
        "Basado en este contexto global del negocio, escribe una 'Conclusión Ejecutiva' de 1 párrafo.\n"
        "Resume el rendimiento general, destaca la métrica más impactante y da 1 recomendación estratégica breve.\n"
        "Usa HTML <b> para resaltar lo importante."
    )
    try:
        resp = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un experto estratega de datos."},
                {"role": "user", "content": f"{context}\n\n{prompt}"},
            ],
            model=GROQ_MODEL,
            temperature=0.4,
            max_tokens=300,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"❌ Error Groq IA (conclusión): {e}")
        return ""
