# app/application/dashboard.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import pandas as pd
import numpy as np

# --------------------- Helpers numéricos/fechas ---------------------

def _strip_money_to_num(s: pd.Series) -> pd.Series:
    """Quita símbolos, miles y normaliza decimales a punto para convertir a float (para series no numéricas)."""
    s2 = (
        s.astype(str)
         .str.replace(r"[^\d\-,\.]", "", regex=True)
         .str.replace(".", "", regex=False)     # miles con punto
         .str.replace(",", ".", regex=False)    # coma decimal -> punto
    )
    return pd.to_numeric(s2, errors="coerce")

def _to_numeric_robust(s: pd.Series) -> pd.Series:
    """Si ya es numérica, respétala; si no, usa el normalizador de moneda."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    return _strip_money_to_num(s)

def _safe_to_datetime(s: pd.Series) -> pd.Series:
    """Parse robusto de fechas: intenta dayfirst y luego mes/día. Sin infer_datetime_format."""
    x = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if x.notna().mean() < 0.5:
        x2 = pd.to_datetime(s, errors="coerce", dayfirst=False)
        if x2.notna().mean() > x.notna().mean():
            return x2
    return x

def _detect_currency_prefix(df: pd.DataFrame) -> str:
    """Si hay una sola moneda en 'moneda', devuelve un prefijo para el eje Y."""
    if "moneda" not in df.columns:
        return ""
    u = df["moneda"].dropna().astype(str).str.upper().unique().tolist()
    if len(u) != 1:
        return ""
    m = u[0]
    return {
        "CLP": "$",
        "USD": "USD ",
        "EUR": "€",
        "GBP": "£",
        "ARS": "ARS ",
        "MXN": "MX$ ",
        "BRL": "R$ ",
        "PEN": "S/ ",
    }.get(m, f"{m} ")

# --------------------- Helper de título ---------------------

def _title_cfg(text: str) -> Dict[str, Any]:
    """Título legible (alineado izq., margen) para cada gráfico."""
    return {
        "text": text or "",
        "x": 0.01,
        "xanchor": "left",
        "y": 0.99,
        "yanchor": "top",
        "font": {
            "size": 16,
            "color": "#e5e7eb",
            "family": "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial",
        },
        "pad": {"t": 6, "b": 8},
    }

# --------------------- Builders Plotly ---------------------

def _build_line_month(df: pd.DataFrame, x_field: str, y_field: Optional[str], aggregate: str) -> Dict[str, Any]:
    if x_field not in df.columns:
        return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    ds = _safe_to_datetime(df[x_field])
    tmp = df.copy()
    tmp["_fecha"] = ds
    tmp = tmp[tmp["_fecha"].notna()]

    if y_field and y_field in tmp.columns:
        metric = _to_numeric_robust(tmp[y_field])
        tmp["_metric"] = metric
        if aggregate.lower() == "sum":
            ser = tmp.set_index("_fecha")["_metric"].resample("MS").sum(min_count=1).dropna()
        else:
            ser = tmp.set_index("_fecha")["_metric"].resample("MS").mean().dropna()
    else:
        ser = tmp.set_index("_fecha")["_fecha"].resample("MS").count()

    x = [d.strftime("%Y-%m") for d in ser.index.to_pydatetime()]
    y = ser.astype(float).tolist()

    return {
        "data": [{"x": x, "y": y, "type": "scatter", "mode": "lines+markers"}],
        "layout": {
            "title": "",
            "margin": {"t": 10, "r": 20, "l": 40, "b": 40},
            "xaxis": {"title": "Mes"},
            "yaxis": {"title": y_field or "Conteo"},
        },
    }

def _build_bar_top(df: pd.DataFrame, dim: Optional[str], y_field: Optional[str], aggregate: str, limit: int = 10) -> Dict[str, Any]:
    if not dim or dim not in df.columns:
        return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}

    if y_field and y_field != "__row__" and y_field in df.columns:
        vals_raw = df[y_field]
        vals = _to_numeric_robust(vals_raw)
        grp = pd.DataFrame({dim: df[dim], "_v": vals}).dropna(subset=[dim]).groupby(dim, dropna=False)["_v"]
        ser = grp.sum() if aggregate.lower() == "sum" else grp.mean()
    else:
        ser = df[dim].value_counts(dropna=False)

    ser = ser.sort_values(ascending=False).head(limit)
    x = [str(k) for k in ser.index.tolist()]
    y = ser.astype(float).tolist()

    return {
        "data": [{"x": x, "y": y, "type": "bar"}],
        "layout": {
            "title": "",
            "margin": {"t": 10, "r": 20, "l": 40, "b": 80},
            "xaxis": {"tickangle": -30, "title": dim},
            "yaxis": {"title": y_field or "Conteo"},
        },
    }

def _build_pie(df: pd.DataFrame, cat_field: Optional[str], val_field: Optional[str], aggregate: str, limit: int = 8) -> Dict[str, Any]:
    if not cat_field or cat_field not in df.columns:
        return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}

    if val_field and val_field != "__row__" and val_field in df.columns:
        vals = _to_numeric_robust(df[val_field])
        ser = (
            pd.DataFrame({cat_field: df[cat_field], "_v": vals})
            .dropna(subset=[cat_field])
            .groupby(cat_field, dropna=False)["_v"]
        )
        ser = ser.sum() if aggregate.lower() == "sum" else ser.mean()
    else:
        ser = df[cat_field].value_counts(dropna=False)

    ser = ser.sort_values(ascending=False)
    if limit and len(ser) > limit:
        head = ser.head(limit - 1)
        tail = pd.Series({"Otros": ser.iloc[limit - 1 :].sum()})
        ser = pd.concat([head, tail])

    labels = [str(k) for k in ser.index.tolist()]
    values = ser.astype(float).tolist()

    return {
        "data": [{
            "labels": labels,
            "values": values,
            "type": "pie",
            "hole": 0.45,
            "textinfo": "label+percent",
            "textposition": "outside",
            "automargin": True
        }],
        "layout": {"title": "", "margin": {"t": 10, "r": 10, "l": 10, "b": 10}},
    }

def _build_hist(values: pd.Series, title_y: str = "Frecuencia") -> Dict[str, Any]:
    x = pd.to_numeric(values, errors="coerce").dropna().astype(float).tolist()
    return {
        "data": [{"x": x, "type": "histogram"}],
        "layout": {
            "title": "",
            "margin": {"t": 10, "r": 20, "l": 40, "b": 40},
            "xaxis": {"title": ""},
            "yaxis": {"title": title_y},
        },
    }

def _build_bar_inline(rows: List[Dict[str, Any]], x_key="col", y_key="nulos", y_title="Nulos") -> Dict[str, Any]:
    x = [str(r.get(x_key, "")) for r in rows]
    y = [float(r.get(y_key, 0)) for r in rows]
    return {
        "data": [{"x": x, "y": y, "type": "bar"}],
        "layout": {
            "title": "",
            "margin": {"t": 10, "r": 20, "l": 40, "b": 80},
            "xaxis": {"tickangle": -30},
            "yaxis": {"title": y_title},
        },
    }

def _build_heatmap_pivot(df: pd.DataFrame, dim_x: Optional[str], dim_y: Optional[str],
                         val_field: Optional[str], aggregate: str) -> Dict[str, Any]:
    """Heatmap de conteos o métrica agregada."""
    if not dim_x or not dim_y or dim_x not in df.columns or dim_y not in df.columns:
        return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}

    if val_field and val_field in df.columns:
        vals = _to_numeric_robust(df[val_field])
        piv = pd.pivot_table(
            df.assign(_v=vals),
            index=dim_y, columns=dim_x, values="_v",
            aggfunc=("sum" if aggregate.lower() == "sum" else "mean")
        )
    else:
        piv = pd.pivot_table(
            df.assign(_v=1),
            index=dim_y, columns=dim_x, values="_v",
            aggfunc="count"
        )
    piv = piv.fillna(0)

    return {
        "data": [{
            "z": piv.to_numpy().tolist(),
            "x": [str(c) for c in piv.columns.tolist()],
            "y": [str(i) for i in piv.index.tolist()],
            "type": "heatmap"
        }],
        "layout": {"title": "", "xaxis": {"title": dim_x}, "yaxis": {"title": dim_y}}
    }

# --------------------- Encodings & dataset meta nulos ---------------------

def _encoding_fields(enc: Dict[str, Any]) -> List[str]:
    """Extrae los nombres de field de un encoding Vega-lite-like."""
    out: List[str] = []
    for key in ("x", "y", "category", "value"):
        v = enc.get(key, {})
        f = v.get("field")
        if isinstance(f, str) and f:
            out.append(f)
    return out

def _chart_uses_null_meta(chart: Dict[str, Any]) -> bool:
    """Devuelve True si el gráfico usa __null_pct__ o __column__ en su encoding."""
    enc = chart.get("encoding", {}) or {}
    fields = _encoding_fields(enc)
    return any(f in {"__null_pct__", "__column__"} for f in fields)

def _null_meta_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye un dataset con dos columnas:
      - __column__: nombre de columna original
      - __null_pct__: % de nulos de esa columna (0..100)
    """
    ser = df.isna().mean().mul(100.0)
    out = pd.DataFrame({"__column__": ser.index.astype(str), "__null_pct__": ser.values})
    return out

# --------------------- Mapeo spec -> Plotly ---------------------

def _chart_to_plot(df: pd.DataFrame, chart: Dict[str, Any]) -> Dict[str, Any]:
    # Si el gráfico pide meta de nulos, construimos un df ad-hoc
    df_use = _null_meta_df(df) if _chart_uses_null_meta(chart) else df

    ctype = chart.get("type")
    enc   = chart.get("encoding", {}) or {}
    title = chart.get("title", "")
    x_title = chart.get("x_title", "")
    y_title = chart.get("y_title", "")
    x_tickangle = chart.get("x_tickangle", -30)
    money_prefix = _detect_currency_prefix(df)

    if ctype == "line":
        x_field  = enc.get("x", {}).get("field")
        timeunit = (enc.get("x", {}).get("timeUnit") or "").lower()
        y_field  = enc.get("y", {}).get("field")
        agg      = (enc.get("y", {}).get("aggregate") or "count").lower()
        if not x_field or timeunit not in ("month", "ms"):
            return {"data": [], "layout": {"title": _title_cfg(title or "Sin datos")}}
        spec = _build_line_month(df_use, x_field, y_field, agg)
        spec["layout"].update({
            "title": _title_cfg(title),
            "xaxis": {"title": {"text": x_title or "Mes"}, "automargin": True},
            "yaxis": {"title": {"text": y_title or (y_field or "Valor")}, "automargin": True},
        })
        if y_field and money_prefix and df_use is df:
            spec["layout"]["yaxis"]["tickprefix"] = money_prefix
        return spec

    if ctype == "bar":
        dim     = enc.get("x", {}).get("field")
        y_field = enc.get("y", {}).get("field")
        agg     = (enc.get("y", {}).get("aggregate") or "count").lower()
        spec = _build_bar_top(df_use, dim, y_field, agg, limit=int(chart.get("limit", 10)))
        spec["layout"].update({
            "title": _title_cfg(title),
            "xaxis": {"title": {"text": x_title or (dim or "")}, "tickangle": x_tickangle, "automargin": True},
            "yaxis": {"title": {"text": y_title or (y_field or "Conteo")}, "automargin": True},
        })
        if (y_field and y_field != "__row__") and money_prefix and df_use is df:
            spec["layout"]["yaxis"]["tickprefix"] = money_prefix
        return spec

    if ctype == "pie":
        cat       = enc.get("category", {}).get("field")
        val_field = enc.get("value", {}).get("field")
        agg       = (enc.get("value", {}).get("aggregate") or "count").lower()
        spec = _build_pie(df_use, cat, val_field, agg, limit=int(chart.get("limit", 8)))
        spec["layout"].update({"title": _title_cfg(title)})
        return spec

    if ctype == "histogram":
        field = enc.get("x", {}).get("field")
        if not field or field not in df_use.columns:
            return {"data": [], "layout": {"title": _title_cfg(title or "Sin datos")}}
        spec = _build_hist(df_use[field], title_y=y_title or "Frecuencia")
        spec["layout"].update({
            "title": _title_cfg(title),
            "xaxis": {"title": {"text": x_title or (field or "")}, "automargin": True},
            "yaxis": {"automargin": True},
        })
        return spec

    if ctype == "heatmap":
        dim_x = enc.get("x", {}).get("field")
        dim_y = enc.get("y", {}).get("field")
        val_f = enc.get("value", {}).get("field")
        agg   = (enc.get("value", {}).get("aggregate") or "sum").lower()
        spec = _build_heatmap_pivot(df, dim_x, dim_y, val_f, agg)
        spec["layout"].update({
            "title": _title_cfg(title),
            "xaxis": {"title": {"text": x_title or (dim_x or "")}, "automargin": True},
            "yaxis": {"title": {"text": y_title or (dim_y or "")}, "automargin": True},
        })
        return spec

    if chart.get("data_inline"):
        spec = _build_bar_inline(chart["data_inline"])
        spec["layout"].update({
            "title": _title_cfg(title),
            "xaxis": {"title": {"text": x_title or " "}, "tickangle": x_tickangle, "automargin": True},
            "yaxis": {"title": {"text": y_title or " "}, "automargin": True},
        })
        return spec

    return {"data": [], "layout": {"title": _title_cfg(title or "Sin datos")}}

# --------------------- KPIs ---------------------

def _eval_kpi(df: pd.DataFrame, kpi: Dict[str, Any]) -> str:
    op = (kpi.get("op") or "").lower()
    col = kpi.get("col")
    if op == "count_rows":
        return f"{len(df):,}".replace(",", ".")
    if op in ("sum", "mean") and col in df.columns:
        x = _to_numeric_robust(df[col])
        val = float(x.sum()) if op == "sum" else (float(x.mean()) if x.notna().any() else 0.0)
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if op == "nunique" and col in df.columns:
        return f"{df[col].nunique(dropna=True):,}".replace(",", ".")
    if op == "ratio_gt_zero" and col in df.columns:
        x = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return f"{(x.gt(0).mean()*100):.2f}%"
    if op == "ratio_true" and col in df.columns:
        s = df[col].astype(str).str.lower().isin(["true", "1", "t", "y", "sí", "si"])
        return f"{(s.mean()*100):.2f}%"
    return "—"

# --------------------- Generación del HTML ---------------------

def generate_dashboard_html(
    df: pd.DataFrame,
    artifacts_dir: Path,
    csv_rel_name: str = "dataset_limpio.csv",
    auto_spec: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Genera un HTML oscuro con KPIs y 4 gráficos Plotly a partir de auto_spec.
    - Aprovecha todo el ancho (cuando se oculta el panel, el grid pasa a 2 columnas).
    - Títulos visibles (margen superior + alineación).
    - Redimensiona correctamente al cambiar el layout.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / "dashboard.html"

    title = "Dashboard automático"
    kpis: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []

    if auto_spec:
        dash = (auto_spec.get("dashboards") or [{}])[0]
        title = dash.get("title") or title
        kpis = auto_spec.get("kpis", [])[:3]
        chart_ids = dash.get("charts", [])[:4]
        all_charts = {c["id"]: c for c in auto_spec.get("charts", [])}
        charts = [all_charts[cid] for cid in chart_ids if cid in all_charts]

    kpi_cards = []
    for k in kpis:
        val = _eval_kpi(df, k)
        kpi_cards.append(f"""
          <div class="card">
            <div class="kpi-title">{k.get('title','KPI')}</div>
            <div class="kpi-value">{val}</div>
          </div>
        """)

    plots: List[Dict[str, Any]] = []
    for idx, ch in enumerate(charts[:4], start=1):
        p = _chart_to_plot(df, ch)
        plots.append({"container": f"chart-{idx}", "data": p["data"], "layout": p["layout"]})

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  :root {{ --gap: 18px; --left: 300px; --right: 340px; }}
  @media (min-width: 1600px) {{ :root {{ --left: 320px; --right: 380px; }} }}

  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0f172a; color:#e2e8f0; }}
  header {{ padding:16px 24px; background:#0b1220; border-bottom:1px solid #1f2937; }}
  header .bar {{ display:flex; align-items:center; gap:12px; }}
  header .t {{ font-size:20px; font-weight:700; letter-spacing:.2px; flex:1; }}
  header .actions button {{
    background:#111827; border:1px solid #1f2937; color:#93c5fd; padding:6px 10px; border-radius:10px; cursor:pointer;
  }}
  header .actions button:hover {{ border-color:#284268; color:#bfdbfe; }}

  .container {{ width:100%; margin:0 auto; display:grid; gap:var(--gap); padding:var(--gap); }}
  .container.no-side {{ grid-template-columns: var(--left) 1fr; }}
  .container.with-side {{ grid-template-columns: var(--left) 1fr var(--right); }}

  .left, .center, .right {{ display:flex; flex-direction:column; gap:var(--gap); }}
  .center {{ display:grid; grid-template-columns: 1fr 1fr; gap:var(--gap); }}

  .card {{ background:#111827; border:1px solid #1f2937; border-radius:14px; padding:16px; }}
  .kpi-title {{ font-size:12px; color:#93c5fd; text-transform:uppercase; letter-spacing:.06em; }}
  .kpi-value {{ font-size:30px; font-weight:800; margin-top:6px; }}
  .muted {{ color:#9ca3af; font-size:12px; }}
  a {{ color:#93c5fd; text-decoration:none; }} a:hover {{ text-decoration:underline; }}

  .plot {{ height: clamp(340px, 46vh, 560px); }}
  .plot-tall {{ height: clamp(360px, 50vh, 600px); }}

  .hidden {{ display:none; }}

  @media (max-width: 1200px) {{
    .container.no-side, .container.with-side {{ grid-template-columns: 1fr; }}
    .center {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="t">{title}</div>
      <div class="actions">
        <button id="toggleSide">Mostrar filtros & esquema</button>
      </div>
    </div>
  </header>

  <div id="grid" class="container no-side">
    <div class="left">
      {"".join(kpi_cards) if kpi_cards else '<div class="card"><div class="kpi-title">Info</div><div class="kpi-value">Sin KPIs</div></div>'}
      <div class="card">
        <div class="kpi-title">Datos</div>
        <div class="muted">Filas: {len(df):,} · Columnas: {df.shape[1]}</div>
        <div style="margin-top:8px"><a href="./{csv_rel_name}" target="_blank">Descargar CSV limpio</a></div>
      </div>
    </div>

    <div class="center">
      <div id="chart-1" class="card plot"></div>
      <div id="chart-2" class="card plot"></div>
      <div id="chart-3" class="card plot-tall"></div>
      <div id="chart-4" class="card plot-tall"></div>
    </div>

    <div id="side" class="right hidden">
      <div class="card">
        <div class="kpi-title">Filtros</div>
        <pre class="muted" style="white-space:pre-wrap">{json.dumps(auto_spec.get("filters", []) if auto_spec else [], ensure_ascii=False, indent=2)}</pre>
      </div>
      <div class="card">
        <div class="kpi-title">Schema</div>
        <pre class="muted" style="white-space:pre-wrap">{json.dumps(auto_spec.get("schema", {}) if auto_spec else {{}}, ensure_ascii=False, indent=2)}</pre>
      </div>
    </div>
  </div>

  <script>
    const PLOTS = {json.dumps(plots, ensure_ascii=False)};

    const baseLayout = {{
      paper_bgcolor: '#111827',
      plot_bgcolor:  '#111827',
      font: {{ color: '#e2e8f0', size: 14 }},
      margin: {{ t: 96, r: 28, b: 56, l: 64 }},
      xaxis: {{ gridcolor: '#374151', automargin: true, title: {{ standoff: 12 }} }},
      yaxis: {{ gridcolor: '#374151', automargin: true, title: {{ standoff: 12 }} }},
      legend: {{ font: {{ size: 12 }} }}
    }};

    function renderAll() {{
      for (const p of PLOTS) {{
        const el = document.getElementById(p.container);
        const layout = Object.assign({{}}, baseLayout, p.layout || {{}});
        if (p.layout?.xaxis) layout.xaxis = Object.assign({{}}, baseLayout.xaxis, p.layout.xaxis);
        if (p.layout?.yaxis) layout.yaxis = Object.assign({{}}, baseLayout.yaxis, p.layout.yaxis);
        Plotly.newPlot(el, p.data, layout, {{ responsive: true, displayModeBar: false }});
      }}
    }}

    function resizeAll() {{
      for (const p of PLOTS) {{
        const el = document.getElementById(p.container);
        Plotly.Plots.resize(el);
      }}
    }}

    (function init() {{
      renderAll();
      window.addEventListener('resize', resizeAll);
      const btn = document.getElementById('toggleSide');
      const side = document.getElementById('side');
      const grid = document.getElementById('grid');
      if (btn && side && grid) {{
        btn.addEventListener('click', () => {{
          side.classList.toggle('hidden');
          const showing = !side.classList.contains('hidden');
          grid.classList.toggle('with-side', showing);
          grid.classList.toggle('no-side', !showing);
          setTimeout(resizeAll, 50);
          btn.textContent = showing ? 'Ocultar filtros & esquema' : 'Mostrar filtros & esquema';
        }});
      }}
    }})();
  </script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    return out