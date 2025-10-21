# tests/test_perfilado.py
"""
Tests end-to-end del perfilado:

- Sube archivos en CSV, XLSX y ODS (in-memory)
- Verifica /api/process -> id, /api/status/{id} -> completed
- Comprueba metrics (rows/cols) y que exista artifacts['reporte_perfilado.html']
- Abre el HTML en disco y valida que contenga las cabeceras
- Casos de error: tamaño excedido y extensión no soportada
- Status inexistente devuelve 404/400

Requisitos:
    pytest, fastapi, pandas, openpyxl, odfpy
Ejecución:
    pytest -q
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

# --------------------------------------------------------------------
# Asegura que la raíz del repo esté en PYTHONPATH (por si conftest no corrió)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))
# --------------------------------------------------------------------

from app.main import app  # noqa: E402
from app.core.config import RUNS_DIR  # noqa: E402

client = TestClient(app)

# ===== CONFIG =====
# Si tu backend NO usa prefijo, pon API = "" (cadena vacía)
API = "/api"
DONE = {"completed", "done", "finished", "success", "ok"}  # estados finales aceptados
WAIT_TIMEOUT = 30.0  # segundos (generoso para Windows/xlsx/ods)


def post(path: str, **kw):
    return client.post(f"{API}{path}", **kw)


def get(path: str, **kw):
    return client.get(f"{API}{path}", **kw)


# ---------- Dataset base para todos los formatos ----------
DF = pd.DataFrame(
    {
        "fecha": ["2024-01-01", "2024-01-02"],
        "cliente": ["Acme", "Beta"],
        "monto": [1000, 2000],
        "moneda": ["CLP", "CLP"],
    }
)
EXPECTED_ROWS = 2
EXPECTED_COLS = 4
HEADERS = ["fecha", "cliente", "monto", "moneda"]


def _make_csv() -> Tuple[bytes, str, str]:
    data = DF.to_csv(index=False).encode("utf-8")
    return data, "mini.csv", "text/csv"


def _make_xlsx() -> Tuple[bytes, str, str]:
    bio = io.BytesIO()
    DF.to_excel(bio, index=False, engine="openpyxl")
    return bio.getvalue(), "mini.xlsx", (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _make_ods() -> Tuple[bytes, str, str]:
    """
    Genera un ODS válido para el engine 'odf' de pandas:
    - Encabezados como string
    - fecha -> date (office:date-value)
    - cliente/moneda -> string
    - monto -> float
    """
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P

    doc = OpenDocumentSpreadsheet()
    table = Table(name="Hoja1")

    # Fila de encabezados (string)
    tr = TableRow()
    for h in ["fecha", "cliente", "monto", "moneda"]:
        cell = TableCell(valuetype="string")
        cell.addElement(P(text=h))
        tr.addElement(cell)
    table.addElement(tr)

    # Filas de datos con tipos explícitos
    rows = [
        ("2024-01-01", "Acme", 1000.0, "CLP"),
        ("2024-01-02", "Beta", 2000.0, "CLP"),
    ]
    for fecha, cliente, monto, moneda in rows:
        tr = TableRow()

        # fecha -> date
        c_fecha = TableCell(valuetype="date", datevalue=fecha)
        c_fecha.addElement(P(text=fecha))
        tr.addElement(c_fecha)

        # cliente -> string
        c_cliente = TableCell(valuetype="string")
        c_cliente.addElement(P(text=cliente))
        tr.addElement(c_cliente)

        # monto -> float
        c_monto = TableCell(valuetype="float", value=str(float(monto)))
        c_monto.addElement(P(text=str(int(monto))))  # texto visible
        tr.addElement(c_monto)

        # moneda -> string
        c_moneda = TableCell(valuetype="string")
        c_moneda.addElement(P(text=moneda))
        tr.addElement(c_moneda)

        table.addElement(tr)

    doc.spreadsheet.addElement(table)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue(), "mini.ods", "application/vnd.oasis.opendocument.spreadsheet"


# ---------- Helpers de flujo ----------
def _process_upload(data: bytes, filename: str, ctype: str) -> Dict:
    files = {"file": (filename, data, ctype)}
    r = post("/process", files=files)
    # Acepta 200 o 201 (según semántica elegida en el endpoint)
    assert r.status_code in (200, 201), f"/process falló: {r.status_code}, {r.text}"
    return r.json()


def _read_status_file(pid: str) -> Dict | None:
    path = RUNS_DIR / pid / "status.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _resolve_artifact_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    # Interpretamos como relativo a la raíz del proyecto
    return (ROOT / p).resolve()


def _wait_status_done(pid: str, timeout_s: float = WAIT_TIMEOUT) -> Dict:
    """
    Poll a /status/{id} hasta que termine.
    Acepta varios alias de 'done' y, si el endpoint se retrasa,
    cae al estado del archivo runs/{id}/status.json.
    """
    t0 = time.time()
    last_js = None
    while time.time() - t0 < timeout_s:
        s = get(f"/status/{pid}")
        assert s.status_code in (200, 201), f"/status falló: {s.status_code}, {s.text}"
        js = s.json()
        last_js = js
        st = str(js.get("status", "")).lower().strip()

        # ¿ya está done por API?
        if st in DONE:
            return js

        # ¿ya existe el artifact? (indicio fuerte de 'done')
        art = (js.get("artifacts") or {}).get("reporte_perfilado.html")
        if art:
            html = _resolve_artifact_path(art)
            if html.exists():
                return js

        # ¿el archivo en disco ya está done?
        js_disk = _read_status_file(pid)
        if js_disk:
            st2 = str(js_disk.get("status", "")).lower().strip()
            if st2 in DONE:
                return js_disk

        time.sleep(0.05)

    raise AssertionError(
        "Tiempo de espera excedido esperando completion.\n"
        f"Última respuesta de /status: {json.dumps(last_js, indent=2, ensure_ascii=False)}\n"
        f"Status.json en disco: {json.dumps(_read_status_file(pid) or {}, indent=2, ensure_ascii=False)}"
    )


def _check_profile_ok(status_json: Dict) -> None:
    # metrics
    metrics = status_json.get("metrics") or {}
    assert int(metrics.get("rows", -1)) == EXPECTED_ROWS, metrics
    assert int(metrics.get("cols", -1)) == EXPECTED_COLS, metrics

    # artefacto
    artifacts = status_json.get("artifacts") or {}
    rel = artifacts.get("reporte_perfilado.html")
    assert rel, f"reporte_perfilado.html no presente en artifacts: {artifacts}"

    html_path = _resolve_artifact_path(rel)
    assert html_path.exists(), f"No existe el HTML en disco: {html_path}"

    text = html_path.read_text(encoding="utf-8", errors="ignore")
    # Presencia de título/cabeceras
    assert ("Reporte de Perfilado" in text) or ("Reporte de perfilado" in text)
    for h in HEADERS:
        assert h in text, f"'{h}' no encontrado en el HTML"


# ---------- Tests positivos por formato ----------
def test_perfilado_csv():
    data, name, ctype = _make_csv()
    res = _process_upload(data, name, ctype)
    pid = res.get("id") or res.get("process_id")
    assert pid, res
    js = _wait_status_done(pid)
    _check_profile_ok(js)


def test_perfilado_xlsx():
    data, name, ctype = _make_xlsx()
    res = _process_upload(data, name, ctype)
    pid = res.get("id") or res.get("process_id")
    assert pid, res
    js = _wait_status_done(pid)
    _check_profile_ok(js)


def test_perfilado_ods():
    data, name, ctype = _make_ods()
    res = _process_upload(data, name, ctype)
    pid = res.get("id") or res.get("process_id")
    assert pid, res
    js = _wait_status_done(pid)
    _check_profile_ok(js)


# ---------- Negativos: tamaño y extensión ----------
def test_error_tamano_excedido():
    # ~21 MB para gatillar 413/400
    big = io.BytesIO(b"0" * (21 * 1024 * 1024))
    files = {"file": ("grande.csv", big.getvalue(), "text/csv")}
    r = post("/process", files=files)
    assert r.status_code in (400, 413), r.text


def test_error_extension_no_soportada():
    files = {"file": ("nota.txt", b"hola", "text/plain")}
    r = post("/process", files=files)
    assert r.status_code in (400, 415), r.text


# ---------- Adicional: status inexistente ----------
def test_status_inexistente():
    s = get("/status/00000000-0000-0000-0000-000000000000")
    assert s.status_code in (404, 400), f"esperado 404/400, got {s.status_code}"
