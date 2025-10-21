from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ------------------------
# Helpers para métricas
# ------------------------

def _fmt_pct(x: float, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{(x / total) * 100:.2f}%"

def _examples(s: pd.Series, k: int = 5) -> List[str]:
    vals = (
        s.dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    return [str(v)[:80] for v in vals[:k]]

def _tukey_outliers_count(num: pd.Series) -> int:
    s = pd.to_numeric(num, errors="coerce").dropna()
    if s.empty:
        return 0
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((s < lo) | (s > hi)).sum())

def _num_details(s: pd.Series) -> str:
    sn = pd.to_numeric(s, errors="coerce").dropna()
    if sn.empty:
        return "—"
    p5 = sn.quantile(0.05)
    p95 = sn.quantile(0.95)
    parts = [
        f"min={sn.min():g}",
        f"p5={p5:g}",
        f"media={sn.mean():g}",
        f"p95={p95:g}",
        f"max={sn.max():g}",
        f"std={sn.std():g}",
        f"outliers_Tukey={_tukey_outliers_count(s)}",
    ]
    return ", ".join(parts)

def _date_details(s: pd.Series) -> str:
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True, utc=False)
    ok = int(dt.notna().sum())
    if ok == 0:
        return "parseadas=0%"
    mn = dt.min()
    mx = dt.max()
    return f"parseadas={_fmt_pct(ok, len(s))}, min={mn.date() if pd.notna(mn) else '—'}, max={mx.date() if pd.notna(mx) else '—'}"

def _text_details(s: pd.Series) -> str:
    ss = s.dropna().astype(str).str.strip()
    if ss.empty:
        return "—"
    vc = ss.value_counts(dropna=True)
    top = ", ".join([f"{k}({v})" for k, v in vc.head(3).items()])
    ln = ss.str.len()
    return f"top3={top} · len(min/med/max)={ln.min()}/{int(ln.median())}/{ln.max()}"

def _bool_details(s: pd.Series) -> str:
    ss = s.dropna().astype(str).str.lower().str.strip()
    m = {
        "sí": True, "si": True, "true": True, "1": True, "t": True, "y": True,
        "no": False, "false": False, "0": False, "f": False, "n": False
    }
    mapped = ss.map(lambda x: m.get(x, pd.NA))
    vc = mapped.value_counts(dropna=True)
    if vc.empty:
        return "—"
    parts = [f"{'true' if k else 'false'}({v})" for k, v in vc.items()]
    return " · ".join(parts)

def _moneda_details(s: pd.Series) -> str:
    ss = s.dropna().astype(str).str.strip()
    if ss.empty:
        return "—"
    vc = ss.value_counts()
    return "top3=" + ", ".join([f"{k}({v})" for k, v in vc.head(3).items()])

# ------------------------
# Heurística de rol
# ------------------------

def infer_role(col: str, s: pd.Series) -> str:
    name = col.lower().strip()

    # Pistas por nombre
    if any(k in name for k in ["fecha", "date", "fcha"]):
        return "fecha"
    if any(k in name for k in ["monto", "importe", "amount", "total"]):
        return "monto"
    if any(k in name for k in ["moneda", "currency"]):
        return "moneda"
    if any(k in name for k in ["id_", "id-","id "]) or name.startswith("id"):
        return "id"
    if any(k in name for k in ["bool", "flag", "activo", "enable", "enabled"]):
        return "bool"
    if any(k in name for k in ["cat", "tipo", "segmento", "grupo", "clase"]):
        return "categoría"

    # Pistas por contenido
    ss = s.dropna().astype(str).str.strip()
    parsed = pd.to_datetime(ss, errors="coerce", dayfirst=True, utc=False)
    if parsed.notna().mean() >= 0.7:
        return "fecha"

    numeric = pd.to_numeric(
        ss.str.replace(r"[.\s]", "", regex=True).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    if numeric.notna().mean() >= 0.8:
        return "numérico"

    if ss.str.lower().isin({"0","1","true","false","sí","si","no"}).mean() >= 0.9:
        return "bool"

    return "texto"

def details_by_role(role: str, s: pd.Series) -> str:
    role = (role or "").lower()
    if role in {"monto", "numérico"}:
        return _num_details(s)
    if role == "fecha":
        return _date_details(s)
    if role == "bool":
        return _bool_details(s)
    if role == "moneda":
        return _moneda_details(s)
    return _text_details(s)

def alerts_for(role: str, col: str, s: pd.Series, n_rows: int) -> List[str]:
    alerts: List[str] = []
    nulls = int(s.isna().sum())
    if n_rows > 0 and nulls == n_rows:
        alerts.append("100% nulos")

    if role == "id":
        dup = int((s.duplicated(keep=False)).sum())
        if dup > 0:
            alerts.append(f"duplicados={dup}")

    if role == "fecha":
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True, utc=False)
        ok = int(dt.notna().sum())
        if ok / max(1, n_rows) < 0.7:
            alerts.append("baja_lectura_fechas")

    if role in {"monto", "numérico"}:
        cnt = _tukey_outliers_count(s)
        if cnt > 0:
            alerts.append(f"outliers_Tukey={cnt}")

    return alerts

# ------------------------
# Motor de plantilla
# ------------------------

def generate_profile_html(
    df: pd.DataFrame,
    artifacts_dir: Path,
    templates_dir: Path,
    roles: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Genera artifacts/reporte_perfilado.html usando templates/profile.html.
    Columnas:
      Columna | Tipo (inferido) | Rol | Únicos (n/%) | Nulos (n/%) | Detalles | Ejemplos | Alertas
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    n_rows = int(df.shape[0])
    rows: List[Dict[str, Any]] = []

    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        role = (roles or {}).get(col) or infer_role(col, s)

        uniques = int(s.nunique(dropna=True))
        nulls = int(s.isna().sum())
        uniques_pct = _fmt_pct(uniques, n_rows)
        nulls_pct = _fmt_pct(nulls, n_rows)

        det = details_by_role(role, s)
        ex = _examples(s, k=5)
        al = alerts_for(role, col, s, n_rows)

        rows.append(
            {
                "col": col,
                "dtype": dtype,
                "role": role,
                "uniques": uniques,
                "uniques_pct": uniques_pct,
                "nulls": nulls,
                "nulls_pct": nulls_pct,
                "details": det,
                "examples": ex,
                "alerts": al,
            }
        )

    # Render con Jinja2
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Fallback amistoso si falta el template (para que el pipeline no falle)
    template_name = "profile.html"
    try:
        tpl = env.get_template(template_name)
        html = tpl.render(
            n_rows=n_rows,
            n_cols=int(df.shape[1]),
            rows=rows,
            title="Reporte de Perfilado",
        )
    except Exception:
        # Plantilla mínima de emergencia
        table_rows = "\n".join(
            f"<tr><td>{r['col']}</td><td>{r['dtype']}</td><td>{r['role']}</td>"
            f"<td>{r['uniques']} ({r['uniques_pct']})</td>"
            f"<td>{r['nulls']} ({r['nulls_pct']})</td>"
            f"<td>{r['details']}</td>"
            f"<td>{', '.join(r['examples'])}</td>"
            f"<td>{', '.join(r['alerts'])}</td></tr>"
            for r in rows
        )
        html = f"""
        <html>
          <head><meta charset="utf-8"><title>Reporte de Perfilado</title></head>
          <body>
            <h1>Reporte de Perfilado</h1>
            <p><em>Plantilla '{template_name}' no encontrada. Usando fallback.</em></p>
            <p>Filas: {n_rows} · Columnas: {int(df.shape[1])}</p>
            <table border="1" cellspacing="0" cellpadding="4">
              <thead>
                <tr>
                  <th>Columna</th><th>Tipo</th><th>Rol</th>
                  <th>Únicos</th><th>Nulos</th><th>Detalles</th><th>Ejemplos</th><th>Alertas</th>
                </tr>
              </thead>
              <tbody>
                {table_rows}
              </tbody>
            </table>
          </body>
        </html>
        """

    out = artifacts_dir / "reporte_perfilado.html"
    out.write_text(html, encoding="utf-8")
    return out
