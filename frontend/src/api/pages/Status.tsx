// src/pages/Status.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import Header from "../../components/Header";
import Stepper, { type StepItem } from "../../components/Steeper";
import { getStatus, artifactUrl, getHistory } from "../../libs/api";

const STAGES = ["Subir archivo", "Perfilado", "Limpieza", "Dashboard", "Reporte"] as const;
const PROCESS_FINISHED = new Set(["ok", "done", "finished", "completed", "success"]);
const PROCESS_QUEUED   = new Set(["queued", "pending"]);
const STEP_FINISHED    = new Set(["ok", "done", "finished", "success"]);
const STEP_RUNNING     = new Set(["running", "in_progress"]);

type ApiStep = { name: string; status?: string | null };
type StatusResponse = {
  status?: string | null;
  steps?: ApiStep[];
  progress?: number | null;
  updated_at?: string | null;
  current_step?: string | null;
  error?: string | null;
  artifacts?: Record<string, string>;
  metrics?: Record<string, any>;
};

export default function StatusPage() {
  const params = useParams();
  const runId = ((params.runId as string) ?? (params.id as string) ?? "").trim();

  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProfile, setShowProfile] = useState(false);
  const [showDash, setShowDash] = useState(true);

  // history
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // ===== Poll de estado =====
  useEffect(() => {
    if (!runId) return;
    let timer: number | undefined;
    let canceled = false;

    const tick = async () => {
      try {
        const json = await getStatus(runId);
        if (canceled) return;
        setData(json);
        setLoading(false);

        const s = String(json?.status ?? "");
        if (!PROCESS_FINISHED.has(s) && s !== "failed") {
          timer = window.setTimeout(tick, 1500);
        }
      } catch (err) {
        if (canceled) return;
        setData((d) => d ?? { status: "failed", error: (err as Error).message });
        setLoading(false);
      }
    };

    tick();
    return () => {
      canceled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  // ===== Poll de bitácora (mientras no finaliza) =====
  useEffect(() => {
    if (!runId) return;
    let timer: number | undefined;
    let canceled = false;

    const tick = async () => {
      try {
        const res = await getHistory(runId, 200);
        if (!canceled) setHistory(res.items || []);
      } catch { /* ignore */ }

      const s = String(data?.status ?? "");
      if (!PROCESS_FINISHED.has(s) && s !== "failed") {
        timer = window.setTimeout(tick, 1500);
      }
    };

    // arrancar una vez tengamos algo de estado
    if (data) tick();

    return () => {
      canceled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId, data?.status]); // refresca si cambia el estado global

  const currentIdx = useMemo(() => {
    if (!data) return -1;
    if (data.current_step) {
      const i = STAGES.indexOf(data.current_step as any);
      if (i >= 0) return i;
    }
    const list = data.steps ?? [];
    for (let i = 0; i < STAGES.length; i++) {
      const s = list.find((x) => x.name === STAGES[i]);
      if (!s || !STEP_FINISHED.has(String(s.status ?? ""))) return i;
    }
    return -1;
  }, [data]);

  const steps: StepItem[] = useMemo(() => {
    if (!data) return STAGES.map((label) => ({ label, state: "pending" as const }));

    const proc = String(data?.status ?? "");
    if (PROCESS_FINISHED.has(proc)) return STAGES.map((label) => ({ label, state: "ok" as const }));
    if (proc === "failed")         return STAGES.map((label) => ({ label, state: "failed" as const }));
    if (PROCESS_QUEUED.has(proc))  return STAGES.map((label) => ({ label, state: "pending" as const }));

    return STAGES.map<StepItem>((label, idx) => {
      let state: StepItem["state"] = "pending";
      const backend = (data.steps ?? []).find((s) => s.name === label);
      if (backend) {
        const b = String(backend.status ?? "").toLowerCase();
        if (STEP_FINISHED.has(b)) state = "ok";
        else if (STEP_RUNNING.has(b)) state = "running";
        else if (b === "failed") state = "failed";
      }
      if (state === "pending" && currentIdx > -1) {
        if (idx < currentIdx) state = "ok";
        else if (idx === currentIdx) state = "running";
      }
      return { label, state };
    });
  }, [data, currentIdx]);

  const progress   = Math.max(0, Math.min(100, Number(data?.progress ?? 0)));
  const lastUpdate = data?.updated_at ? new Date(data.updated_at).toLocaleString("es-ES") : "—";
  const failed     = String(data?.status ?? "") === "failed";
  const queued     = PROCESS_QUEUED.has(String(data?.status ?? ""));

  const perfilRel = data?.artifacts?.["reporte_perfilado.html"];
  const dashRel   = data?.artifacts?.["dashboard.html"];
  const csvRel    = data?.artifacts?.["dataset_limpio.csv"];
  const repRel    = data?.artifacts?.["reporte_integrado.html"];

  const perfilHref = perfilRel ? artifactUrl(perfilRel) : null;
  const dashHref   = dashRel   ? artifactUrl(dashRel)   : null;
  const csvHref    = csvRel    ? artifactUrl(csvRel)    : null;
  const repHref    = repRel    ? artifactUrl(repRel)    : null;

  useEffect(() => {
    setShowProfile(!!perfilHref);
  }, [perfilHref]);

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-[1400px] px-6 md:px-8 py-8 md:py-10">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 md:p-10">
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-xl md:text-2xl font-semibold">Ejecución</h1>
          </div>

          {/* Avisos */}
          <div className="mt-3 space-y-2">
            {queued && (
              <div className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                El proceso está en cola… empezará en breve.
              </div>
            )}
            {!runId && (
              <div className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                Falta el <code>runId</code> en la ruta. Vuelve al inicio y procesa un archivo para empezar.
              </div>
            )}
            {failed && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                Proceso fallido. {data?.error ? `Detalle: ${data.error}` : null}
              </div>
            )}
          </div>

          {/* Stepper */}
          <div className="mt-6">
            <Stepper steps={steps} />
          </div>

          {/* Progreso */}
          <div className="mt-6 space-y-2">
            <div className="w-full h-2 bg-slate-200 rounded-full">
              <div
                className="h-2 rounded-full bg-emerald-600 transition-all"
                style={{ width: `${progress}%` }}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress}
                role="progressbar"
              />
            </div>
            <div className="text-xs text-slate-500">
              Progreso: {progress}% · Última actualización: {lastUpdate}
            </div>
          </div>

          {loading && <div className="mt-4 text-sm text-slate-500">Cargando…</div>}

          {/* ======= Descargas rápidas ======= */}
          {(csvHref || dashHref || repHref) && (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-slate-800 mb-3">Artefactos</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {csvHref && (
                  <a
                    className="rounded-lg border border-slate-200 hover:border-emerald-400 transition p-3 text-sm"
                    href={csvHref}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="font-medium">Archivo limpio (CSV)</div>
                    <div className="text-slate-500 mt-1">dataset_limpio.csv</div>
                  </a>
                )}
                {dashHref && (
                  <a
                    className="rounded-lg border border-slate-200 hover:border-emerald-400 transition p-3 text-sm"
                    href={dashHref}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="font-medium">Dashboard</div>
                    <div className="text-slate-500 mt-1">dashboard.html</div>
                  </a>
                )}
                {repHref && (
                  <a
                    className="rounded-lg border border-slate-200 hover:border-emerald-400 transition p-3 text-sm"
                    href={repHref}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="font-medium">Reporte</div>
                    <div className="text-slate-500 mt-1">reporte_integrado.html</div>
                  </a>
                )}
              </div>
            </section>
          )}

          {/* ======= Perfilado ======= */}
          {perfilHref && (
            <section className="mt-10">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-slate-800">Perfilado</h2>
                <button
                  type="button"
                  onClick={() => setShowProfile((v) => !v)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sky-700 hover:text-sky-900 focus:outline-none focus:ring-2 focus:ring-sky-300"
                  aria-expanded={showProfile}
                  aria-controls="perfilado-panel"
                  title={showProfile ? "Ocultar" : "Mostrar"}
                >
                  <svg viewBox="0 0 24 24" stroke="currentColor" fill="none"
                       className={`w-4 h-4 transition-transform ${showProfile ? "rotate-180" : ""}`}>
                    <path strokeWidth="1.8" d="M6 15l6-6 6 6" />
                  </svg>
                  <span className="text-sm">{showProfile ? "ocultar" : "mostrar"}</span>
                </button>
                <div className="flex-1 h-px bg-slate-200" />
              </div>

              <div id="perfilado-panel"
                   className={`mt-4 overflow-hidden transition-[max-height,opacity] duration-300 ${
                     showProfile ? "max-h-[90vh] opacity-100" : "max-h-0 opacity-0"
                   }`}>
                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <iframe src={perfilHref} title="Reporte de perfilado" className="w-full h-[72vh] bg-white" />
                </div>
              </div>

              <div className="mt-2 text-xs text-slate-500">
                Si el reporte no carga correctamente,{" "}
                <a className="text-sky-600 hover:underline" target="_blank" rel="noreferrer" href={perfilHref}>
                  ábrelo en una pestaña nueva
                </a>.
              </div>
            </section>
          )}

      {/* ======= Dashboard embebido ======= */}
{dashHref && (
  <section className="mt-10">
    <div className="flex items-center gap-3">
      <h2 className="text-base font-semibold text-slate-800">Dashboard</h2>
      <button
        type="button"
        onClick={() => setShowDash((v) => !v)}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sky-700 hover:text-sky-900 focus:outline-none focus:ring-2 focus:ring-sky-300"
        aria-expanded={showDash}
        aria-controls="dashboard-panel"
        title={showDash ? "Ocultar" : "Mostrar"}
      >
        <svg viewBox="0 0 24 24" stroke="currentColor" fill="none"
             className={`w-4 h-4 transition-transform ${showDash ? "rotate-180" : ""}`}>
          <path strokeWidth="1.8" d="M6 15l6-6 6 6" />
        </svg>
        <span className="text-sm">{showDash ? "ocultar" : "mostrar"}</span>
      </button>
      <div className="flex-1 h-px bg-slate-200" />
    </div>

    {/* 🔗 Hipervínculo solicitado */}
    <div className="mt-3">
      <a
        href={dashHref}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sky-600 hover:underline underline-offset-2"
      >
        haz clic aqui para ver el dashboard mejor en una pestaña aparte
      </a>
    </div>

    {/* Opcional: puedes borrar todo el panel de abajo si solo quieres el link */}
    <div
      id="dashboard-panel"
      className={`mt-4 overflow-hidden transition-[max-height,opacity] duration-300 ${
        showDash ? "max-h-[90vh] opacity-100" : "max-h-0 opacity-0"
      }`}
    >
      <div className="rounded-lg border border-slate-200 overflow-hidden">
        <iframe src={dashHref} title="Dashboard" className="w-full h-[72vh] bg-white" />
      </div>
    </div>
  </section>
)}


          {/* ======= Bitácora ======= */}
          <section className="mt-10">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-slate-800">Bitácora</h2>
              <button
                type="button"
                onClick={() => setShowHistory((v) => !v)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sky-700 hover:text-sky-900 focus:outline-none focus:ring-2 focus:ring-sky-300"
                aria-expanded={showHistory}
                aria-controls="history-panel"
                title={showHistory ? "Ocultar" : "Mostrar"}
              >
                <svg viewBox="0 0 24 24" stroke="currentColor" fill="none"
                     className={`w-4 h-4 transition-transform ${showHistory ? "rotate-180" : ""}`}>
                  <path strokeWidth="1.8" d="M6 15l6-6 6 6" />
                </svg>
                <span className="text-sm">{showHistory ? "ocultar" : "mostrar"}</span>
              </button>
              <div className="flex-1 h-px bg-slate-200" />
            </div>

            <div id="history-panel"
                 className={`mt-4 transition-[max-height,opacity] duration-300 ${
                   showHistory ? "max-h-[80vh] opacity-100" : "max-h-0 opacity-0 overflow-hidden"
                 }`}>
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="text-left p-2">ts</th>
                      <th className="text-left p-2">type</th>
                      <th className="text-left p-2">detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((e, idx) => (
                      <tr key={idx} className="border-t border-slate-100">
                        <td className="p-2 whitespace-nowrap">{e.ts}</td>
                        <td className="p-2">{e.type}</td>
                        <td className="p-2 text-slate-600">
                          <code className="text-[12px]">{JSON.stringify(e)}</code>
                        </td>
                      </tr>
                    ))}
                    {history.length === 0 && (
                      <tr><td className="p-3 text-slate-500" colSpan={3}>Sin eventos aún…</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 text-xs text-slate-500">
                La bitácora se descarga desde el backend como <code>history.jsonl</code>.
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
