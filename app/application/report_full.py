# app/application/report_full.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

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
    """
    out_html.parent.mkdir(parents=True, exist_ok=True)

    def _btn(href: str, text: str) -> str:
        if not href:
            return ""
        return f'<a class="btn" href="{href}" target="_blank" rel="noopener">{text}</a>'

    html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Reporte Ejecutivo - CleanDataAI</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial;margin:24px}}
h1{{margin:0 0 12px}} h2{{margin:20px 0 8px}}
.card{{border:1px solid #e5e7eb;border-radius:14px;padding:16px;margin:12px 0}}
.kpi{{display:flex;gap:16px;flex-wrap:wrap}}
.kpi>div{{border:1px solid #e5e7eb;border-radius:12px;padding:10px 14px;min-width:160px}}
ul{{line-height:1.6}} code{{background:#f3f4f6;padding:2px 6px;border-radius:8px}}
.small{{color:#6b7280}}
.btn{{display:inline-block;margin-right:8px;text-decoration:none;border:1px solid #e5e7eb;padding:8px 12px;border-radius:10px;background:#fff}}
</style></head>
<body>

<h1>Reporte Ejecutivo</h1>

<div class="kpi">
  <div><b>Filas (limpio)</b><br>{quality.get("rows","-")}</div>
  <div><b>Columnas</b><br>{quality.get("cols","-")}</div>
  <div><b>Nulos (global)</b><br>{quality.get("missing_overall_pct",0):.2f}%</div>
  <div><b>Duplicados eliminados</b><br>{clean_summary.get("dropped_duplicates",0)}</div>
</div>

<div class="card">
  <h2>Limpieza aplicada</h2>
  <ul>
    <li>Trim/normalización de espacios: {", ".join(clean_summary.get("trimmed_cols", []) or ["—"])}</li>
    <li>Convertidas a <b>numérico</b>: {", ".join(clean_summary.get("numeric_cols", []) or ["—"])}</li>
    <li>Convertidas a <b>booleano</b>: {", ".join(clean_summary.get("bool_cols", []) or ["—"])}</li>
    <li>Convertidas a <b>fecha</b>: {", ".join(clean_summary.get("date_cols", []) or ["—"])}</li>
  </ul>
</div>

<div class="card">
  <h2>Calidad de datos</h2>
  <p class="small">Porcentaje de nulos por columna (top 5):</p>
  <ul>
    { "".join(f"<li><code>{k}</code>: {v:.2f}%</li>" for k,v in list(quality.get("missing_by_col_pct",{}).items())[:5]) or "<li>—</li>" }
  </ul>
</div>

<div class="card">
  <h2>Artefactos</h2>
  <p>
    { _btn(links.get("dataset_limpio.csv",""), "Descargar CSV limpio") }
    { _btn(links.get("dashboard.html",""), "Ver Dashboard") }
    { _btn(links.get("reporte_perfilado.html",""), "Reporte de Perfilado") }
  </p>
  <p class="small">Este documento resume la sesión y enlaza a los artefactos completos.</p>
</div>

<p class="small">Generado automáticamente por CleanDataAI.</p>
</body></html>
"""
    out_html.write_text(html, encoding="utf-8")
    return out_html
