# tests/test_requirements_matrix.py
from __future__ import annotations
import io
import json
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.core import config

client = TestClient(app)

GREEN = "🟢"
YELLOW = "🟡"
RED = "🔴"

# ---------- helpers ----------

def _post_process(data: bytes, filename: str, ctype="text/csv"):
    files = {"file": (filename, data, ctype)}
    # intenta /api/process y luego /process (según tu main)
    r = client.post("/api/process", files=files)
    if r.status_code >= 400:
        r = client.post("/process", files=files)
    return r

def _get_status(pid: str):
    r = client.get(f"/api/status/{pid}")
    if r.status_code >= 400:
        r = client.get(f"/status/{pid}")
    return r

def _wait_done(pid: str, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = _get_status(pid)
        if r.status_code == 200:
            js = r.json()
            st = str(js.get("status", "")).lower()
            if st in {"completed", "done", "finished", "ok"} or st == "failed":
                return js
        time.sleep(0.25)
    raise AssertionError("Timeout esperando estado 'completed/failed'")

def _get_artifact(pid: str, name: str):
    # intenta rutas pública y /api/ según tu configuración dev
    r = client.get(f"/api/artifacts/{pid}/{name}")
    if r.status_code >= 400:
        r = client.get(f"/artifacts/{pid}/{name}")
    return r

def _get_history(pid: str):
    r = client.get(f"/api/history/{pid}")
    if r.status_code >= 400:
        r = client.get(f"/history/{pid}")
    return r

def _make_csv_bytes():
    df = pd.DataFrame(
        {
            "Fecha ": ["2024-01-01", "2024-01-02", "2024-01-03"],
            " Cliente": ["Acme", "Beta", "Acme"],
            "Monto  ": [1000, 2000, 1000],
            "Moneda": ["CLP", "CLP", "CLP"],
        }
    )
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# ---------- prueba / reporte ----------

def test_requirements_matrix_report_does_not_fail_and_prints_table(capsys):
    csv = _make_csv_bytes()
    r = _post_process(csv, "matrix.csv", "text/csv")
    assert r.status_code in (200, 201), f"POST /process devolvió {r.status_code}: {r.text}"
    resp = r.json()
    pid = resp.get("id") or resp.get("process_id")
    assert pid, resp

    status = _wait_done(pid)
    arts = status.get("artifacts") or {}
    base_dir = Path(config.BASE_DIR)

    # empezamos marcando por lo que ya está probado con tus tests E2E anteriores
    rf = {}

    # Verdes comprobados E2E
    for k in [
        "RFN1", "RFN2", "RFN3",
        "RFN4", "RFN5", "RFN7",
        "RFN21", "RFN26", "RFN27",
        "RFN30", "RFN31", "RFN32",
        "RFN44", "RFN51",
        "RFN56", "RFN57", "RFN58",
        "RFN64", "RFN65", "RFN66", "RFN67", "RFN68",
        "RFN71", "RFN73",
        "RFN37",  # history accesible
    ]:
        rf[k] = GREEN

    # Lectura XLS antiguo (xlrd 1.2.0 soportado): sin test explícito -> amarillo
    rf["RFN6"] = YELLOW

    # Encabezados (hay normalización trim/minúsculas/únicos en datasources.py): marcamos verde si vemos normalización en el CSV limpio
    # Descargamos dataset_limpio.csv y checamos headers
    try:
        r_csv = _get_artifact(pid, "dataset_limpio.csv")
        if r_csv.status_code == 200:
            df_clean = pd.read_csv(io.BytesIO(r_csv.content))
            cols = [str(c) for c in df_clean.columns]
            # heurística sencilla de normalización
            cond8 = all(c == c.lower() for c in cols)
            cond9 = all("  " not in c for c in cols)  # sin espacios dobles
            cond10 = len(cols) == len(set(cols))
            rf["RFN8"]  = GREEN if cond8 else YELLOW
            rf["RFN9"]  = GREEN if cond9 else YELLOW
            rf["RFN10"] = GREEN if cond10 else YELLOW
        else:
            rf["RFN8"] = rf["RFN9"] = rf["RFN10"] = YELLOW
    except Exception:
        rf["RFN8"] = rf["RFN9"] = rf["RFN10"] = YELLOW

    # Fechas a ISO (RFN15): miramos si alguna columna de fecha se normalizó al estilo YYYY-MM-DD
    try:
        if 'fecha' in [c.lower().strip() for c in df_clean.columns]:
            s = pd.to_datetime(df_clean[[c for c in df_clean.columns if c.lower().strip() == 'fecha'][0]], errors="coerce")
            rf["RFN15"] = GREEN if s.notna().all() else YELLOW
        else:
            rf["RFN15"] = YELLOW
    except Exception:
        rf["RFN15"] = YELLOW

    # Tipos (básica) RFN20: ya inferimos tipos y los guardamos en metrics.inferred_types
    if status.get("metrics", {}).get("inferred_types"):
        rf["RFN20"] = GREEN
    else:
        rf["RFN20"] = YELLOW

    # Dashboard filtros/KPI (RFN53-55, 83-85): existe dashboard; assert suave -> amarillo si no verificamos internamente
    for k in ["RFN53", "RFN54", "RFN83", "RFN84", "RFN85"]:
        rf[k] = YELLOW

    # Bitácora y progreso por etapa (RFN35, RFN36, RFN55, RFN86): ya registramos eventos, marcamos amarillo si no auditamos todos los campos
    hist_r = _get_history(pid)
    if hist_r.status_code == 200:
        try:
            js = hist_r.json()
            items = js["items"] if isinstance(js, dict) and "items" in js else (js if isinstance(js, list) else [])
            rf["RFN35"] = GREEN if items else YELLOW
            rf["RFN36"] = YELLOW  # falta asociar usuario en todos los eventos
            rf["RFN55"] = GREEN if any(i.get("type") == "process_failed" for i in items) or items else YELLOW
            rf["RFN86"] = YELLOW  # barra/tiempos ya están, pero no auditamos UI aquí
        except Exception:
            rf["RFN35"] = rf["RFN36"] = rf["RFN55"] = rf["RFN86"] = YELLOW
    else:
        for k in ["RFN35", "RFN36", "RFN55", "RFN86"]:
            rf[k] = YELLOW

    # Reglas YAML/JSON (RFN11-14, 41-42): código base está, falta test específico -> amarillo
    for k in ["RFN11", "RFN12", "RFN13", "RFN14", "RFN41", "RFN42"]:
        rf[k] = YELLOW

    # Moneda / números / deduplicación por clave (RFN16-19): pendiente robustecer y testear -> rojo/amarillo
    rf["RFN16"] = RED     # estandarización de moneda no verificada
    rf["RFN17"] = YELLOW  # normalización básica existe, falta exhaustivo + test
    rf["RFN18"] = RED     # detección de claves de unicidad pendiente
    rf["RFN19"] = YELLOW  # drop_duplicates existe, falta por claves detectadas + logging específico

    # PDF (RFN28-29-43): HTML listo; PDF controlado por flag, sin test -> rojo
    rf["RFN28"] = rf["RFN29"] = rf["RFN43"] = RED

    # Seguridad/JWT (RFN38, RFN59, RFN81): helpers listos, endpoints con flags públicos en dev -> amarillo/rojo
    rf["RFN38"] = YELLOW  # existe validación Bearer helper, falta enforcement + test dedicado
    rf["RFN59"] = YELLOW  # endpoint protegido si ARTIFACTS_PUBLIC=0, en dev suele ser 1
    rf["RFN81"] = YELLOW  # idem, front ya usa /api/artifacts, falta modo protegido testeado

    # Logs en JSON estructurado global (RFN46): bitácora por proceso sí, logger global no -> amarillo
    rf["RFN46"] = YELLOW

    # Explicación paso a paso (RFN47): hay bitácora, falta narrativa en reporte -> amarillo
    rf["RFN47"] = YELLOW

    # Preferencias persistentes y re-ejecución (RFN48-50): sin implementar -> rojo
    rf["RFN48"] = rf["RFN49"] = rf["RFN50"] = RED

    # Saludo raíz (RFN74)
    r_root = client.get("/")
    rf["RFN74"] = GREEN if r_root.status_code == 200 else YELLOW

    # UUIDv4 (RFN75): se generan así (comprobado indirectamente) -> amarillo/verde
    rf["RFN75"] = YELLOW  # lo damos por hecho; si quieres, valida patrón UUIDv4 del pid

    # Frontend (RFN76-93): muchas son de UI/UX; las marcamos según base disponible
    front_yellow = [
        "RFN76","RFN77","RFN78","RFN79","RFN80","RFN82","RFN83","RFN84","RFN85",
        "RFN88","RFN89","RFN90","RFN91","RFN92","RFN93"
    ]
    for k in front_yellow:
        rf[k] = YELLOW

    # Docker image oficial (RFN45): pendiente -> rojo
    rf["RFN45"] = RED

    # Limpieza de temporales (RFN63): pendiente -> rojo
    rf["RFN63"] = RED

    # Exactitud de inferencia (RFN61) / Hints roles (RFN62): pendiente -> rojo/amarillo
    rf["RFN61"] = RED
    rf["RFN62"] = YELLOW

    # Tukey IQR (RFN24-25): no implementado (tenemos IsolationForest) -> rojo
    rf["RFN24"] = rf["RFN25"] = RED

    # ---- imprime reporte ----
    order = [f"RFN{i}" for i in range(1, 94)]
    rows = []
    green_count = yellow_count = red_count = 0
    for k in order:
        v = rf.get(k, YELLOW)
        rows.append((k, v))
        if v == GREEN:
            green_count += 1
        elif v == YELLOW:
            yellow_count += 1
        else:
            red_count += 1

    # salida bonita (tabla)
    print("\n=== MATRIZ DE CUMPLIMIENTO RFN ===")
    print(f"Verdes: {green_count}  | Amarillos: {yellow_count}  | Rojos: {red_count}\n")
    print(f"{'ID':<6}  Estado")
    print("-"*20)
    for k, v in rows:
        print(f"{k:<6}  {v}")
    print("\nLeyenda: 🟢 verde (OK)  🟡 parcial/pendiente de test  🔴 pendiente")

    # el test NUNCA falla: es un reporte visual
    assert True
