# tests/test_artifacts_history.py
from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from fastapi.testclient import TestClient

# Asegura que el repo esté en el path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.core.config import RUNS_DIR  # noqa: E402

client = TestClient(app)

API = "/api"
DONE = {"completed", "done", "finished", "success", "ok"}
WAIT_TIMEOUT = 45.0  # subir un poco por si odf/openpyxl tardan

def post(path: str, **kw):
    return client.post(f"{API}{path}", **kw)

def get(path: str, **kw):
    return client.get(f"{API}{path}", **kw)

# Dataset mínimo
DF = pd.DataFrame(
    {
        "fecha": ["2024-01-01", "2024-01-02"],
        "cliente": ["Acme", "Beta"],
        "monto": [1000, 2000],
        "moneda": ["CLP", "CLP"],
    }
)

def _make_csv() -> Tuple[bytes, str, str]:
    data = DF.to_csv(index=False).encode("utf-8")
    return data, "mini.csv", "text/csv"

def _process_upload(data: bytes, filename: str, ctype: str) -> Dict:
    files = {"file": (filename, data, ctype)}
    r = post("/process", files=files)
    assert r.status_code == 201, f"/process debería devolver 201: {r.status_code} {r.text}"
    return r.json()

def _wait_done(pid: str, timeout_s: float = WAIT_TIMEOUT) -> Dict:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        r = get(f"/status/{pid}")
        assert r.status_code in (200, 201), r.text
        js = r.json()
        last = js
        st = str(js.get("status", "")).lower()
        if st in DONE:
            return js
        time.sleep(0.15)
    raise AssertionError(f"Timeout esperando completion. Último status: {last}")

def test_artefactos_y_historia_e2e():
    # 1) upload
    data, name, ctype = _make_csv()
    res = _process_upload(data, name, ctype)
    pid = res.get("id") or res.get("process_id")
    assert pid, res

    # 2) esperar a done
    js = _wait_done(pid)

    # 3) validar artefactos esperados
    arts = js.get("artifacts") or {}
    for key in (
        "reporte_perfilado.html",
        "dataset_limpio.csv",
        "dashboard.html",
        "reporte_integrado.html",
    ):
        assert key in arts, f"Falta artefacto: {key}"
        # el path relativo debe existir en disco
        rel = arts[key]
        p = (ROOT / rel).resolve()
        assert p.exists(), f"No existe en disco: {p}"

    # 4) descargar artefactos por endpoint protegido
    def _fetch_art(name: str):
        r = get(f"/artifacts/{pid}/{name}")
        assert r.status_code == 200, f"GET /artifacts fallo {name}: {r.status_code} {r.text}"
        return r

    r_html = _fetch_art("reporte_perfilado.html")
    assert "text/html" in (r_html.headers.get("content-type") or "")

    r_csv = _fetch_art("dataset_limpio.csv")
    assert "text/csv" in (r_csv.headers.get("content-type") or "") or \
           "application/octet-stream" in (r_csv.headers.get("content-type") or "")

    r_dash = _fetch_art("dashboard.html")
    assert "text/html" in (r_dash.headers.get("content-type") or "")

    r_rep = _fetch_art("reporte_integrado.html")
    assert "text/html" in (r_rep.headers.get("content-type") or "")

    # 5) bitácora
    h = get(f"/history/{pid}")
    assert h.status_code == 200, h.text
    hist = h.json()
    assert isinstance(hist.get("items"), list) and hist["items"], "Bitácora vacía"
    # al menos eventos de start y completed/failed
    types = {it.get("type") for it in hist["items"]}
    assert {"process_started", "process_completed"} & types, types
