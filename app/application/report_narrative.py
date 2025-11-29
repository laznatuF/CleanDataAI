# app/application/report_narrative.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json
import pandas as pd

from app.application.storytelling import generate_chart_story, generate_executive_conclusion
from app.application.dashboard import _chart_to_plot 

def build_narrative_report(
    df: pd.DataFrame, 
    auto_spec: Dict[str, Any], 
    artifacts_dir: Path
) -> Path:
    out_path = artifacts_dir / "reporte_narrativo.html"
    
    # 1. Generar la Conclusión (pero la guardamos para el final)
    conclusion = generate_executive_conclusion(df, auto_spec)
    
    # 2. Generar Items (Gráfico + Texto)
    all_charts_ids = []
    for d in auto_spec.get("dashboards", []):
        all_charts_ids.extend(d.get("charts", []))
        
    chart_defs = {c["id"]: c for c in auto_spec.get("charts", [])}
    report_items = []
    
    for cid in all_charts_ids:
        if cid not in chart_defs: continue
        c_def = chart_defs[cid]
        
        # Generar historia detallada
        story = generate_chart_story(df, c_def, full_spec=auto_spec)
        
        try:
            plot_obj = _chart_to_plot(df, c_def)
        except Exception:
            plot_obj = None
        
        report_items.append({
            "id": cid,
            "title": c_def.get("title", "Análisis"),
            "story": story,
            "plot_data": plot_obj,
            "type": c_def.get("type", "bar")
        })

    # 3. Construir HTML (Conclusión al FINAL)
    # Nota: El bloque <div class="executive-summary"> ahora está después del loop
    html_content = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<title>Reporte Narrativo</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #334155; margin: 0; padding: 40px; line-height: 1.6; }}
  .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px; }}
  
  h1 {{ color: #0f172a; text-align: center; margin-bottom: 10px; }}
  .subtitle {{ text-align: center; color: #64748b; margin-bottom: 40px; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }}

  /* Estilos para la Conclusión Final */
  .executive-summary {{ 
      background: #eff6ff; 
      border-left: 5px solid #3b82f6; 
      padding: 20px; 
      margin-top: 60px; /* Separación de los gráficos */
      border-radius: 4px; 
  }}
  .executive-summary h2 {{ margin-top: 0; color: #1e40af; font-size: 1.4rem; }}

  .report-item {{ margin-bottom: 60px; page-break-inside: avoid; }}
  .chart-title {{ font-size: 1.4rem; font-weight: 600; color: #1e293b; margin-bottom: 10px; border-left: 4px solid #F28C18; padding-left: 10px; }}
  
  .content-grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
  @media(min-width: 768px) {{ .content-grid {{ grid-template-columns: 3fr 2fr; align-items: start; }} }}
  
  .text-panel {{ padding: 20px; background: #fdfbf7; border: 1px solid #e4dccb; border-radius: 8px; font-size: 0.95rem; text-align: justify; }}
  .chart-panel {{ height: 350px; border: 1px solid #e2e8f0; border-radius: 4px; }}
  
  .footer {{ text-align: center; font-size: 0.8rem; color: #94a3b8; margin-top: 50px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
</style>
</head>
<body>
  <div class="container">
    <h1>Reporte Narrativo de Datos</h1>
    <p class="subtitle">Análisis detallado generado por Inteligencia Artificial</p>
    
    <!-- GRÁFICOS DETALLADOS -->
    {''.join([f'''
    <div class="report-item">
        <div class="chart-title">{item['title']}</div>
        <div class="content-grid">
            <div id="plot_{item['id']}" class="chart-panel"></div>
            <div class="text-panel">
                {item['story']}
            </div>
        </div>
    </div>
    ''' for item in report_items])}
    
    <!-- CONCLUSIÓN AL FINAL -->
    {f'<div class="executive-summary"><h2>🔎 Conclusión Ejecutiva y Recomendaciones</h2>{conclusion}</div>' if conclusion else ''}
    
    <div class="footer">
        Generado con Llama 3.3 AI el {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
    </div>
  </div>

  <script>
    const ITEMS = {json.dumps(report_items, ensure_ascii=False)};
    const layoutBase = {{ 
        margin: {{ t: 30, l: 40, r: 20, b: 40 }}, 
        font: {{ size: 10 }},
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)'
    }};
    
    for(const item of ITEMS) {{
        const el = document.getElementById('plot_' + item.id);
        if(el && item.plot_data) {{
            const layout = Object.assign({{}}, layoutBase, item.plot_data.layout || {{}});
            Plotly.newPlot(el, item.plot_data.data, layout, {{responsive: true, displayModeBar: false}});
        }}
    }}
  </script>
</body>
</html>"""

    out_path.write_text(html_content, encoding="utf-8")
    return out_path