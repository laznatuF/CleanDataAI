# app/application/report_full.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json


def build_full_report(
    clean_summary: Dict[str, Any],
    quality: Dict[str, Any],
    links: Dict[str, str],
    out_html: Path,
) -> Path:
    """
    Genera 'reporte_integrado.html' combinando:
      - Resumen de limpieza (clean_summary)
      - Métricas de calidad (quality)
      - Enlaces a artifacts (links)
    Deja por escrito TODO lo que se hizo en la fase de limpieza.
    """
    out_html.parent.mkdir(parents=True, exist_ok=True)

    def _btn(href: str, text: str) -> str:
        if not href:
            return ""
        return f'<a class="btn" href="{href}" target="_blank" rel="noopener">{text}</a>'

    # ---------- Info de limpieza ----------
    trimmed_cols = list(clean_summary.get("trimmed_cols") or [])
    date_cols = list(clean_summary.get("date_cols") or [])
    money_extracted = list(clean_summary.get("money_cols_extracted") or [])
    currency_norm = list(clean_summary.get("currency_normalized") or [])
    imputed = dict(clean_summary.get("imputed") or {})
    struct_start = list(clean_summary.get("structural_fixes_start") or [])
    struct_mid = list(clean_summary.get("structural_fixes_middle") or [])
    dropped_dup = int(clean_summary.get("dropped_duplicates") or 0)

    # ---------- KPIs de calidad ----------
    rows = quality.get("rows", "-")
    cols = quality.get("cols", "-")
    missing_overall = float(quality.get("missing_overall_pct", 0.0) or 0.0)
    missing_by_col = quality.get("missing_by_col_pct") or {}

    # Top 10 columnas con más nulos
    top_missing = sorted(
        missing_by_col.items(), key=lambda kv: kv[1], reverse=True
    )[:10]
    if top_missing:
        missing_html = "".join(
            f"<li><code>{k}</code>: {v:.2f}%</li>" for k, v in top_missing
        )
    else:
        missing_html = "<li>—</li>"

    # ---------- Descripciones de cada paso ----------

    # Trim de texto
    if trimmed_cols:
        trimmed_example = ", ".join(trimmed_cols[:8])
        if len(trimmed_cols) > 8:
            trimmed_example += "…"
        trimmed_desc = (
            f"Se recortaron espacios y se normalizaron vacíos en "
            f"<b>{len(trimmed_cols)}</b> columnas. "
            f"Ejemplos: <code>{trimmed_example}</code>."
        )
    else:
        trimmed_desc = (
            "No se detectaron columnas de texto a las que aplicar trim de espacios."
        )

    # Correcciones estructurales
    struct_msgs = struct_start + struct_mid
    if struct_msgs:
        struct_html = "".join(f"<li>{msg}</li>" for msg in struct_msgs)
    else:
        struct_html = (
            "<li>No se aplicaron correcciones estructurales "
            "(desplazamientos de columnas).</li>"
        )

    # Fechas
    if date_cols:
        dates_desc = (
            f"Se normalizaron <b>{len(date_cols)}</b> columnas como fecha "
            f"en formato ISO <code>YYYY-MM-DD</code>: {', '.join(date_cols)}."
        )
    else:
        dates_desc = (
            "No se detectaron columnas que cumplieran criterios suficientes "
            "para ser tratadas como fecha."
        )

    # Dinero y divisas
    if money_extracted:
        money_desc = (
            "Se detectaron columnas con valores monetarios y se extrajeron "
            f"números y divisas en: {', '.join(money_extracted)}."
        )
    else:
        money_desc = (
            "No se detectaron columnas de texto con patrones claros de montos y divisas."
        )

    if currency_norm:
        currency_desc = (
            "Se generaron columnas unificadas en CLP para análisis comparable: "
            f"{', '.join(currency_norm)}."
        )
    else:
        currency_desc = "No se generaron columnas de montos unificados en CLP."

    # Imputación
    if imputed:
        imputed_items = "".join(
            f"<li><code>{col}</code>: {cnt} valores faltantes rellenados</li>"
            for col, cnt in sorted(imputed.items(), key=lambda kv: kv[0])
        )
        imputed_intro = (
            "Se aplicó imputación de valores faltantes según las reglas definidas:"
        )
    else:
        imputed_items = (
            "<li>No se rellenaron valores faltantes de forma automática.</li>"
        )
        imputed_intro = (
            "No se aplicó imputación automática de valores faltantes "
            "(o no fue necesaria)."
        )

    # Outliers (opcional: si vienen en quality)
    outliers_count = quality.get("outliers_count")
    outliers_ratio = quality.get("outliers_ratio")
    if outliers_count is not None:
        outliers_desc = (
            f"Se marcaron o filtraron <b>{int(outliers_count)}</b> registros "
            f"como atípicos ({float(outliers_ratio or 0.0):.2f}% del dataset limpio)."
        )
    else:
        outliers_desc = (
            "No se incluyen métricas de outliers en este resumen "
            "(pueden verse en el dashboard)."
        )

    # ---------- Links ----------
    href_clean = links.get("dataset_limpio.csv", "")
    href_dash = links.get("dashboard.html", "")
    href_profile = links.get("reporte_perfilado.html", "")
    href_original_csv = links.get("dataset_original.csv", "")
    href_original_raw = links.get("input_original", "")
    href_narrative = links.get("reporte_narrativo.html", "")

    # JSON técnico para el punto 4
    pretty_clean_summary = json.dumps(clean_summary or {}, ensure_ascii=False, indent=2)
    pretty_quality = json.dumps(quality or {}, ensure_ascii=False, indent=2)

    # ---------- HTML ----------
    html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Reporte Ejecutivo - CleanDataAI</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial;margin:24px}}
h1{{margin:0 0 12px}} h2{{margin:20px 0 8px}} h3{{margin:14px 0 6px}}
.card{{border:1px solid #e5e7eb;border-radius:14px;padding:16px;margin:12px 0}}
.kpi{{display:flex;gap:16px;flex-wrap:wrap}}
.kpi>div{{border:1px solid #e5e7eb;border-radius:12px;padding:10px 14px;min-width:160px}}
ul{{line-height:1.6}} code{{background:#f3f4f6;padding:2px 6px;border-radius:8px}}
.small{{color:#6b7280}}
.btn{{display:inline-block;margin:4px 8px 4px 0;text-decoration:none;
      border:1px solid #e5e7eb;padding:8px 12px;border-radius:10px;background:#fff}}
.section-title{{font-size:1.05rem;font-weight:600}}
pre{{background:#0b1020;color:#e5e7eb;padding:12px 14px;border-radius:10px;
     font-size:12px;overflow-x:auto;max-height:380px}}
details summary{{cursor:pointer;font-weight:500}}
</style></head>
<body>

<h1>Reporte Ejecutivo</h1>

<div class="kpi">
  <div><b>Filas (dataset limpio)</b><br>{rows}</div>
  <div><b>Columnas</b><br>{cols}</div>
  <div><b>Nulos (global)</b><br>{missing_overall:.2f}%</div>
  <div><b>Duplicados eliminados</b><br>{dropped_dup}</div>
</div>

<div class="card">
  <h2 class="section-title">1. Archivos procesados</h2>
  <p>
    {_btn(href_original_raw, "Ver archivo original (formato cargado)")}
    {_btn(href_original_csv, "Ver dataset original como CSV")}
    {_btn(href_clean, "Ver/descargar CSV limpio")}
    {_btn(href_dash, "Abrir dashboard interactivo")}
    {_btn(href_profile, "Reporte de perfilado")}
    {_btn(href_narrative, "Reporte narrativo AI")}
  </p>
  <p class="small">
    Usa estos enlaces para comparar el archivo original con el dataset limpio y revisar el dashboard generado.
  </p>
</div>

<div class="card">
  <h2 class="section-title">2. Calidad de datos tras la limpieza</h2>
  <p class="small">Porcentaje de valores nulos por columna (top 10):</p>
  <ul>
    {missing_html}
  </ul>
</div>

<div class="card">
  <h2 class="section-title">3. Detalle de todas las transformaciones aplicadas</h2>

  <h3>3.1 Correcciones estructurales</h3>
  <ul>
    {struct_html}
  </ul>

  <h3>3.2 Normalización de texto y espacios</h3>
  <p>{trimmed_desc}</p>

  <h3>3.3 Tratamiento de fechas</h3>
  <p>{dates_desc}</p>

  <h3>3.4 Tratamiento de montos y divisas</h3>
  <p>{money_desc}</p>
  <p>{currency_desc}</p>

  <h3>3.5 Imputación de valores faltantes</h3>
  <p>{imputed_intro}</p>
  <ul>
    {imputed_items}
  </ul>

  <h3>3.6 Duplicados y outliers</h3>
  <ul>
    <li>Filas duplicadas eliminadas: <b>{dropped_dup}</b></li>
    <li>{outliers_desc}</li>
  </ul>
</div>

<div class="card">
  <h2 class="section-title">4. Detalle completo (CSV Preview + JSON técnico)</h2>
  <p>
    Para revisar <b>todo el contenido del dataset limpio</b> fila por fila, abre la vista
    <b>“Archivo limpio (CSV)”</b> en la aplicación (csv preview). Desde el panel de estado,
    usa el botón <i>“Ver”</i> del bloque “Archivo limpio (CSV)” o descarga el archivo desde aquí:
  </p>
  <p>
    {_btn(href_clean, "Abrir/descargar CSV limpio")}
  </p>
  <p class="small">
    Debajo se muestra además el JSON completo con todas las métricas internas de la limpieza
    (por si necesitas una trazabilidad 100% técnica).
  </p>

  <details open>
    <summary>clean_summary (todo lo que registró la limpieza)</summary>
    <pre>{pretty_clean_summary}</pre>
  </details>

  <details>
    <summary>quality (métricas de calidad utilizadas en este reporte)</summary>
    <pre>{pretty_quality}</pre>
  </details>
</div>

<p class="small">Generado automáticamente por CleanDataAI.</p>
</body></html>
"""
    out_html.write_text(html, encoding="utf-8")
    return out_html

