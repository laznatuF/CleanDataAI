# app/application/semantics.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import re, math, importlib, os
import pandas as pd
import numpy as np

# ===================== Importaciones opcionales =====================

# Fechas
try:
    import dateparser as _dateparser
except Exception:
    _dateparser = None
try:
    from dateutil import parser as _dateutil_parser  # type: ignore
except Exception:
    _dateutil_parser = None

# Embeddings
try:
    from sentence_transformers import SentenceTransformer, util as _st_util  # type: ignore
    _HAS_EMB = True
except Exception:
    _HAS_EMB = False

# TF-IDF (fallback de embeddings)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _HAS_TFIDF = True
except Exception:
    _HAS_TFIDF = False

# sdtypes (tipo semántico base opcional)
def _load_infer_sdtypes():
    try:
        m = importlib.import_module("sdtypes")
        return getattr(m, "infer_sdtypes", None)
    except Exception:
        return None
_infer_sdtypes = _load_infer_sdtypes()

# Clasificador de dominio opcional (joblib)
try:
    import joblib  # type: ignore
    _HAS_JOBLIB = True
except Exception:
    _HAS_JOBLIB = False


# ===================== Utilidades de normalización =====================

def _slug(s: str) -> str:
    s = re.sub(r"[^\w\s\-\.%/]", " ", str(s), flags=re.I)
    s = re.sub(r"\s+", "_", s.strip().lower())
    return s[:80] or "col"

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    cols, seen = [], set()
    for c in df.columns:
        base = _slug(str(c))
        name, k = base, 2
        while name in seen:
            name = f"{base}_{k}"; k += 1
        seen.add(name); cols.append(name)
    out = df.copy()
    out.columns = cols
    return out

# -------- fechas tolerantes --------
def _parse_any_date_ok(x: Any) -> bool:
    if pd.isna(x):
        return False
    s = str(x)
    if _dateparser:
        try:
            if _dateparser.parse(s) is not None:
                return True
        except Exception:
            pass
    if _dateutil_parser:
        try:
            _dateutil_parser.parse(s, dayfirst=True, fuzzy=True)
            return True
        except Exception:
            pass
    try:
        v = pd.to_datetime(s, errors="coerce", dayfirst=True)  # sin infer_datetime_format (evita warning)
        return pd.notna(v)
    except Exception:
        return False

def _is_date_series(s: pd.Series) -> bool:
    ser = s.dropna()
    if ser.empty: return False
    try:
        samp = ser.sample(min(200, len(ser)), random_state=1)
    except ValueError:
        samp = ser
    ok = sum(_parse_any_date_ok(v) for v in samp.head(200))
    return ok >= max(4, math.ceil(len(samp)*0.6))

# -------- numérico robusto (miles/decimal) --------
_NUM_CLEAN_RE = re.compile(r"[^\d\-,\.]")

def _to_float_robust(x: Any) -> Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip()
    if not s: return None
    s = _NUM_CLEAN_RE.sub("", s)
    # heurística: si hay ',' y '.', decide decimal por última aparición
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _pct_from_str(x: Any) -> Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip().lower()
    if not s: return None
    if "%" in s:
        s = s.replace("%", "")
        v = _to_float_robust(s)
        return v if v is None else v/100.0
    return None

def _series_num_ratio(s: pd.Series) -> float:
    ser = s.dropna()
    if ser.empty: return 0.0
    vals = ser.map(_to_float_robust)
    return float(pd.Series(vals).notna().mean())

# -------- booleanos / moneda / porcentaje / geo --------
def _looks_bool_values(s: pd.Series) -> bool:
    ser = s.dropna().astype(str).str.lower()
    if ser.empty: return False
    allowed = {"0","1","true","false","t","f","si","sí","no","y","n"}
    return ser.isin(allowed).mean() > 0.9

def _is_money_values(s: pd.Series) -> bool:
    ser = s.dropna().astype(str)
    if ser.empty: return False
    patt = r"[$€£]|CLP|USD|EUR|MXN|ARS|BRL|PEN|GBP|COP|UYU"
    return ser.str.contains(patt, case=False, regex=True).mean() > 0.2

def _is_percent_series(s: pd.Series) -> bool:
    ser = s.dropna().astype(str)
    if ser.empty: return False
    return ser.str.contains(r"%", regex=True).mean() > 0.5

def _geo_ratio(s: pd.Series, kind: str) -> float:
    """kind: 'lat' or 'lon'"""
    ser = s.dropna().map(_to_float_robust)
    ser = ser[pd.notna(ser)]
    if ser.empty: return 0.0
    if kind == "lat":
        ok = ser.between(-90, 90).mean()
    else:
        ok = ser.between(-180, 180).mean()
    return float(ok)

def _looks_code_series(s: pd.Series) -> bool:
    ser = s.dropna().astype(str)
    if ser.empty: return False
    # Códigos tipo alfanumérico/guiones, alta unicidad
    ratio = ser.str.match(r"^[A-Za-z0-9\-_\/\.]{4,}$").mean()
    return ratio > 0.6

# -------- embeddings / TF-IDF --------
def _emb_model():
    if not _HAS_EMB: return None
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None

def _tfidf_similarity(name: str, terms_list: List[List[str]]) -> List[float]:
    docs = [name] + [" ".join(t) for t in terms_list]
    if not _HAS_TFIDF:
        return [0.0]*len(terms_list)
    try:
        tfidf = TfidfVectorizer(analyzer="word", ngram_range=(1,2)).fit_transform(docs)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).ravel()
        return [float(x) for x in sims]
    except Exception:
        return [0.0]*len(terms_list)

ONTO: Dict[str, List[str]] = {
    "fecha": ["fecha","date","day","month","year","timestamp","periodo","period","fec","fech"],
    "métrica_monetaria": ["monto","importe","amount","revenue","ventas","price","precio",
                          "total","valor","salary","sueldo","pay","wage","unit_price","precio_unitario"],
    "métrica_numérica": ["cantidad","qty","units","score","porcentaje","percent","ratio",
                         "count","duración","duration","tiempo","time","age","edad","stock","inventory"],
    "bool": ["flag","is_","has_","true","false","sí","si","no","activo","inactivo","active","enabled"],
    "id": ["id","code","codigo","uuid","nro","numero","folio","order_id","invoice_id"],
    "categórica": ["categoría","category","tipo","clase","segmento","producto","cliente",
                   "departamento","ciudad","estado","moneda","brand","region","región","prioridad","canal"],
    "geo": ["lat","latitude","lon","longitud","long","lng","geo","coordinates"],
}

def _name_role_similarity(name: str, model) -> Dict[str, float]:
    name = (name or "").lower()
    roles = list(ONTO.keys())
    if model is not None:
        col_vec = model.encode(name, normalize_embeddings=True)
        out: Dict[str,float] = {}
        for role, terms in ONTO.items():
            term_vec = model.encode(terms, normalize_embeddings=True)
            out[role] = float(_st_util.cos_sim(col_vec, term_vec).max())
        return out
    sims = _tfidf_similarity(name, [ONTO[r] for r in roles])
    return {r: sims[i] for i, r in enumerate(roles)} if sims else {r: float(any(t in name for t in ONTO[r])) for r in roles}

# ===================== Dominio =====================

def _domain_by_rules(cols: List[str]) -> str:
    s = " ".join(cols).lower()
    if any(k in s for k in ["salary","sueldo","hire","termination","department","employee","hr"]):
        return "hr"
    if any(k in s for k in ["venta","sales","price","order","sku","cliente","invoice","region","canal"]):
        return "sales"
    if any(k in s for k in ["proveedor","purchase","ap","pago","factura","oc","compras"]):
        return "procurement"
    if any(k in s for k in ["stock","inventario","warehouse","bodega"]):
        return "inventory"
    return "generic"

def _domain_with_model(cols: List[str]) -> Tuple[str,float]:
    """
    Intenta cargar un clasificador entrenado. Busca en:
    - models/domain_clf.pkl
    - data/domain_model.joblib  (fallback)
    Si no existe o falla → reglas.
    """
    text = " ".join(cols).lower()
    # rutas relativas a este archivo
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..", "models", "domain_clf.pkl")),
        os.path.abspath(os.path.join(here, "..", "data", "domain_model.joblib")),
    ]
    if not _HAS_JOBLIB:
        return _domain_by_rules(cols), 0.5
    model = None
    for p in candidates:
        if os.path.exists(p):
            try:
                model = joblib.load(p)
                break
            except Exception:
                model = None
    if model is None:
        return _domain_by_rules(cols), 0.5
    try:
        prob = model.predict_proba([text])[0]
        label = model.classes_[int(np.argmax(prob))]
        return str(label), float(np.max(prob))
    except Exception:
        try:
            label = model.predict([text])[0]
            return str(label), 0.6
        except Exception:
            return _domain_by_rules(cols), 0.5

# ===================== Esquema / salida =====================

@dataclass
class Schema:
    roles: Dict[str, str]                # col -> role
    primary_date: Optional[str]
    primary_metric: Optional[str]
    dims: List[str]                      # 1..3
    units: Dict[str, str]                # {"currency": "CLP"} etc.
    domain: str
    confidence: Dict[str, float]         # col -> 0..1
    derived: Dict[str, str]              # ej: {"importe_total": "cantidad * precio_unitario"}

# ===================== Inferencia principal =====================

def infer_semantics(df_raw: pd.DataFrame) -> Schema:
    df = normalize_headers(df_raw)
    model = _emb_model()

    # sdtypes (si existe) como pista
    types: Dict[str, Any] = {}
    if _infer_sdtypes:
        try:
            types = _infer_sdtypes(df, as_series=False)  # type: ignore
        except Exception:
            types = {}

    roles: Dict[str,str] = {}
    confs: Dict[str,float] = {}
    derived: Dict[str,str] = {}

    # colecciones por rol
    money_cols: List[str] = []
    date_cols:  List[str] = []
    num_cols:   List[str] = []
    cat_cols:   List[str] = []
    bool_cols:  List[str] = []
    id_cols:    List[str] = []
    geo_lat, geo_lon = None, None

    n = len(df)

    # ---------------- Scoring por columna ----------------
    for col in df.columns:
        name = col.lower()
        sims = _name_role_similarity(name, model)
        ser = df[col]
        nunique = ser.astype(str).nunique(dropna=True)
        base_type = str(types.get(col, "unknown"))

        # señales por valores
        date_score  = 1.0 if _is_date_series(ser) else 0.0
        money_score = 1.0 if _is_money_values(ser) else 0.0
        bool_score  = 1.0 if _looks_bool_values(ser) else 0.0
        num_ratio   = _series_num_ratio(ser)
        pct_score   = 1.0 if _is_percent_series(ser) else 0.0
        lat_ratio   = _geo_ratio(ser, "lat")
        lon_ratio   = _geo_ratio(ser, "lon")
        code_like   = _looks_code_series(ser)

        # pesos (ajustables)
        w_name, w_val, w_cons = 0.45, 0.45, 0.10

        # candidatos
        s_fecha = w_name*sims.get("fecha",0) + w_val*date_score
        s_mon   = w_name*sims.get("métrica_monetaria",0) + w_val*money_score + w_cons*min(1.0, num_ratio+0.25*pct_score)
        s_num   = w_name*sims.get("métrica_numérica",0) + w_val*num_ratio
        s_bool  = w_name*sims.get("bool",0) + w_val*bool_score
        s_id    = (0.25 if "id" in name else 0.0) + (0.6 if (nunique >= n*0.98) else 0.0) + (0.2 if code_like else 0.0)
        s_lat   = w_name*(1.0 if "lat" in name else 0.0) + w_val*lat_ratio
        s_lon   = w_name*(1.0 if ("lon" in name or "lng" in name or "long" in name) else 0.0) + w_val*lon_ratio
        s_cat   = sims.get("categórica", 0.0) * w_name

        scores = {
            "fecha": s_fecha,
            "métrica_monetaria": s_mon,
            "métrica_numérica": s_num,
            "bool": s_bool,
            "id": s_id,
            "geo_lat": s_lat,
            "geo_lon": s_lon,
            "categórica": s_cat
        }
        best_role, best_score = max(scores.items(), key=lambda kv: kv[1])

        # normalización de decisión
        if best_role == "geo_lat":
            roles[col] = "geo_lat"; confs[col] = float(best_score); geo_lat = col; continue
        if best_role == "geo_lon":
            roles[col] = "geo_lon"; confs[col] = float(best_score); geo_lon = col; continue

        if best_role == "id" and nunique < n*0.8:
            # no tan único → re-evalúa
            best_role = "métrica_numérica" if s_num > s_cat else "categórica"

        # si sdtypes dice float/int, sube un poco confianza numérica
        if ("float" in base_type or "int" in base_type) and best_role == "métrica_numérica":
            best_score = min(1.0, best_score + 0.1)

        roles[col] = best_role
        confs[col] = float(min(1.0, max(0.1, best_score)))

        # colecciones
        if roles[col] == "fecha": date_cols.append(col)
        elif roles[col] == "métrica_monetaria": money_cols.append(col)
        elif roles[col] == "métrica_numérica": num_cols.append(col)
        elif roles[col] == "bool": bool_cols.append(col)
        elif roles[col] == "id": id_cols.append(col)
        elif roles[col] in ("geo_lat","geo_lon"): pass
        else: cat_cols.append(col)

    # si hay lat & lon marcadas, mantenlas explícitas
    if geo_lat and geo_lon:
        roles[geo_lat] = "geo_lat"
        roles[geo_lon] = "geo_lon"
    elif geo_lat or geo_lon:
        # solo una de las dos → tratar como métrica_numérica/categórica según evidencia
        g = geo_lat or geo_lon
        if roles.get(g) in ("geo_lat","geo_lon"):
            # degradar a numérica si parece número
            if _series_num_ratio(df[g]) > 0.7:
                roles[g] = "métrica_numérica"
            else:
                roles[g] = "categórica"

    # ============ primary_date ============
    primary_date = max(date_cols, key=lambda c: df[c].notna().mean()) if date_cols else None

    # ============ métrica derivada (cantidad x precio) ============
    qty_like = [c for c in df.columns if c in num_cols and re.search(r"(qty|cantidad|units|cantidad_total)", c, re.I)]
    unitp_like = [c for c in df.columns if (c in money_cols or c in num_cols) and re.search(r"(unit_price|precio_unitario|precio)", c, re.I)]
    primary_metric: Optional[str] = None

    if qty_like and unitp_like:
        q, p = qty_like[0], unitp_like[0]
        derived_name = "importe_total"
        if derived_name not in df.columns:
            derived[derived_name] = f"{q} * {p}"
        primary_metric = money_cols[0] if money_cols else derived_name

    # si no hay derivada elegible: prioriza monetaria; si no, numérica estable
    if not primary_metric:
        if money_cols:
            primary_metric = max(money_cols, key=lambda c: df[c].notna().mean())
        elif num_cols:
            num_ok = [c for c in num_cols if df[c].nunique(dropna=True) < n*0.9 and df[c].astype(str).nunique() > 5]
            primary_metric = (num_ok or num_cols)[0]

    # ============ dims (evita ids/bools; cardinalidad 2..50; pocos nulos) ============
    dims: List[str] = []
    for c in cat_cols:
        s = df[c]
        u = s.astype(str).nunique(dropna=True)
        if 2 <= u <= min(50, max(2, int(0.25*n))) and s.isna().mean() < 0.4 and not _looks_code_series(s):
            dims.append(c)
    # fallback si no hay categóricas útiles
    if not dims:
        if bool_cols: dims = [bool_cols[0]]
        elif cat_cols: dims = [cat_cols[0]]
        elif id_cols: dims = [id_cols[0]]

    # ============ unidades (moneda) ============
    units: Dict[str,str] = {}
    if "moneda" in df.columns:
        u = df["moneda"].dropna().astype(str).str.upper().unique().tolist()
        if len(u) == 1:
            units["currency"] = u[0]
    elif money_cols:
        # heurística por símbolos
        sample = " ".join(df[money_cols[0]].dropna().astype(str).head(200).tolist())
        if re.search(r"\bUSD\b|\$", sample): units["currency"] = "USD"
        elif re.search(r"€|\bEUR\b", sample): units["currency"] = "EUR"
        elif re.search(r"£|\bGBP\b", sample): units["currency"] = "GBP"
        elif re.search(r"\bCLP\b|\$", sample): units["currency"] = "CLP"

    # ============ dominio ============
    domain, _ = _domain_with_model(list(df.columns))

    # salida
    return Schema(
        roles=roles,
        primary_date=primary_date,
        primary_metric=primary_metric,
        dims=dims[:3],
        units=units,
        domain=domain,
        confidence=confs,
        derived=derived
    )

# ===================== Perfil compacto =====================

def _safe_nanmin(x: pd.Series) -> Optional[float]:
    try:
        arr = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
        if np.isnan(arr).all():
            return None
        return float(np.nanmin(arr))
    except Exception:
        return None

def _safe_nanmax(x: pd.Series) -> Optional[float]:
    try:
        arr = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
        if np.isnan(arr).all():
            return None
        return float(np.nanmax(arr))
    except Exception:
        return None

def simple_profile(df: pd.DataFrame) -> Dict[str, Any]:
    cols: Dict[str, Any] = {}
    for c in df.columns:
        s = df[c]
        is_num = pd.api.types.is_numeric_dtype(s) or _series_num_ratio(s) > 0.8
        cols[c] = {
            "dtype": str(s.dtype),
            "rows": int(len(s)),
            "non_null": int(s.notna().sum()),
            "null_pct": float((s.isna().mean() * 100.0)),
            "nunique": int(s.astype(str).nunique(dropna=True)),
            "sample": [str(v) for v in s.dropna().astype(str).head(5).tolist()],
            "min": _safe_nanmin(s) if is_num else None,
            "max": _safe_nanmax(s) if is_num else None,
        }
    return {"rows": int(len(df)), "columns": cols}
