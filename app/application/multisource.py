# app/application/multisource.py
from __future__ import annotations

from typing import List, Tuple, Dict, Optional, Any
import re

import numpy as np
import pandas as pd

# ============================
#  sklearn (TF-IDF) opcional
# ============================
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    _HAS_SK = True
except Exception:  # pragma: no cover - entorno sin sklearn
    TfidfVectorizer = None  # type: ignore
    cosine_similarity = None  # type: ignore
    _HAS_SK = False

# ====================================
#  Sentence-Transformers opcional
# ====================================
try:
    from sentence_transformers import SentenceTransformer  # type: ignore

    _HAS_ST = True
except Exception:  # pragma: no cover - entorno sin ST
    SentenceTransformer = None  # type: ignore
    _HAS_ST = False

# =================================================
#  Mapa de campos canónicos (ventas / bodega)
# =================================================
_CANONICAL_FIELDS: Dict[str, List[str]] = {
    # Fechas
    "fecha": [
        "fecha",
        "fecha_venta",
        "fecha_pedido",
        "fecha_creacion",
        "order_date",
        "date",
        "created_at",
        "fecha_transaccion",
        "fecha_movimiento",
    ],
    # Identificadores
    "id_transaccion": [
        "id_transaccion",
        "id_venta",
        "id_pedido",
        "order_id",
        "transaction_id",
        "folio",
        "n_venta",
    ],
    "sku": [
        "sku",
        "codigo_producto",
        "id_producto",
        "product_id",
        "codigo",
        "sku_producto",
    ],
    # Entidades
    "cliente": [
        "cliente",
        "nombre_cliente",
        "customer",
        "buyer",
        "comprador",
        "razon_social",
    ],
    "producto": [
        "producto",
        "nombre_producto",
        "producto_nombre",
        "item",
        "descripcion_producto",
        "product_name",
    ],
    "categoria": [
        "categoria",
        "segmento",
        "category",
        "familia",
        "rubro",
        "linea",
    ],
    # Métricas / dinero
    "moneda": [
        "moneda",
        "currency",
        "divisa",
        "tipo_moneda",
    ],
    "monto": [
        "monto",
        "total",
        "importe",
        "valor_total",
        "order_total",
        "subtotal",
        "precio_total",
        "neto",
        "bruto",
        "valor_venta",
    ],
    "precio_unitario": [
        "precio_unitario",
        "precio",
        "unit_price",
        "precio_lista",
        "valor_unitario",
    ],
    "cantidad": [
        "cantidad",
        "qty",
        "quantity",
        "unidades",
        "cant",
        "cantidad_vendida",
        "stock_salida",
    ],
    # Logística / stock
    "bodega": [
        "bodega",
        "almacen",
        "almacén",
        "warehouse",
        "deposito",
    ],
    "stock": [
        "stock",
        "inventario",
        "existencias",
        "qty_stock",
        "cantidad_disponible",
    ],
    # Métodos de pago / canal
    "metodo_pago": [
        "metodo_pago",
        "medio_pago",
        "forma_pago",
        "payment_method",
        "metodo_de_pago",
    ],
    "canal": [
        "canal",
        "origen",
        "source",
        "marketplace",
        "plataforma",
        "platform",
        "tienda",
        "channel",
    ],
    "proveedor": [
        "proveedor",
        "supplier",
        "vendor",
        "vendedor",
    ],
}

# ==========================================
#  Utilidades de normalización de texto
# ==========================================


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _slug_header(raw: str) -> str:
    """
    Similar a la normalización de app.infrastructure.datasources,
    pero local para evitar dependencias circulares.
    """
    s = str(raw or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or ""


# ==================================================
#  Índice TF-IDF sobre los nombres canónicos
# ==================================================

_CANONICAL_NAMES: List[str] = []
_CANONICAL_TEXTS: List[str] = []

for canon, syns in _CANONICAL_FIELDS.items():
    # El propio nombre canónico también se usa como sinónimo
    for phrase in syns + [canon]:
        _CANONICAL_NAMES.append(canon)
        _CANONICAL_TEXTS.append(_normalize_text(phrase))

if _HAS_SK:
    _VECTORIZER = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 4),
    )
    _CANONICAL_MATRIX = _VECTORIZER.fit_transform(_CANONICAL_TEXTS)
else:
    _VECTORIZER = None  # type: ignore[assignment]
    _CANONICAL_MATRIX = None  # type: ignore[assignment]

# ==================================================
#  Sentence-Transformers (carga perezosa)
# ==================================================

_st_model: Any = None
_st_canonical_emb: Optional[np.ndarray] = None
_CANONICAL_SENTENCES: List[str] = [t for t in _CANONICAL_TEXTS]


def _get_st_model() -> Any:
    """
    Carga el modelo ST la primera vez que se usa.
    Se devuelve `None` si no está disponible o falla.
    """
    global _st_model, _st_canonical_emb

    if not _HAS_ST:
        return None

    if _st_model is None:
        try:
            # Modelo liviano multilingüe (incluye español).
            _st_model = SentenceTransformer(  # type: ignore[call-arg]
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            _st_canonical_emb = _st_model.encode(
                _CANONICAL_SENTENCES,
                normalize_embeddings=True,
            )
        except Exception:
            _st_model = None
            _st_canonical_emb = None
    return _st_model


# ==================================================
#  Matching semántico de nombres de columnas
# ==================================================


def _tfidf_best_match(text: str) -> Tuple[Optional[str], float]:
    if not (_HAS_SK and _VECTORIZER is not None and _CANONICAL_MATRIX is not None):
        return None, 0.0
    text = _normalize_text(text)
    if not text:
        return None, 0.0

    v = _VECTORIZER.transform([text])
    sims = cosine_similarity(v, _CANONICAL_MATRIX)[0]  # type: ignore[arg-type]
    idx = int(np.argmax(sims))
    return _CANONICAL_NAMES[idx], float(sims[idx])


def _st_best_match(text: str) -> Tuple[Optional[str], float]:
    text = _normalize_text(text)
    if not text:
        return None, 0.0

    model = _get_st_model()
    if model is None or _st_canonical_emb is None:
        return None, 0.0

    emb = model.encode([text], normalize_embeddings=True)
    # vectores normalizados → producto punto = coseno
    sims = (emb @ _st_canonical_emb.T)[0]
    idx = int(np.argmax(sims))
    return _CANONICAL_NAMES[idx], float(sims[idx])


def _best_canonical(text: str) -> Tuple[Optional[str], float]:
    """
    Combina TF-IDF y ST y devuelve el mejor campo canónico + score.
    """
    cand1, s1 = _tfidf_best_match(text)
    cand2, s2 = _st_best_match(text)

    if s2 > s1:
        return cand2, s2
    return cand1, s1


def _guess_unified_name(col_name: str, series: pd.Series) -> str:
    """
    Devuelve el nombre de columna unificado:
      - Si ya es un nombre canónico, lo respeta.
      - Si encuentra match semántico, usa el canónico (fecha, monto, etc.)
      - Si no, usa slug del nombre original.
    """
    slug = _slug_header(col_name)

    if slug in _CANONICAL_FIELDS:
        return slug

    best, score = _best_canonical(slug)

    # Pequeñas heurísticas según tipo de datos
    try:
        if pd.api.types.is_datetime64_any_dtype(series):
            # Si la serie es datetime y el match no es muy bueno, preferir "fecha"
            if best is None or (best != "fecha" and score < 0.65):
                return "fecha"
        elif pd.api.types.is_numeric_dtype(series):
            # Métricas numéricas: monto / cantidad si el texto lo sugiere vagamente
            if best == "monto" and score >= 0.35:
                return "monto"
            if best == "cantidad" and score >= 0.35:
                return "cantidad"
    except Exception:
        # Cualquier problema con dtypes → ignorar heurística
        pass

    if best is not None and score >= 0.45:
        return best

    # Fallback: simplemente el slug normalizado
    return slug


def _infer_channel_from_filename(name: str) -> str:
    """
    Intenta deducir el canal a partir del nombre de archivo.
    Ejemplos:
      - "instagram_shop_ventas.csv" → "InstagramShop"
      - "ventas_mercadolibre_2025.xlsx" → "MercadoLibre"
    """
    s = (name or "").lower()
    if "instagram" in s or "ig_" in s:
        return "InstagramShop"
    if "mercado" in s or "meli" in s or "mercadolibre" in s or "ml_" in s:
        return "MercadoLibre"
    if "bodega" in s or "stock" in s or "inventario" in s or "warehouse" in s:
        return "Bodega"
    if "proveedor" in s or "supplier" in s or "vendor" in s:
        return "Proveedor"
    return "Desconocido"


# ==================================================
#  API principal: unify_sources
# ==================================================


def unify_sources(named_dfs: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """
    Unifica varias hojas/archivos en un solo DataFrame.

    - Mapea nombres de columnas a campos canónicos (fecha, sku, monto, etc.)
      usando TF-IDF + Sentence-Transformers cuando está disponible.
    - Asegura que dentro de CADA archivo los nombres resultantes sean únicos:
      si dos columnas caen en el mismo canónico, la primera se queda con él
      y las siguientes se renombran como "<nombre>_2", "<nombre>_3", ...
    - Añade metadatos: origen_archivo + origen_canal.
    """
    if not named_dfs:
        raise ValueError("No se recibieron datos para unificar.")

    per_source_maps: List[Dict[str, str]] = []
    all_cols: set[str] = set()

    # 1) Definir mapeos columna -> nombre unificado por archivo
    for file_name, df in named_dfs:
        col_map: Dict[str, str] = {}
        dest_counts: Dict[str, int] = {}

        for col in df.columns:
            unified = _guess_unified_name(str(col), df[col])

            # Asegurar unicidad dentro de este archivo
            n = dest_counts.get(unified, 0) + 1
            dest_counts[unified] = n
            final_name = unified if n == 1 else f"{unified}_{n}"

            col_map[str(col)] = final_name
            all_cols.add(final_name)

        per_source_maps.append(col_map)

    # 2) Orden de columnas: primero las canónicas más importantes
    canonical_priority = [
        "fecha",
        "id_transaccion",
        "cliente",
        "proveedor",
        "producto",
        "categoria",
        "sku",
        "moneda",
        "precio_unitario",
        "cantidad",
        "monto",
        "metodo_pago",
        "canal",
        "bodega",
        "stock",
    ]
    canonical_first = [c for c in canonical_priority if c in all_cols]
    others = sorted(all_cols - set(canonical_first))
    final_order = canonical_first + others

    unified_frames: List[pd.DataFrame] = []

    # 3) Aplicar mapeos, rellenar columnas y añadir metadatos
    for (file_name, df), col_map in zip(named_dfs, per_source_maps):
        tmp = df.copy()

        # Renombrar según col_map
        tmp.columns = [col_map.get(str(c), str(c)) for c in df.columns]

        # Añadir columnas faltantes
        for col in final_order:
            if col not in tmp.columns:
                tmp[col] = pd.NA

        # Ordenar columnas
        tmp = tmp[final_order]

        # Metadatos
        tmp["origen_archivo"] = file_name
        canal = _infer_channel_from_filename(file_name)
        tmp["origen_canal"] = canal

        unified_frames.append(tmp)

    # 4) Concatenar todo
    result = pd.concat(unified_frames, ignore_index=True)
    return result
