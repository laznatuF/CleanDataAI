# app/application/spec_guard.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
import math
import pandas as pd

@dataclass
class ChartIssue:
    code: str
    message: str
    severity: str  # "error" | "warn" | "info"

@dataclass
class ChartHealth:
    chart_id: str
    score: float           # 0..100
    issues: List[ChartIssue]

def _col_ok(df: pd.DataFrame, col: Optional[str], min_non_null=0.6) -> Tuple[bool,float]:
    if not col or col not in df.columns: return (False, 0.0)
    ratio = 1.0 - float(df[col].isna().mean())
    return (ratio >= min_non_null, ratio)

def _looks_id(df: pd.DataFrame, col: str) -> bool:
    if col not in df: return False
    n = len(df)
    u = df[col].astype(str).nunique(dropna=True)
    return (n > 0) and (u >= 0.98 * n)

def _is_boolish(df: pd.DataFrame, col: str) -> bool:
    s = df[col].dropna().astype(str).str.lower()
    if s.empty: return False
    return s.isin({"0","1","true","false","t","f","si","sí","no","y","n"}).mean() > 0.9

def _cardinality(df: pd.DataFrame, col: str) -> int:
    return int(df[col].astype(str).nunique(dropna=True)) if col in df else 0

def _is_all_zero_or_const(df: pd.DataFrame, col: str) -> bool:
    if col not in df: return True
    s = pd.to_numeric(df[col], errors="coerce")
    return s.notna().any() and (s.max() - s.min() == 0)

def _total_match(lhs: float, rhs: float, tol=0.02) -> bool:
    if not math.isfinite(lhs) or not math.isfinite(rhs) or rhs == 0: return False
    return abs(lhs - rhs) / abs(rhs) <= tol

def _safe_sum(s: pd.Series) -> float:
    return float(pd.to_numeric(s, errors="coerce").sum())

def validate_chart(df: pd.DataFrame, chart: Dict[str, Any], spec_roles: Dict[str,str]) -> ChartHealth:
    ctype = chart.get("type","")
    enc   = chart.get("encoding",{})
    cid   = str(chart.get("id","?"))
    issues: List[ChartIssue] = []
    score = 100.0

    # columnas
    x = enc.get("x",{}).get("field")
    y = (enc.get("y",{}) or {}).get("field") or enc.get("value",{}).get("field")
    cat = (enc.get("category",{}) or {}).get("field")
    dim = x or cat

    # 1) cobertura
    for col in filter(None, [x, y, cat]):
        ok, cov = _col_ok(df, col)
        if not ok:
            issues.append(ChartIssue("low_coverage", f"Cobertura baja en '{col}' ({cov:.0%}).", "warn"))
            score -= 10

    # 2) cardinalidad y roles
    if dim:
        card = _cardinality(df, dim)
        if card > 50:
            issues.append(ChartIssue("too_many_categories", f"'{dim}' con {card} categorías; recortar Top-N.", "warn"))
            score -= 10
        if _looks_id(df, dim):
            issues.append(ChartIssue("id_dim", f"'{dim}' parece ID; evitar como dimensión.", "error"))
            score -= 20
        if _is_boolish(df, dim):
            issues.append(ChartIssue("bool_dim", f"'{dim}' es booleana; usar solo si no hay mejores dims.", "warn"))
            score -= 5

    # 3) coherencia por tipo
    if ctype == "line":
        # debe ser fecha en X
        if spec_roles.get(x,"") != "fecha":
            issues.append(ChartIssue("line_without_date", f"Línea con X='{x}' que no es fecha.", "error"))
            score -= 25
    if ctype in ("bar","pie","histogram"):
        # Y no constante
        if y and _is_all_zero_or_const(df, y):
            issues.append(ChartIssue("constant_metric", f"Métrica '{y}' es constante.", "error"))
            score -= 25

    # 4) consistencia aritmética (bar)
    if ctype == "bar" and dim and y:
        # suma por categoría vs total
        group = (
            pd.DataFrame({dim: df[dim], y: pd.to_numeric(df[y], errors="coerce")})
            .dropna(subset=[dim])
        )
        cat_sum = float(group.groupby(dim, dropna=False)[y].sum().sum())
        total   = _safe_sum(df[y])
        if total != 0 and not _total_match(cat_sum, total):
            issues.append(ChartIssue("sum_mismatch", "La suma por categoría no cuadra con el total.", "warn"))
            score -= 10

    # 5) límites
    score = max(0.0, min(100.0, score))
    return ChartHealth(chart_id=cid, score=score, issues=issues)

@dataclass
class DashboardHealth:
    score: float
    charts: List[ChartHealth]
    blocking: bool
    messages: List[str]

def validate_dashboard(df: pd.DataFrame, auto_spec: Dict[str,Any], roles: Dict[str,str]) -> DashboardHealth:
    all_health: List[ChartHealth] = []
    dash = (auto_spec.get("dashboards") or [{}])[0]
    ids  = dash.get("charts", [])[:4]
    charts = {c["id"]: c for c in auto_spec.get("charts", [])}
    for cid in ids:
        if cid in charts:
            all_health.append(validate_chart(df, charts[cid], roles))

    # score global = promedio penalizado
    if all_health:
        s = sum(ch.score for ch in all_health) / len(all_health)
    else:
        s = 0.0
    blocking = any(any(i.severity=="error" for i in ch.issues) for ch in all_health) or s < 60
    msgs = []
    if blocking:
        msgs.append("Dashboard con problemas. Se sugiere usar layout seguro.")
    return DashboardHealth(score=s, charts=all_health, blocking=blocking, messages=msgs)
