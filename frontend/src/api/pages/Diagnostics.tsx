import React, { useCallback, useMemo, useRef, useState } from "react";

type TestStatus = "idle" | "running" | "ok" | "fail";
type Test = {
  id: string;
  nombre: string;
  rfns: string[];             // RFN que cubre
  run: () => Promise<void>;
  status: TestStatus;
  detalle?: string;
};

const json = async (res: Response) => {
  const txt = await res.text();
  try { return JSON.parse(txt); } catch { return { raw: txt }; }
};

// Utilidad: espera
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

// CSV pequeño de prueba
const SAMPLE_CSV = `fecha,monto,categoria
2024-01-02,123.45,Food
02/01/2024,67,Transport
`;

export default function DiagnosticsPage() {
  const [tests, setTests] = useState<Test[]>([]);
  const processIdRef = useRef<string>("");

  const setOne = useCallback((id: string, patch: Partial<Test>) => {
    setTests(prev => prev.map(t => t.id === id ? { ...t, ...patch } : t));
  }, []);

  const buildTests = useCallback((): Test[] => {
    const t: Test[] = [];

    // RFN74 (saludo raíz) opcional, si tienes GET /
    t.push({
      id: "root-ping",
      nombre: "Ping backend raíz",
      rfns: ["RFN74"],
      status: "idle",
      run: async () => {
        setOne("root-ping", { status: "running", detalle: "" });
        const res = await fetch("/api/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await json(res);
        setOne("root-ping", { status: "ok", detalle: JSON.stringify(data).slice(0, 200) });
      }
    });

    // RFN1–3: POST /process → id
    t.push({
      id: "process-post",
      nombre: "POST /process con CSV (crea proceso y devuelve id)",
      rfns: ["RFN1", "RFN2", "RFN3"],
      status: "idle",
      run: async () => {
        setOne("process-post", { status: "running", detalle: "" });

        const fd = new FormData();
        const file = new File([SAMPLE_CSV], "qa.csv", { type: "text/csv" });
        fd.append("file", file);

        const res = await fetch("/api/process", { method: "POST", body: fd });
        if (!res.ok) throw new Error(`HTTP ${res.status} ${await res.text()}`);
        const data = await json(res);
        const pid = data?.id || data?.process_id;
        if (!pid) throw new Error(`Sin id en respuesta: ${JSON.stringify(data)}`);
        processIdRef.current = String(pid);
        setOne("process-post", { status: "ok", detalle: `id=${pid}` });
      }
    });

    // RFN31–32–58: poll /status/{id}
    t.push({
      id: "status-poll",
      nombre: "Polling /status/{id} hasta done/ok",
      rfns: ["RFN31", "RFN32", "RFN58"],
      status: "idle",
      run: async () => {
        setOne("status-poll", { status: "running", detalle: "" });
        const pid = processIdRef.current;
        if (!pid) throw new Error("No hay process_id (ejecuta primero POST /process)");

        const deadline = Date.now() + 20000; // 20s
        let last = "";
        while (Date.now() < deadline) {
          const res = await fetch(`/api/status/${encodeURIComponent(pid)}`);
          if (!res.ok) throw new Error(`HTTP ${res.status} ${await res.text()}`);
          const js = await json(res);
          const st = String(js?.status ?? "").toLowerCase();
          last = JSON.stringify(js).slice(0, 200);
          if (["completed", "done", "ok", "success", "finished"].includes(st)) {
            setOne("status-poll", { status: "ok", detalle: last });
            return;
          }
          if (st === "failed") {
            throw new Error(`Proceso en failed: ${last}`);
          }
          await sleep(500);
        }
        throw new Error("Timeout esperando completion");
      }
    });

    // RFN21–73: artefacto perfilado (si el backend expone /runs o similar)
    t.push({
      id: "artifact-profile",
      nombre: "Cargar reporte_perfilado.html",
      rfns: ["RFN21", "RFN73"],
      status: "idle",
      run: async () => {
        setOne("artifact-profile", { status: "running", detalle: "" });
        const pid = processIdRef.current;
        if (!pid) throw new Error("No hay process_id (ejecuta primero POST /process)");

        const resS = await fetch(`/api/status/${encodeURIComponent(pid)}`);
        if (!resS.ok) throw new Error(`HTTP ${resS.status} ${await resS.text()}`);
        const js = await json(resS);
        const path = js?.artifacts?.["reporte_perfilado.html"];
        if (!path) throw new Error("No se encontró artifacts.reporte_perfilado.html en /status");

        // Intentar GET directo (si el backend sirve /runs). Si lo tienes protegido con JWT, ajusta a tu endpoint seguro.
        const res = await fetch(`/${path.replace(/^\/?/, "")}`, { method: "GET" });
        if (!res.ok) throw new Error(`No se pudo cargar el HTML del perfilado: HTTP ${res.status}`);
        const text = await res.text();
        if (!text || text.length < 50) throw new Error("HTML vacío o muy corto");
        setOne("artifact-profile", { status: "ok", detalle: `OK: ${path}` });
      }
    });

    // RFN88–89–90 (parcial): comprobaciones suaves de FE
    t.push({
      id: "frontend-es-localstorage",
      nombre: "UI ES + responsive (básico) + localStorage",
      rfns: ["RFN88", "RFN89", "RFN90"],
      status: "idle",
      run: async () => {
        setOne("frontend-es-localstorage", { status: "running", detalle: "" });
        // Español (heurística: textos comunes)
        const hasEs = document.body.innerText.includes("Procesar")
                   || document.body.innerText.includes("Subir archivo")
                   || document.body.innerText.includes("Ejecución");
        if (!hasEs) throw new Error("No detecté textos en ES en la vista actual");

        // Responsive: comprobación mínima (existe botón/hamburguesa con aria-label)
        const anyHamb = document.querySelector('button[aria-label*="Abrir"]')
                      || document.querySelector('button[aria-label*="Menú"]')
                      || document.querySelector('button[aria-label*="Navegación"]');
        if (!anyHamb) throw new Error("No vi botón de menú/hamburguesa (ver Header)");

        // localStorage: guardamos último id
        const pid = processIdRef.current || "dummy-id";
        localStorage.setItem("last_process_id", pid);
        const back = localStorage.getItem("last_process_id");
        if (back !== pid) throw new Error("No pude persistir process_id en localStorage");

        setOne("frontend-es-localstorage", { status: "ok", detalle: `last_process_id=${back}` });
      }
    });

    return t;
  }, [setOne]);

  const all = useMemo(() => tests, [tests]);
  const passed = all.filter(t => t.status === "ok").length;
  const failed = all.filter(t => t.status === "fail").length;

  const runAll = useCallback(async () => {
    const initial = buildTests();
    setTests(initial);
    for (const test of initial) {
      try {
        await test.run();
      } catch (e: any) {
        setOne(test.id, { status: "fail", detalle: String(e?.message || e) });
      }
    }
  }, [buildTests, setOne]);

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Diagnóstico RFN (desde Frontend)</h1>
      <p className="text-sm text-gray-600">
        Estas pruebas validan flujos end-to-end: subida, estado, artefactos y UI básica.
      </p>

      <button
        onClick={runAll}
        className="px-4 py-2 rounded-md bg-black text-white hover:bg-gray-900"
      >
        Ejecutar pruebas
      </button>

      <div className="text-sm text-gray-700">
        Resultado: <span className="font-medium text-green-700">{passed} OK</span>{" "}
        / <span className="font-medium text-red-700">{failed} FALLÓ</span>
      </div>

      <ul className="space-y-3">
        {all.map(t => (
          <li key={t.id} className="border rounded-lg p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">{t.nombre}</div>
                <div className="text-xs text-gray-500">Cubre: {t.rfns.join(", ")}</div>
              </div>
              <span
                className={
                  "text-xs px-2 py-1 rounded " +
                  (t.status === "ok"
                    ? "bg-green-100 text-green-700"
                    : t.status === "fail"
                    ? "bg-red-100 text-red-700"
                    : t.status === "running"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-600")
                }
              >
                {t.status.toUpperCase()}
              </span>
            </div>
            {t.detalle && (
              <pre className="text-xs mt-2 bg-gray-50 p-2 rounded overflow-x-auto">
                {t.detalle}
              </pre>
            )}
          </li>
        ))}
      </ul>

      <div className="text-xs text-gray-500">
        Nota: si tienes protegidos los artefactos (RFN59), ajusta este test para usar tu endpoint seguro.
      </div>
    </div>
  );
}
