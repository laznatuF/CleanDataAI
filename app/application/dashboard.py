# app/application/dashboard.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import json
import pandas as pd
import numpy as np
import re


def _pick_cols(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Heurística: (date_col, category_col, amount_col)."""
    date_col = None
    # prioridad: dtype datetime; si no, nombres típicos
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            date_col = c
            break
    if not date_col:
        for c in df.columns:
            if re.search(r"(fecha|date|fecha?_)", c, re.I):
                try:
                    tmp = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
                    if tmp.notna().mean() > 0.7:
                        df[c] = tmp
                        date_col = c
                        break
                except Exception:
                    continue

    # categoría: object con cardinalidad razonable
    cat_col = None
    for c in df.select_dtypes(include=["object"]).columns:
        u = df[c].nunique(dropna=True)
        if 2 <= u <= 30:
            cat_col = c
            break

    # monto: numérica, preferencia por nombres comunes
    amount_col = None
    num_cols = list(df.select_dtypes(include=[np.number]).columns)
    if num_cols:
        prefer = [c for c in num_cols if re.search(r"(monto|importe|amount|total|valor|precio|costo)", c, re.I)]
        amount_col = prefer[0] if prefer else num_cols[0]

    return date_col, cat_col, amount_col


def _aggregate(df: pd.DataFrame, date_col: Optional[str], cat_col: Optional[str], amount_col: Optional[str]) -> Dict[str, Any]:
    ag: Dict[str, Any] = {}
    # KPIs
    ag["kpi_count"] = int(len(df))
    if amount_col:
        s = pd.to_numeric(df[amount_col], errors="coerce")
        ag["kpi_sum"] = float(np.nansum(s))
        ag["kpi_mean"] = float(np.nanmean(s)) if len(s) else 0.0
    else:
        ag["kpi_sum"] = None
        ag["kpi_mean"] = None

    # Serie temporal por fecha
    if date_col and amount_col:
        tmp = df.copy()
        tmp = tmp[[date_col, amount_col]].dropna()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
        tmp = tmp.dropna(subset=[date_col])
        ts = tmp.groupby(tmp[date_col].dt.to_period("D"))[amount_col].sum().sort_index()
        ts.index = ts.index.astype(str)
        ag["timeseries"] = {"labels": list(ts.index), "values": [float(x) for x in ts.values]}
    elif date_col:
        tmp = df.copy()
        tmp = tmp[[date_col]].dropna()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
        tmp = tmp.dropna(subset=[date_col])
        ts = tmp.groupby(tmp[date_col].dt.to_period("D")).size().sort_index()
        ts.index = ts.index.astype(str)
        ag["timeseries"] = {"labels": list(ts.index), "values": [int(x) for x in ts.values]}
    else:
        ag["timeseries"] = None

    # Top categorías
    if cat_col and amount_col:
        grp = (
            df.groupby(cat_col)[amount_col]
            .agg(["count", "sum", "mean"])
            .sort_values("sum", ascending=False)
            .head(10)
            .round(2)
        )
        ag["by_category"] = {
            "labels": grp.index.tolist(),
            "count": grp["count"].astype(int).tolist(),
            "sum": grp["sum"].astype(float).tolist(),
            "mean": grp["mean"].astype(float).tolist(),
        }
    elif cat_col:
        vc = df[cat_col].value_counts().head(10)
        ag["by_category"] = {"labels": vc.index.tolist(), "count": vc.astype(int).tolist()}
    else:
        ag["by_category"] = None

    ag["columns"] = {
        "date": date_col,
        "category": cat_col,
        "amount": amount_col,
    }
    return ag


def generate_dashboard_html(df_clean: pd.DataFrame, out_dir: Path, csv_rel_name: str = "dataset_limpio.csv") -> Path:
    """
    Genera artifacts/dashboard.html con:
      - KPIs (conteo, suma, media)
      - Línea temporal (si hay fecha)
      - Barras por categoría (si hay categórica)
    No requiere servidor extra: gráficos con Chart.js (CDN).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_html = out_dir / "dashboard.html"

    # Selección de columnas y agregaciones
    date_col, cat_col, amount_col = _pick_cols(df_clean)
    ag = _aggregate(df_clean, date_col, cat_col, amount_col)

    # HTML (simple y bonito)
    html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Dashboard - CleanDataAI</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="preconnect" href="https://cdn.jsdelivr.net"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial;margin:24px}}
h1{{margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.card{{border:1px solid #e5e7eb;border-radius:14px;padding:16px}}
.kpi{{font-size:28px;font-weight:700}}
.small{{color:#6b7280}}
.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 16px}}
button,a.btn{{padding:8px 12px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;text-decoration:none}}
</style></head>
<body>
<h1>Dashboard</h1>

<div class="toolbar">
  <a class="btn" href="{csv_rel_name}" target="_blank">Descargar CSV limpio</a>
  {"<span class='small'>Fecha: <b>"+str(date_col)+"</b></span>" if date_col else ""}
  {"<span class='small'>Categoría: <b>"+str(cat_col)+"</b></span>" if cat_col else ""}
  {"<span class='small'>Monto: <b>"+str(amount_col)+"</b></span>" if amount_col else ""}
</div>

<div class="grid">
  <div class="card">
    <div class="small">Filas</div>
    <div class="kpi">{ag["kpi_count"]}</div>
  </div>
  <div class="card">
    <div class="small">Suma</div>
    <div class="kpi">{('-' if ag['kpi_sum'] is None else round(ag['kpi_sum'],2))}</div>
  </div>
  <div class="card">
    <div class="small">Media</div>
    <div class="kpi">{('-' if ag['kpi_mean'] is None else round(ag['kpi_mean'],2))}</div>
  </div>
</div>

{"<div class='card' style='margin-top:16px'><h3>Serie temporal</h3><canvas id='ts'></canvas></div>" if ag["timeseries"] else ""}
{"<div class='card' style='margin-top:16px'><h3>Top categorías</h3><canvas id='cat'></canvas></div>" if ag["by_category"] else ""}

<script>
const AGG = {json.dumps(ag, ensure_ascii=False)};
function makeTs() {{
  if (!AGG.timeseries) return;
  const ctx = document.getElementById('ts');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: AGG.timeseries.labels,
      datasets: [{{ label: 'Serie', data: AGG.timeseries.values }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false, scales: {{ x: {{ ticks: {{ maxRotation: 0 }} }} }} }}
  }});
}}
function makeCat() {{
  if (!AGG.by_category) return;
  const ctx = document.getElementById('cat');
  const labels = AGG.by_category.labels;
  const ds = [];
  if (AGG.by_category.sum) ds.push({{ label: 'Suma', data: AGG.by_category.sum, type: 'bar' }});
  if (AGG.by_category.count) ds.push({{ label: 'Conteo', data: AGG.by_category.count, type: 'bar' }});
  if (AGG.by_category.mean) ds.push({{ label: 'Media', data: AGG.by_category.mean, type: 'line', tension: .3 }});
  new Chart(ctx, {{ data: {{ labels, datasets: ds }}, options: {{ responsive: true, maintainAspectRatio: false }} }});
}}
makeTs(); makeCat();
</script>

</body></html>
"""
    out_html.write_text(html, encoding="utf-8")
    return out_html
