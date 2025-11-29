# app/application/dashboard.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import json
import pandas as pd
import numpy as np

# --- MAPAS DE TRADUCCIÓN A ESPAÑOL ---
MESES_ES_FULL = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}
MESES_ES_ABR = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
}

def _ensure_series(data: Union[pd.Series, pd.DataFrame]) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        return data.iloc[:, 0]
    return data

def _strip_money_to_num(s: pd.Series) -> pd.Series:
    s = _ensure_series(s)
    s2 = (s.astype(str).str.replace(r"[^\d\-,\.]", "", regex=True)
          .str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s2, errors="coerce")

def _to_numeric_robust(s: pd.Series) -> pd.Series:
    s = _ensure_series(s)
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    return _strip_money_to_num(s)

def _safe_to_datetime(s: pd.Series) -> pd.Series:
    s = _ensure_series(s)
    try:
        return pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")
    except ValueError:
        return pd.to_datetime(s, errors="coerce", dayfirst=True)

def _title_cfg(text: str) -> Dict[str, Any]:
    return {
        "text": text or "", "x": 0.01, "xanchor": "left", "y": 0.96, "yanchor": "top",
        "font": {"size": 14, "color": "#e5e7eb", "family": "Inter, sans-serif"},
        "pad": {"t": 4, "b": 4}
    }

# --------------------- BUILDERS ---------------------

def _build_line_month(df: pd.DataFrame, x_field: str, y_field: Optional[str], aggregate: str) -> Dict[str, Any]:
    if x_field not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    ds = _safe_to_datetime(df[x_field])
    tmp = pd.DataFrame({"_fecha": ds})
    tmp = tmp[tmp["_fecha"].notna()]
    if y_field and y_field in df.columns:
        tmp["_metric"] = _to_numeric_robust(df[y_field])
        ser = tmp.set_index("_fecha")["_metric"].resample("MS").sum() if aggregate=="sum" else tmp.set_index("_fecha")["_metric"].resample("MS").mean()
    else:
        ser = tmp.set_index("_fecha").resample("MS").size()
    x = [f"{MESES_ES_ABR.get(d.month, '')} {d.year}" for d in ser.index]
    return {
        "data": [{"x": x, "y": ser.tolist(), "type": "scatter", "mode": "lines+markers", "line": {"color": "#60a5fa", "width": 3}}],
        "layout": {"title": "", "xaxis": {"title": "Mes"}, "yaxis": {"title": y_field or "Valor"}}
    }

def _build_heatmap_pivot(df: pd.DataFrame, date_col: str, city_col: str, val_col: str) -> Dict[str, Any]:
    if not all(c in df.columns for c in [date_col, city_col]): return {"data": [], "layout": {"title": _title_cfg("Faltan datos")}}
    ds = _safe_to_datetime(df[date_col])
    city_s = df[city_col].astype(str).str.title()
    vals = _to_numeric_robust(df[val_col]) if val_col in df.columns else pd.Series(1, index=df.index)
    tmp = pd.DataFrame({"date": ds, "city": city_s, "val": vals}).dropna()
    tmp["period"] = tmp["date"].dt.to_period("M").dt.to_timestamp()
    piv = pd.pivot_table(tmp, index="city", columns="period", values="val", aggfunc="sum").fillna(0)
    if len(piv) > 25:
        top = piv.sum(axis=1).sort_values(ascending=False).head(25).index
        piv = piv.loc[top]
    x_labels = [f"{MESES_ES_ABR.get(d.month, '')} {d.year}" for d in piv.columns]
    y_labels = piv.index.tolist()
    z_data = piv.to_numpy().tolist()
    return {
        "data": [{"z": z_data, "x": x_labels, "y": y_labels, "type": "heatmap", "colorscale": "Viridis", "colorbar": {"title": "Monto"}, "ygap": 1}],
        "layout": {"title": "", "margin": {"l": 160, "b": 80, "r": 50, "t": 30}, "xaxis": {"title": "", "side": "bottom", "tickangle": -45, "automargin": True}, "yaxis": {"title": "", "automargin": True}}
    }

def _build_treemap(df: pd.DataFrame, cat_col: str, sub_col: str, val_col: str) -> Dict[str, Any]:
    """Treemap ancho completo con mejor legibilidad y (Categoría) en etiqueta"""
    if cat_col not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    
    df_clean = df.copy()
    df_clean["_v"] = _to_numeric_robust(df[val_col]) if val_col in df.columns else 1
    
    # Nivel 1: Categorías (Padres)
    l1 = df_clean.groupby(cat_col)["_v"].sum().reset_index()
    l1.columns = ["label", "value"]
    l1["parent"] = ""
    l1["id"] = l1["label"] # ID único para enlazar
    l1["color_val"] = range(len(l1)) # Para asignar colores distintos

    final_df = l1
    
    # Nivel 2: Productos (Hijos)
    if sub_col and sub_col in df.columns:
        l2 = df_clean.groupby([cat_col, sub_col])["_v"].sum().reset_index()
        l2.columns = ["parent", "label_raw", "value"]
        
        # AQUÍ AGREGAMOS LA CATEGORÍA ENTRE PARÉNTESIS AL PRODUCTO
        l2["label"] = l2["label_raw"].astype(str) + " (" + l2["parent"].astype(str) + ")"
        l2["id"] = l2["parent"] + "/" + l2["label_raw"]
        l2["color_val"] = 0 # No afecta color de padres
        
        # Unimos
        final_df = pd.concat([l1, l2])
    
    return {
        "data": [{
            "type": "treemap",
            "ids": final_df.get("id", []).tolist(),
            "labels": final_df["label"].astype(str).tolist(),
            "parents": final_df["parent"].astype(str).tolist(),
            "values": final_df["value"].tolist(),
            # Usamos root > parents > leaves para colorear por rama (Categoría)
            "branchvalues": "total",
            "textinfo": "label+value", 
            "hoverinfo": "label+value+percent parent",
            # Configuración de texto para que se lea bien sobre rojo/verde/morado
            "textfont": {"family": "Arial", "size": 14, "color": "white"},
            "marker": {
                "line": {"width": 1, "color": "#222"}, # Bordes oscuros para separar
                "colorscale": "Set2" # Paleta de colores más suave y legible
            },
            "pathbar": {"visible": True}
        }],
        "layout": {
            "title": "", 
            "autosize": True,
            # Márgenes mínimos para ocupar todo el ancho
            "margin": {"t": 20, "l": 0, "r": 0, "b": 10},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)"
        }
    }
    
def _build_calendar_heatmap(df: pd.DataFrame, date_col: str, val_col: str) -> Dict[str, Any]:
    if date_col not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Falta fecha")}}
    ds = _safe_to_datetime(df[date_col])
    vals = _to_numeric_robust(df[val_col]) if val_col in df.columns else pd.Series(1, index=df.index)
    tmp = pd.DataFrame({"date": ds, "val": vals}).dropna()
    tmp["month_label"] = tmp["date"].dt.month.map(MESES_ES_FULL)
    tmp["day"] = tmp["date"].dt.day
    tmp["month_int"] = tmp["date"].dt.month 
    piv = pd.pivot_table(tmp, index="day", columns=["month_int", "month_label"], values="val", aggfunc="sum").fillna(0)
    x_labels = [c[1] for c in piv.columns] 
    z_data = piv.to_numpy().tolist()
    y_labels = [str(i) for i in piv.index]
    return {
        "data": [{"z": z_data, "x": x_labels, "y": y_labels, "type": "heatmap", "colorscale": "Spectral", "ygap": 1, "xgap": 1}],
        "layout": {
            "title": "", 
            # CORRECCIÓN: Aumentamos 't' (top) de 50 a 100 para bajar el gráfico.
            # Esto despeja el área superior para el título.
            "margin": {"t": 100, "l": 70}, 
            "xaxis": {"title": "Mes", "side": "top"}, 
            "yaxis": {"title": "Día", "autorange": "reversed"}
        }
    }

def _build_bar_top(df: pd.DataFrame, dim: str, y_field: str, aggregate: str, limit: int = 10) -> Dict[str, Any]:
    if dim not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    dim_s = _ensure_series(df[dim])
    if y_field and y_field in df.columns and y_field != "__row__":
        vals = _to_numeric_robust(df[y_field])
        ser = pd.DataFrame({dim: dim_s, "v": vals}).groupby(dim)["v"].sum() if aggregate=="sum" else pd.DataFrame({dim: dim_s, "v": vals}).groupby(dim)["v"].mean()
    else:
        ser = dim_s.value_counts()
    ser = ser.sort_values(ascending=False).head(limit)
    return {
        "data": [{"x": ser.index.astype(str).tolist(), "y": ser.tolist(), "type": "bar", "marker": {"color": "#3b82f6"}}],
        "layout": {"title": "", "xaxis": {"tickangle": -30}, "yaxis": {"title": y_field or "Valor"}}
    }

def _build_pie(df: pd.DataFrame, cat_field: str, val_field: str, limit: int=8) -> Dict[str, Any]:
    if cat_field not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    cat_s = _ensure_series(df[cat_field])
    if val_field and val_field in df.columns and val_field != "__row__":
        vals = _to_numeric_robust(df[val_field])
        ser = pd.DataFrame({cat_field: cat_s, "v": vals}).groupby(cat_field)["v"].sum()
    else:
        ser = cat_s.value_counts()
    ser = ser.sort_values(ascending=False)
    if len(ser) > limit:
        ser = pd.concat([ser.head(limit-1), pd.Series({"Otros": ser.iloc[limit-1:].sum()})])
    return {
        "data": [{"labels": ser.index.astype(str).tolist(), "values": ser.tolist(), "type": "pie", "hole": 0.4}],
        "layout": {"title": "", "margin": {"t": 20, "b": 20}}
    }

def _build_histogram(df: pd.DataFrame, field: str) -> Dict[str, Any]:
    if field not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    vals = _to_numeric_robust(df[field]).dropna()
    return {
        "data": [{"x": vals.tolist(), "type": "histogram", "marker": {"color": "#8b5cf6"}}],
        "layout": {"title": "", "xaxis": {"title": field}, "yaxis": {"title": "Frecuencia"}}
    }

""" def _build_scatter(df: pd.DataFrame, x_col: str, y_col: str) -> Dict[str, Any]:
    if x_col not in df.columns or y_col not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Faltan cols")}}
    df_clean = pd.DataFrame({"x": _to_numeric_robust(df[x_col]), "y": _to_numeric_robust(df[y_col])}).dropna()
    if len(df_clean) > 1000: df_clean = df_clean.sample(1000)
    return {
        "data": [{"x": df_clean["x"].tolist(), "y": df_clean["y"].tolist(), "mode": "markers", "type": "scatter", "marker": {"color": "#10b981", "opacity":0.6}}],
        "layout": {"title": "", "xaxis": {"title": x_col}, "yaxis": {"title": y_col}} 
    } """
    
def _build_scatter(df: pd.DataFrame, x_col: str, y_col: str) -> Dict[str, Any]:
    # Validación básica
    if x_col not in df.columns or y_col not in df.columns: 
        return {"data": [], "layout": {"title": _title_cfg("Faltan columnas")}}
    
    # 1. DETECCIÓN DE GRUPO (PRODUCTO)
    group_col = None
    if "producto" in df.columns:
        group_col = "producto"
    else:
        candidates = [c for c in df.columns if df[c].dtype == 'object' and c not in [x_col, y_col]]
        valid_cats = [c for c in candidates if df[c].nunique() < 50]
        if valid_cats: group_col = valid_cats[0]

    df_clean = df.copy()
    df_clean = df_clean.dropna(subset=[x_col, y_col])
    
    # Muestreo seguro
    if len(df_clean) > 2000: df_clean = df_clean.sample(2000)

    data = []
    
    if group_col:
        unique_items = df_clean[group_col].unique()
        n_items = len(unique_items)
        
        # Generación de colores únicos (HSL)
        colors = [f"hsl({int(i * 360 / n_items)}, 75%, 50%)" for i in range(n_items)]
        
        for i, item in enumerate(unique_items):
            mask = df_clean[group_col] == item
            sub_df = df_clean[mask]
            
            # Etiqueta: "Nombre Producto (Categoría)"
            cat_label = ""
            if "categoria" in df_clean.columns:
                val = sub_df["categoria"].iloc[0]
                cat_label = f" ({val})"
            
            legend_name = f"{str(item)}{cat_label}"

            data.append({
                "x": _to_numeric_robust(sub_df[x_col]).tolist(),
                "y": _to_numeric_robust(sub_df[y_col]).tolist(),
                "mode": "markers",
                "type": "scatter",
                "name": legend_name,
                "marker": {
                    "color": colors[i],
                    "size": 10, "opacity": 0.8, 
                    "line": {"width": 1, "color": "white"}
                },
                "text": sub_df[group_col].tolist(),
                "hovertemplate": "<b>%{text}</b>" + cat_label + "<br>" + f"{x_col}: %{{x}}<br>{y_col}: %{{y}}<extra></extra>"
            })
    else:
        # Caso simple sin agrupación
        data = [{
            "x": _to_numeric_robust(df_clean[x_col]).tolist(),
            "y": _to_numeric_robust(df_clean[y_col]).tolist(),
            "mode": "markers",
            "type": "scatter",
            "marker": {"color": "#10b981", "size": 9, "opacity": 0.6}
        }]

    return {
        "data": data,
        "layout": {
            "title": "", 
            "autosize": True, # Forzar ajuste automático al contenedor
            
            # AXIS CONFIG: 'automargin' es CLAVE para que ocupe el ancho sin romperse
            "xaxis": {
                "title": x_col, 
                "gridcolor": "#444",
                "automargin": True,
                "zeroline": False
            }, 
            "yaxis": {
                "title": y_col, 
                "gridcolor": "#444",
                "automargin": True,
                "zeroline": False
            },
            
            "legend": {
                "orientation": "h",
                "yanchor": "top",
                "y": -0.25, # Leyenda abajo con suficiente espacio
                "xanchor": "center",
                "x": 0.5,
                "itemclick": "toggleothers",
                "itemdoubleclick": "toggle"
            },
            
            # MÁRGENES AJUSTADOS:
            # 'r': 20 -> Le damos un respiro a la derecha para que la última etiqueta (180k)
            # no fuerce al gráfico a encogerse.
            # 'l': 50 -> Espacio suficiente para los números del eje Y.
            "margin": {"t": 30, "l": 50, "r": 20, "b": 100}, 
            "hovermode": "closest"
        }
    }
    
def _build_boxplot(df: pd.DataFrame, x_col: str, y_col: str) -> Dict[str, Any]:
    if x_col not in df.columns or y_col not in df.columns: return {"data": [], "layout": {"title": _title_cfg("Sin datos")}}
    top_cats = df[x_col].value_counts().head(10).index
    df_filt = df[df[x_col].isin(top_cats)]
    return {
        "data": [{
            "x": df_filt[x_col].astype(str).tolist(), 
            "y": _to_numeric_robust(df_filt[y_col]).tolist(), 
            "type": "box", 
            "marker": {"color": "#f59e0b"}
        }],
        "layout": {"title": "", "xaxis": {"title": x_col}, "yaxis": {"title": y_col}}
    }

# --------------------- MASTER MAPPER ---------------------
def _chart_to_plot(df: pd.DataFrame, chart: Dict[str, Any]) -> Dict[str, Any]:
    ctype = chart.get("type")
    enc = chart.get("encoding", {})
    t = chart.get("title", "")
    
    spec = {"data": [], "layout": {"title": _title_cfg(t)}}
    
    try:
        if ctype == "line":
            spec = _build_line_month(df, enc.get("x",{}).get("field"), enc.get("y",{}).get("field"), enc.get("y",{}).get("aggregate", "sum"))
        elif ctype == "heatmap_pivot":
            spec = _build_heatmap_pivot(df, enc.get("x",{}).get("field"), enc.get("y",{}).get("field"), enc.get("value",{}).get("field"))
        elif ctype == "calendar":
            spec = _build_calendar_heatmap(df, enc.get("date",{}).get("field"), enc.get("value",{}).get("field"))
        elif ctype == "bar":
            spec = _build_bar_top(df, enc.get("x",{}).get("field"), enc.get("y",{}).get("field"), enc.get("y",{}).get("aggregate", "count"), chart.get("limit", 10))
        elif ctype == "pie":
            spec = _build_pie(df, enc.get("category",{}).get("field"), enc.get("value",{}).get("field"))
        elif ctype == "histogram":
            spec = _build_histogram(df, enc.get("x",{}).get("field"))
        elif ctype == "treemap":
            spec = _build_treemap(df, enc.get("category",{}).get("field"), enc.get("sub",{}).get("field"), enc.get("value",{}).get("field"))
        elif ctype == "scatter":
            spec = _build_scatter(df, enc.get("x",{}).get("field"), enc.get("y",{}).get("field"))
        elif ctype == "box":
            spec = _build_boxplot(df, enc.get("x",{}).get("field"), enc.get("y",{}).get("field"))
    except Exception:
        pass 

    if "layout" not in spec: spec["layout"] = {}
    spec["layout"]["title"] = _title_cfg(t)
    return spec

# --------------------- GENERADOR HTML ---------------------
def _eval_kpi(df: pd.DataFrame, kpi: Dict[str, Any]) -> str:
    op = kpi.get("op", "")
    col = kpi.get("col")
    if op == "count_rows": return f"{len(df):,}".replace(",",".")
    if op == "nunique" and col in df.columns: return f"{df[col].nunique():,}".replace(",",".")
    if op in ["sum", "mean"] and col in df.columns:
        val = _to_numeric_robust(df[col]).agg(op)
        return f"{val:,.0f}".replace(",",".")
    return "-"

def generate_dashboard_html(df: pd.DataFrame, artifacts_dir: Path, csv_rel_name: str, auto_spec: Optional[Dict[str, Any]]=None) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / "dashboard.html"
    
    kpi_html = ""
    sections_html = ""
    plots_data = []
    
    if auto_spec:
        # KPIs
        for k in auto_spec.get("kpis", [])[:4]:
            kpi_html += f'<div class="card"><div class="kpi-title">{k["title"]}</div><div class="kpi-value">{_eval_kpi(df, k)}</div></div>'
            
        # Secciones
        charts_dict = {c["id"]: c for c in auto_spec.get("charts", [])}
        for dash in auto_spec.get("dashboards", []):
            sections_html += f'<div class="section-header"><h3>{dash["title"]}</h3><div class="line"></div></div><div class="center">'
            for cid in dash["charts"]:
                if cid in charts_dict:
                    div_id = f"plot_{cid}"
                    c_def = charts_dict[cid]
                    
                    # LOGICA DE LAYOUT: "span-2" expande a ancho completo (2 columnas)
                    # Calendar y Treemap ahora son FULL WIDTH
                    is_full_width = c_def["type"] in ["calendar", "treemap"]
                    cls = "card plot-tall span-2" if is_full_width else "card plot"
                    
                    sections_html += f'<div id="{div_id}" class="{cls}"></div>'
                    p = _chart_to_plot(df, c_def)
                    plots_data.append({"container": div_id, "data": p["data"], "layout": p["layout"]})
            sections_html += '</div>'

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Analytics Avanzado</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ margin:0; font-family: Inter, sans-serif; background:#0f172a; color:#e2e8f0; padding-bottom:40px; }}
  .container {{ max-width: 1600px; margin:0 auto; padding: 24px; display:flex; flex-direction:column; gap: 32px; }}
  
  /* KPIs Grid */
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
  
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px; overflow: hidden; }}
  .kpi-title {{ font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; font-weight: 600; }}
  .kpi-value {{ font-size:28px; font-weight:700; margin-top:4px; color: #f1f5f9; }}
  
  .section-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }}
  .section-header h3 {{ margin: 0; font-size: 18px; color: #60a5fa; whitespace: nowrap; }}
  .section-header .line {{ height: 1px; background: #334155; width: 100%; }}
  
  /* --- VISTA PANTALLA: GRILLA DE 2 COLUMNAS --- */
  .center {{ 
      display: grid; 
      grid-template-columns: 1fr 1fr; /* 2 Columnas */
      gap: 24px; 
  }}
  
  /* Clase para ocupar 2 columnas (Full Width) */
  .span-2 {{ grid-column: span 2; }}
  
  /* Móvil: 1 columna */
  @media (max-width: 768px) {{
      .center {{ grid-template-columns: 1fr; }}
      .span-2 {{ grid-column: span 1; }}
  }}

  .plot {{ height: 400px; }} .plot-tall {{ height: 550px; }}
  a {{ color:#60a5fa; }}

  /* --- VISTA IMPRESIÓN (PDF): 1 SOLA COLUMNA --- */
  @media print {{
      .no-print {{ display: none !important; }}
      body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; background-color: #0f172a !important; color: #e2e8f0 !important; }}
      .container {{ max-width: 100%; margin: 0; padding: 0; }}
      
      .center {{ 
          display: grid; 
          grid-template-columns: 1fr !important; /* Forza 1 columna */
          gap: 30px; 
      }}
      
      .card, .span-2 {{ 
          grid-column: span 1 !important; /* Forza span 1 */
          break-inside: avoid; 
          page-break-inside: avoid; 
          border: 1px solid #444; 
          width: 100%; 
          margin-bottom: 20px;
      }}
  }}
</style>
</head>
<body>
  <div class="container">
    <div class="no-print" style="margin-bottom: 10px; display: flex; justify-content: flex-end;">
        <button onclick="window.print()" style="background-color: #3b82f6; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-family: sans-serif;">
            🖨️ Guardar Dashboard PDF
        </button>
    </div>

    <div class="kpi-row">
      {kpi_html}
      <div class="card" style="display:flex; align-items:center; justify-content:center;">
        <a href="./{csv_rel_name}" target="_blank">📥 Descargar Dataset</a>
      </div>
    </div>
    {sections_html}
  </div>
  <script>
    const PLOTS = {json.dumps(plots_data, ensure_ascii=False)};
    const base = {{ paper_bgcolor: '#1e293b', plot_bgcolor: '#1e293b', font: {{ color: '#e2e8f0' }} }};
    function render() {{
      for(const p of PLOTS) {{
         const el = document.getElementById(p.container);
         if(el) Plotly.newPlot(el, p.data, Object.assign({{}}, base, p.layout), {{responsive:true}});
      }}
    }}
    if(window.Plotly) render(); else document.querySelector('script').onload = render;
  </script>
</body>
</html>"""
    
    out.write_text(html, encoding="utf-8")
    return out