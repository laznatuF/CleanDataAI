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
# 2. HELPER DE LLAMADA A API (NUEVO)
# ==========================================
def _query_groq(context_text: str, instruction: str, max_tokens: int = 150) -> str:
    """
    context_text: texto con los datos (KPIs, resúmenes de gráficos, etc.).
    instruction: reglas de estilo / rol del analista (system prompt).
    """
    client = _get_groq_client()
    if not client:
        return "IA no disponible (Verifica API Key)."

    try:
        system_content = (
            "Eres un experto en análisis de datos de negocios. "
            "Responde estrictamente basado en los datos proporcionados. "
            "No inventes información. "
            "Si los datos no son suficientes, dilo explícitamente.\n\n"
            + instruction
        )

        messages = [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": context_text,
            },
        ]

        chat_completion = client.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            temperature=0.4,
            max_tokens=max_tokens,
        )

        return chat_completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error llamando a Groq: {e}")
        return "No se pudo generar el texto con IA."


# ==========================================
# 3. HELPERS NUMÉRICOS
# ==========================================

def _fmt_number(value: float, decimals: int = 0) -> str:
    if pd.isna(value):
        return "-"
    return f"{value:,.{decimals}f}"


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


# ==========================================
# 4. CONTEXTO GLOBAL DEL DATASET
# ==========================================

def get_dataset_fingerprint(df: pd.DataFrame, spec: Dict[str, Any]) -> str:
    # 1. KPIs Globales
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

    # 2. Análisis Temporal (Cálculo Real Mensual)
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
                    # Aseguramos métrica numérica
                    df_t[metric_col] = _safe_numeric(df_t[metric_col])
                    df_t = df_t.dropna(subset=[metric_col])

                    df_t.set_index(date_col, inplace=True)
                    # 'M' = fin de mes calendario
                    monthly_data = df_t[metric_col].resample("M").sum()
                    monthly_data = monthly_data[monthly_data > 0]

                    if len(monthly_data) >= 2:
                        v_start = monthly_data.iloc[0]
                        v_end = monthly_data.iloc[-1]
                        growth = ((v_end - v_start) / v_start) * 100

                        trend_text += (
                            f" Tendencia mensual: El primer mes registró {_fmt_number(v_start)} "
                            f"y el último mes {_fmt_number(v_end)}. "
                            f"Variación total: {_fmt_number(growth, 1)}%."
                        )
        except Exception:
            trend_text += " (Cálculo de tendencia no disponible)."

    # 3. Concentración (Pareto)
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

    parts = ["CONTEXTO GLOBAL DEL NEGOCIO:", *kpi_text, trend_text]
    if pareto_text:
        parts.append(pareto_text)
    return "\n".join(parts)


# ==========================================
# 5. PREPARACIÓN LOCAL DEL GRÁFICO
# ==========================================

def _summarize_categorical_distribution(
    series: pd.Series,
    values: Optional[pd.Series] = None,
    max_items: int = 5,
    value_label: str = "valor",
) -> str:
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
        return "No se pudo calcular distribución."

    n_cats = len(grouped)
    top = grouped.head(max_items)
    chunks: List[str] = []

    for cat, val in top.items():
        pct = (val / total) * 100
        chunks.append(f"{cat}: {_fmt_number(pct, 1)}% ({_fmt_number(val)})")

    if n_cats > max_items:
        rest_val = grouped.iloc[max_items:].sum()
        rest_pct = (rest_val / total) * 100
        chunks.append(f"Otros: {_fmt_number(rest_pct, 1)}% ({_fmt_number(rest_val)})")

    return (
        f"Distribución categórica {metric_desc}. Total: {_fmt_number(total)}. Detalle: "
        + "; ".join(chunks)
    )


def _summarize_line_series(df: pd.DataFrame, x: str, y: Optional[str]) -> str:
    """
    Resume una serie temporal. Intenta primero agregar de forma MENSUAL
    (para obtener una variación tipo “inicio de periodo vs fin de periodo”),
    y si no se puede, cae a comparar el primer y último valor crudo.
    """
    if x not in df.columns:
        return "Columna temporal no encontrada."

    df_t = df.copy()
    df_t[x] = pd.to_datetime(df_t[x], errors="coerce")
    df_t = df_t.dropna(subset=[x]).sort_values(x)
    if df_t.empty:
        return "Sin fechas válidas."

    # Determinar la serie y
    if y and y in df_t.columns:
        df_t[y] = _safe_numeric(df_t[y])
        df_t = df_t.dropna(subset=[y])
    else:
        # Si no hay métrica, contamos registros por fecha
        df_t["_count"] = 1
        df_t = df_t.groupby(x)["_count"].sum().reset_index()
        y = "_count"

    if df_t.empty:
        return "Sin datos válidos para la serie temporal."

    # Intento 1: resumir mensualmente (sumatoria por mes)
    try:
        df_t = df_t.set_index(x)
        series = df_t[y]

        monthly = series.resample("M").sum()
        monthly = monthly[monthly > 0]

        if len(monthly) >= 2:
            first_val = monthly.iloc[0]
            last_val = monthly.iloc[-1]
            change_abs = last_val - first_val
            change_pct = (change_abs / first_val) * 100 if first_val else 0

            return (
                f"Serie temporal mensual '{y}' sobre '{x}'. "
                f"Inicio (primer mes): {_fmt_number(first_val)}; "
                f"Fin (último mes): {_fmt_number(last_val)}. "
                f"Variación total: {_fmt_number(change_pct, 1)}%."
            )
    except Exception:
        # Si falla la agregación mensual, seguimos al fallback
        pass

    # Fallback: comparar directamente primer y último registro
    df_t = df_t.sort_index() if isinstance(df_t.index, pd.DatetimeIndex) else df_t
    first_val = df_t[y].iloc[0]
    last_val = df_t[y].iloc[-1]
    change_abs = last_val - first_val
    change_pct = (change_abs / first_val) * 100 if first_val else 0

    return (
        f"Serie temporal '{y}' sobre '{x}'. "
        f"Inicio: {_fmt_number(first_val)}; Fin: {_fmt_number(last_val)}. "
        f"Variación: {_fmt_number(change_pct, 1)}%."
    )


def _summarize_numeric_distribution(series: pd.Series, col_name: str) -> str:
    s = _safe_numeric(series).dropna()
    if s.empty:
        return "Sin datos numéricos."
    return (
        f"Distribución '{col_name}': Min {_fmt_number(s.min())}, "
        f"Max {_fmt_number(s.max())}, Promedio {_fmt_number(s.mean())}."
    )


def _summarize_chart_data(df: pd.DataFrame, chart: Dict[str, Any]) -> str:
    enc = chart.get("encoding", {})
    x = enc.get("x", {}).get("field")
    y = enc.get("y", {}).get("field")
    val_col = y or enc.get("value", {}).get("field")
    chart_type = chart.get("type", "generic")

    try:
        if chart_type in ["bar", "pie", "treemap"]:
            cat_field = enc.get("category", {}).get("field", x)
            if cat_field in df.columns:
                if val_col and val_col in df.columns:
                    return _summarize_categorical_distribution(
                        df[cat_field],
                        df[val_col],
                        value_label=val_col,
                    )
                return _summarize_categorical_distribution(
                    df[cat_field],
                    value_label="frecuencia",
                )

        elif chart_type == "line" and x:
            return _summarize_line_series(df, x, val_col)

        elif chart_type == "histogram" and x:
            return _summarize_numeric_distribution(df[x], x)

        elif chart_type == "heatmap_pivot":
            x_f = enc.get("x", {}).get("field")
            y_f = enc.get("y", {}).get("field")
            v_f = val_col
            if x_f and y_f and v_f:
                return f"Mapa de calor {y_f} vs {x_f}. Datos complejos agregados."

    except Exception:
        pass

    return "Datos del gráfico no extraíbles."


# ==========================================
# 6. CEREBRO IA (Consultor Senior - Párrafos)
# ==========================================

def generate_chart_story(
    df: pd.DataFrame,
    chart: Dict[str, Any],
    full_spec: Optional[Dict[str, Any]] = None,
) -> str:
    global_context = (
        get_dataset_fingerprint(df, full_spec) if full_spec else "Sin contexto global."
    )
    local_data = _summarize_chart_data(df, chart)
    title = chart.get("title", "Gráfico")

    system_prompt = (
        "Actúa como un Consultor de Negocios Senior. Estás escribiendo un reporte ejecutivo.\n"
        "Recibirás datos reales calculados en Python.\n"
        "TU OBJETIVO: Escribir un análisis breve e interpretativo (máx 80 palabras).\n"
        "REGLAS CRÍTICAS DE FORMATO:\n"
        "1. Escribe un ÚNICO párrafo fluido. NO uses listas ni punteros.\n"
        "2. NO uses títulos, encabezados ni asteriscos (ej: nada de **Análisis**).\n"
        "3. Usa etiquetas HTML <b> solo para resaltar la cifra más importante.\n"
        "4. Sé directo: elimina frases de relleno."
    )

    user_msg = (
        f"--- CONTEXTO GLOBAL ---\n{global_context}\n\n"
        f"--- GRÁFICO A ANALIZAR ---\n"
        f"Título: {title}\n"
        f"Datos extraídos: {local_data}\n\n"
        "Dame el análisis estratégico:"
    )

    return _query_groq(user_msg, system_prompt, max_tokens=300)


# ==========================================
# 7. CONCLUSIÓN FINAL (Calculada + IA)
# ==========================================

def generate_executive_conclusion(df: pd.DataFrame, spec: Dict[str, Any]) -> str:
    """
    Genera una conclusión ejecutiva calculando datos reales de contexto
    (Tendencia + Top Categoría + Top Ciudad) para evitar alucinaciones.
    """
    # 1. Calcular Tendencia Temporal
    schema = spec.get("schema", {})
    date_col = schema.get("primary_date")
    metric_col = schema.get("primary_metric")
    trend_text = ""

    if date_col and date_col in df.columns and metric_col and metric_col in df.columns:
        try:
            df_t = df[[date_col, metric_col]].copy()
            df_t[date_col] = pd.to_datetime(df_t[date_col], errors="coerce")
            df_t = df_t.dropna(subset=[date_col]).sort_values(date_col)

            if not df_t.empty:
                df_t[metric_col] = _safe_numeric(df_t[metric_col])
                df_t = df_t.dropna(subset=[metric_col])

                df_t.set_index(date_col, inplace=True)
                monthly = df_t[metric_col].resample("M").sum()
                monthly = monthly[monthly > 0]

                if len(monthly) >= 2:
                    v_start = monthly.iloc[0]
                    v_end = monthly.iloc[-1]
                    growth = ((v_end - v_start) / v_start) * 100
                    trend_text = (
                        f"La tendencia financiera muestra una variación del "
                        f"{_fmt_number(growth, 1)}% entre el inicio y el fin del periodo."
                    )
        except Exception:
            pass

    # 2. Calcular Top Categoría y Ciudad
    top_driver_text = ""
    try:
        cat_col = next(
            (c for c in df.columns if "cat" in c.lower()),
            None,
        )
        city_col = next(
            (c for c in df.columns if "ciudad" in c.lower() or "city" in c.lower()),
            None,
        )

        parts: List[str] = []
        if cat_col:
            top_cat = df[cat_col].value_counts().idxmax()
            parts.append(f"la categoría líder es '{top_cat}'")

        if city_col:
            top_city = df[city_col].value_counts().idxmax()
            parts.append(f"la mayor concentración está en '{top_city}'")

        if parts:
            top_driver_text = "Se destaca que " + " y ".join(parts) + "."
    except Exception:
        pass

    # 3. Preparar el Prompt con DATOS REALES
    context = (
        f"Contexto real de los datos: {trend_text} {top_driver_text} "
        f"El dataset tiene {len(df)} registros totales."
    )

    prompt = (
        "Actúa como un Estratega de Negocios. Escribe una conclusión final compacta (máx 80 palabras).\n"
        "TU OBJETIVO: Conectar la tendencia financiera con los hallazgos operativos.\n"
        "REGLAS:\n"
        "1. NO uses títulos, ni 'Conclusión:', ni asteriscos. Texto fluido 100%.\n"
        "2. Empieza directo con una frase fuerte sobre el desempeño general.\n"
        "3. Menciona qué está sosteniendo el negocio (usa el dato de categoría/ciudad que te pasé).\n"
        "4. Cierra con una recomendación de una sola frase (ej: 'Se sugiere potenciar X...')."
    )

    return _query_groq(context, prompt, max_tokens=150)
