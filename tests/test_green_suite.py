# tests/test_green_suite.py
"""
Verifica RFN en VERDE (núcleo):
- RFN1, RFN2, RFN3: /api/process crea tarea y devuelve id
- RFN4, RFN5, RFN7: lectura CSV/XLSX/ODS (aquí usamos CSV para el e2e)
- RFN26, RFN27: dashboard.html generado
- RFN30: reporte_integrado.html generado
- RFN31, RFN32, RFN58, RFN71, RFN73: /status/{id} con progreso y artefactos en runs/{id}/artifacts
- RFN44: dataset_limpio.csv exportado
- RFN64, RFN65, RFN66, RFN67, RFN68: IsolationForest, columnas de outlier y métricas
- RFN74: endpoint raíz de saludo
- RFN81 (modo local público): descarga artefactos por /artifacts/{id}/{name}
"""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from fastapi.testclient import TestClient

# --- Bootstrapping de imports del proyecto ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.core.config import RUNS_DIR  # noqa: E402

client = TestClient(app)

API = "/api"
DONE = {"completed", "done", "finished", "success", "ok"}
WAIT_TIMEOUT = 35.0  # margen extra por generación de HTMLs


def post(path: str, **kw):
    return client.post(f"{API}{path}", **kw)


def get(path: str, **kw):
    return client.get(f"{API}{path}", **kw)


# ---------- Dataset base (incluye numérica para outliers) ----------
DF = pd.DataFrame(
    {
        "fecha": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "cliente": ["Acme", "Beta", "Beta", "Acme"],
        # valores con un poco de variación para que IsolationForest tenga algo que mirar
        "monto": [1000, 2000, 2100, 120000],  # 120000 es un outlier plausible
        "moneda": ["CLP", "CLP", "CLP", "CLP"],
    }
)
EXPECTED_ROWS = len(DF)
EXPECTED_COLS = DF.shape[1]


def _make_csv() -> Tuple[bytes, str, str]:
    data = DF.to_csv(index=False).encode("utf-8")
    return data, "verde.csv", "text/csv"


def _process_upload(data: bytes, filename: str, ctype: str) -> Dict:
    files = {"file": (filename, data, ctype)}
    r = post("/process", files=files)
    assert r.status_code in (200, 201), f"/process debe 200/201: {r.status_code} {r.text}"
    js = r.json()
    assert js.get("id") or js.get("process_id"), js
    assert str(js.get("status", "")).lower() in {"queued", "pending", "ok"}, js
    return js


def _read_status_file(pid: str) -> Dict | None:
    path = RUNS_DIR / pid / "status.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _resolve_artifact_path(root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    return p if p.is_absolute() else (root / p).resolve()


def _wait_done(pid: str, timeout_s: float = WAIT_TIMEOUT) -> Dict:
    t0 = time.time()
    last_js = None
    while time.time() - t0 < timeout_s:
        s = get(f"/status/{pid}")
        assert s.status_code == 200, f"/status fallo: {s.status_code} {s.text}"
        js = s.json()
        last_js = js
        st = str(js.get("status", "")).lower().strip()
        if st in DONE:
            return js

        # fallback por archivo en disco
        js_disk = _read_status_file(pid)
        if js_disk and str(js_disk.get("status", "")).lower().strip() in DONE:
            return js_disk

        time.sleep(0.1)

    raise AssertionError(
        "Timeout esperando completion.\n"
        f"Último /status: {json.dumps(last_js, indent=2, ensure_ascii=False)}\n"
        f"Status.json en disco: {json.dumps(_read_status_file(pid) or {}, indent=2, ensure_ascii=False)}"
    )


# ========================= PRUEBAS =========================

def test_root_and_health():
    # RFN74 (saludo/estado)
    r = client.get("/")
    assert r.status_code == 200
    js = r.json()
    assert js.get("name") == "CleanDataAI API"
    assert js.get("status") == "ok"
    assert "Bienvenido" in (js.get("message") or "")

    # alias /api/health
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json().get("ok") is True


def test_e2e_green_core_and_artifacts_and_outliers(tmp_path: Path = None):
    # 1) subir
    data, name, ctype = _make_csv()
    res = _process_upload(data, name, ctype)
    pid = res.get("id") or res.get("process_id")
    assert pid

    # 2) esperar done
    js = _wait_done(pid)
    assert str(js.get("status", "")).lower() in DONE

    # 3) métricas básicas (RFN31, RFN32, RFN58, RFN71)
    metrics = js.get("metrics") or {}
    assert int(metrics.get("rows", -1)) == EXPECTED_ROWS
    assert int(metrics.get("cols", -1)) == EXPECTED_COLS

    # 4) artefactos esperados (RFN44, RFN26/27, RFN30)
    arts = js.get("artifacts") or {}
    for key in ("dataset_limpio.csv", "dashboard.html", "reporte_integrado.html", "reporte_perfilado.html"):
        assert key in arts, f"Falta artefacto {key}"
        p = _resolve_artifact_path(ROOT, arts[key])
        assert p.exists(), f"No existe en disco: {p}"

    # 5) outliers: columnas y métricas (RFN64–68)
    # descargar dataset_limpio por endpoint público (RFN81 con ARTIFACTS_PUBLIC=1)
    r_csv = client.get(f"/artifacts/{pid}/dataset_limpio.csv")
    assert r_csv.status_code == 200, r_csv.text
    df_clean = pd.read_csv(io.BytesIO(r_csv.content))

    # columnas de outlier (RFN66)
    assert "is_outlier" in df_clean.columns
    assert "outlier_score" in df_clean.columns
    assert "outlier_method" in df_clean.columns
    assert (df_clean["outlier_method"] == "isolation_forest").all()

    # métricas en status (RFN65, RFN68)
    assert "outliers_used_columns" in metrics
    assert isinstance(metrics.get("outliers_used_columns"), list)
    assert "outliers_contamination" in metrics
    cont = float(metrics.get("outliers_contamination"))
    assert 0.0 < cont <= 0.5

    # 6) endpoints de artefactos (RFN26/27/30 + RFN81 local)
    for name in ("dashboard.html", "reporte_integrado.html", "reporte_perfilado.html"):
        r = client.get(f"/artifacts/{pid}/{name}")
        assert r.status_code == 200, f"GET /artifacts fallo {name}: {r.status_code} {r.text}"
        assert "text/html" in (r.headers.get("content-type") or "")

    # 7) history público (RFN37 en modo local)
    h = client.get(f"/history/{pid}")
    assert h.status_code == 200, h.text
    # respuesta puede ser JSON o JSONL; aceptamos ambos.
    try:
        _ = h.json()
    except Exception:
        assert isinstance(h.content, (bytes, bytearray)) and len(h.content) > 0
