// src/pages/Status.tsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Header from "../../components/Header";
import { getStatus, artifactUrl, requestDashboard } from "../../libs/api";

const PROCESS_FINISHED = new Set([
  "ok",
  "done",
  "finished",
  "completed",
  "success",
]);

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

// --- Helper para forzar descargas ---
function forceDownload(url: string, fileName?: string) {
  const link = document.createElement("a");
  link.href = url;
  if (fileName) link.setAttribute("download", fileName);
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default function StatusPage() {
  const params = useParams();
  const runId = ((params.runId as string) ?? (params.id as string) ?? "").trim();

  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

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

  const statusStr = String(data?.status ?? "");
  const failed = statusStr === "failed";
  const queued = statusStr === "queued" || statusStr === "pending";

  // ===== Artefactos =====
  // 1. Perfilado
  const perfilRel = data?.artifacts?.["reporte_perfilado.html"];
  const perfilCsvRel = data?.artifacts?.["reporte_perfilado.csv"];
  const perfilPdfRel = data?.artifacts?.["reporte_perfilado.pdf"];

  // 2. Dashboard / HTML
  const dashRel = data?.artifacts?.["dashboard.html"];

  // 3. Datos Limpios
  const csvRel = data?.artifacts?.["dataset_limpio.csv"];

  // 4. Reporte Narrativo (AI)
  const narrativeRel = data?.artifacts?.["reporte_narrativo.html"];

  // 5. Archivo Original
  const inputRel = data?.artifacts?.["input_original"];

  // --- URLs absolutas ---
  const perfilHref = perfilRel ? artifactUrl(perfilRel) : null;
  const perfilCsvHref = perfilCsvRel ? artifactUrl(perfilCsvRel) : null;
  const perfilPdfHref = perfilPdfRel ? artifactUrl(perfilPdfRel) : null;

  const dashHref = dashRel ? artifactUrl(dashRel) : null;
  const csvHref = csvRel ? artifactUrl(csvRel) : null;

  const narrativeHref = narrativeRel ? artifactUrl(narrativeRel) : null;

  const inputHref = inputRel ? artifactUrl(inputRel) : null;

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-[1400px] px-6 md:px-8 py-8">
        <div className="rounded-3xl border border-[#E4DCCB] bg-[#FDFBF6] shadow-sm p-6 md:p-10">
          {/* Encabezado de estado */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">Estado del Proceso</h1>
            <p className="text-sm text-slate-500 font-mono mt-1">ID: {runId}</p>
          </div>

          {/* Avisos */}
          <div className="space-y-2 mb-6">
            {queued && (
              <div className="rounded-xl bg-yellow-50 border border-yellow-100 px-4 py-3 text-sm text-yellow-800 flex items-center gap-2">
                <span className="animate-pulse">⏳</span> El proceso está en cola… empezará en breve.
              </div>
            )}
            {failed && (
              <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700">
                ❌ Proceso fallido. {data?.error ? `Detalle: ${data.error}` : null}
              </div>
            )}
            {loading && (
              <div className="text-sm text-slate-500 animate-pulse">
                Actualizando estado...
              </div>
            )}
          </div>

          {/* ======= Tarjetas de artefactos ======= */}
          <ArtifactsPanel
            runId={runId}
            status={statusStr}
            currentStep={data?.current_step ?? null}
            perfilHref={perfilHref}
            perfilCsvHref={perfilCsvHref}
            perfilPdfHref={perfilPdfHref}
            csvHref={csvHref}
            dashHref={dashHref}
            narrativeHref={narrativeHref}
            inputHref={inputHref}
          />
        </div>
      </main>
    </div>
  );
}

/* ---------- Tarjetas de artefactos ---------- */

type ArtifactsPanelProps = {
  runId: string;
  status: string;
  currentStep?: string | null;
  perfilHref: string | null;
  perfilCsvHref: string | null;
  perfilPdfHref: string | null;
  csvHref: string | null;
  dashHref: string | null;
  narrativeHref: string | null;
  inputHref: string | null;
};

function ArtifactsPanel({
  runId,
  status,
  currentStep,
  perfilHref,
  perfilCsvHref,
  perfilPdfHref,
  csvHref,
  dashHref,
  narrativeHref,
  inputHref,
}: ArtifactsPanelProps) {
  const [dashLoading, setDashLoading] = useState(false);
  const [dashError, setDashError] = useState<string | null>(null);

  // Estados para los Modales
  const [showPerfilModal, setShowPerfilModal] = useState(false);
  const [showCsvModal, setShowCsvModal] = useState(false);
  const [showDashModal, setShowDashModal] = useState(false);

  useEffect(() => {
    if (dashHref) {
      setDashLoading(false);
    }
  }, [dashHref]);

  // --- Estilos con tu paleta ---
  const btnPrimary =
    "inline-flex items-center justify-center w-full rounded-full bg-[#F28C18] px-5 py-2.5 text-sm font-bold text-white shadow-md hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40 transition-all disabled:opacity-60 disabled:cursor-not-allowed";

  const btnSecondary =
    "inline-flex items-center justify-center w-full rounded-full border-2 border-[#F28C18] bg-white px-5 py-2.5 text-sm font-bold text-[#F28C18] shadow-sm hover:bg-[#FFF8F0] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed";

  const cardBase =
    "flex flex-col justify-between rounded-3xl border border-[#E4DCCB] bg-white px-6 py-7 shadow-sm relative transition-all hover:shadow-md";

  // Badges
  const ReadyBadge = () => (
    <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-800 border border-emerald-200">
      ✓ Listo
    </span>
  );

  const GeneratingBadge = () => (
    <span className="inline-flex items-center rounded-full bg-orange-100 px-2.5 py-1 text-[11px] font-bold text-orange-700 border border-orange-200">
      <span className="mr-1.5 h-3 w-3 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />
      Procesando
    </span>
  );

  const StatusBadge = ({ ready }: { ready: boolean }) =>
    ready ? <ReadyBadge /> : <GeneratingBadge />;

  const perfilReady = !!perfilHref;
  const csvReady = !!csvHref;
  const dashReady = !!dashHref;
  const narrativeReady = !!narrativeHref;

  const dashInProgress =
    !dashReady &&
    (dashLoading || (status === "running" && currentStep === "Dashboard"));

  async function handleGenerateDashboard() {
    if (!runId || dashReady || dashLoading) return;
    try {
      setDashError(null);
      setDashLoading(true);
      await requestDashboard(runId);
    } catch (err: any) {
      setDashLoading(false);
      setDashError(
        err?.message || "Error al iniciar la generación del dashboard"
      );
    }
  }

  // --- Descarga Masiva CSV (tarjeta Archivo limpio) ---
  function handleDownloadAll() {
    if (csvHref) forceDownload(csvHref, "dataset_limpio.csv");
    setTimeout(() => {
      if (inputHref) forceDownload(inputHref, "archivo_original");
    }, 800);
    setShowCsvModal(false);
  }

  // --- PDF Dashboard: abre dashboard.html con ?autoPrint=1 ---
  function handleDashboardPdf() {
    if (!dashHref) return;
    const url = dashHref.includes("?")
      ? `${dashHref}&autoPrint=1`
      : `${dashHref}?autoPrint=1`;
    window.open(url, "_blank");
  }

  // --- PDF Perfilado: descarga reporte_perfilado.pdf ---
  function handlePerfilPdf() {
    const url = perfilPdfHref || perfilHref;
    if (!url) return;
    forceDownload(url, "reporte_perfilado.pdf");
    setShowPerfilModal(false);
  }

  return (
    <section className="mt-4">
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        {/* 1. PERFILADO */}
        <article className={cardBase}>
          <div>
            <div className="mb-5 flex items-center justify-between">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF3E6] text-[#F28C18]">
                {/* Icono Lupa */}
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  stroke="currentColor"
                  fill="none"
                  strokeWidth={2}
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" strokeLinecap="round" />
                </svg>
              </div>
              <StatusBadge ready={perfilReady} />
            </div>
            <h3 className="text-base font-bold text-slate-900">
              Perfilado de datos
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              Análisis estadístico inicial. Calidad, tipos de datos y
              distribución.
            </p>
          </div>
          <div className="mt-6 flex flex-col gap-3 relative">
            {/* Ver Online (igual que antes) */}
            <Link
              to={
                perfilHref
                  ? `/perfilado?url=${encodeURIComponent(perfilHref)}`
                  : "#"
              }
              className={
                btnPrimary +
                (!perfilHref ? " opacity-50 pointer-events-none" : "")
              }
            >
              Ver Online
            </Link>

            {/* Nuevo botón Descargar... -> modal solo PDF */}
            <button
              type="button"
              onClick={() => setShowPerfilModal(true)}
              disabled={!perfilPdfHref && !perfilHref}
              className={
                btnSecondary +
                (!perfilPdfHref && !perfilHref
                  ? " opacity-50 pointer-events-none"
                  : "")
              }
            >
              Descargar...
            </button>

            {showPerfilModal && (
              <div className="absolute bottom-0 left-0 right-0 z-20 flex flex-col gap-3 p-4 bg-[#F5F1E4] rounded-xl shadow-xl border border-[#E4DCCB] animate-in slide-in-from-bottom-2 fade-in duration-200">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider text-center">
                  Descarga en
                </h4>
                <p className="text-[11px] text-slate-500 text-center -mt-1 mb-1">
                  
                </p>

                <div className="flex justify-center gap-3 mt-1">
                  <button
                    type="button"
                    onClick={() => setShowPerfilModal(false)}
                    className="px-4 py-2 text-xs font-semibold rounded-full bg-white border border-slate-300 text-slate-600 hover:bg-slate-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={handlePerfilPdf}
                    className="px-5 py-2 text-xs font-bold rounded-full bg-[#F28C18] text-white shadow-sm hover:bg-[#d9730d]"
                  >
                    PDF
                  </button>
                </div>
              </div>
            )}
          </div>
        </article>

        {/* 2. ARCHIVO LIMPIO (CSV) - CON MODAL */}
        <article className={cardBase}>
          <div>
            <div className="mb-5 flex items-center justify-between">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF3E6] text-[#F28C18]">
                {/* Icono Archivo */}
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  stroke="currentColor"
                  fill="none"
                  strokeWidth={2}
                >
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <line x1="10" y1="9" x2="8" y2="9" />
                </svg>
              </div>
              <StatusBadge ready={csvReady} />
            </div>
            <h3 className="text-base font-bold text-slate-900">
              Archivo limpio (CSV)
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              Dataset corregido y estandarizado, listo para usar.
            </p>
          </div>
          <div className="mt-6 flex flex-col gap-3 relative">
            <Link
              to={
                csvHref
                  ? `/csv-preview?url=${encodeURIComponent(
                      csvHref
                    )}&id=${encodeURIComponent(runId)}`
                  : "#"
              }
              className={
                btnPrimary +
                (!csvHref ? " opacity-50 pointer-events-none" : "")
              }
            >
              Ver Tabla
            </Link>

            <button
              onClick={() => setShowCsvModal(true)}
              disabled={!csvReady}
              className={btnSecondary}
            >
              Descargar...
            </button>

            {/* === MODAL DESCARGA CSV === */}
            {showCsvModal && (
              <div className="absolute bottom-0 left-0 right-0 z-20 flex flex-col gap-2 p-4 bg-[#F5F1E4] rounded-xl shadow-xl border border-[#E4DCCB] animate-in slide-in-from-bottom-2 fade-in duration-200">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider text-center mb-1">
                  Elige qué descargar
                </h4>

                {/* 1. CSV Limpio */}
                <a
                  href={csvHref || "#"}
                  download
                  className="block w-full text-center py-2 text-xs font-bold text-[#F28C18] bg-white border border-[#F28C18]/30 rounded-lg hover:bg-orange-50 transition-colors"
                >
                  📄 CSV Limpio
                </a>

                {/* 2. Archivo Original */}
                <a
                  href={inputHref || "#"}
                  download
                  className={`block w-full text-center py-2 text-xs font-bold text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 ${
                    !inputHref && "opacity-50 pointer-events-none"
                  }`}
                >
                  📦 Archivo Original
                </a>

                <div className="h-px bg-[#E4DCCB] my-1"></div>

                {/* 3. Descargar Todo */}
                <button
                  onClick={handleDownloadAll}
                  className="block w-full text-center py-2 text-xs font-bold text-white bg-slate-800 rounded-lg hover:bg-slate-900 shadow-sm"
                >
                  ⬇️ Descargar Todo
                </button>

                <button
                  onClick={() => setShowCsvModal(false)}
                  className="mt-1 text-[10px] font-medium text-red-500 hover:underline self-center"
                >
                  Cancelar
                </button>
              </div>
            )}
          </div>
        </article>

        {/* 3. DASHBOARD - CON MODAL */}
        <article className={cardBase}>
          <div>
            <div className="mb-5 flex items-center justify-between">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF3E6] text-[#F28C18]">
                {/* Icono Gráfico */}
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  stroke="currentColor"
                  fill="none"
                  strokeWidth={2}
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="9" y1="21" x2="9" y2="9" />
                </svg>
              </div>
              {dashReady ? <ReadyBadge /> : dashInProgress ? <GeneratingBadge /> : null}
            </div>
            <h3 className="text-base font-bold text-slate-900">Dashboard</h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              Visualización interactiva. Gráficos clave generados automáticamente.
            </p>
          </div>

          <div className="mt-6 flex flex-col gap-3 relative">
            {dashReady ? (
              <>
                <a
                  href={dashHref ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className={btnPrimary}
                >
                  Ver Interactivo
                </a>

                <button
                  type="button"
                  onClick={() => setShowDashModal(true)}
                  className={btnSecondary}
                >
                  Descargar...
                </button>

                {/* === MODAL DASHBOARD === */}
                {showDashModal && (
                  <div className="absolute bottom-0 left-0 right-0 z-20 flex flex-col gap-2 p-4 bg-[#F5F1E4] rounded-xl shadow-xl border border-[#E4DCCB] animate-in slide-in-from-bottom-2 fade-in duration-200">
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider text-center mb-1">
                      Descargar en
                    </h4>

                    <button
                      type="button"
                      onClick={handleDashboardPdf}
                      className="block w-full text-center py-2 text-xs font-bold text-white bg-red-600 rounded-lg hover:bg-red-700 shadow-sm"
                    >
                      PDF
                    </button>

                    <button
                      onClick={() => setShowDashModal(false)}
                      className="mt-2 text-[10px] font-medium text-slate-500 hover:underline self-center"
                    >
                      Cerrar
                    </button>
                  </div>
                )}
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={handleGenerateDashboard}
                  disabled={!csvHref || !runId || dashInProgress}
                  className={
                    btnPrimary +
                    (!csvHref || !runId || dashInProgress
                      ? " opacity-50 cursor-not-allowed"
                      : "")
                  }
                >
                  {dashInProgress ? "Generando..." : "Generar Dashboard"}
                </button>
                {dashError && (
                  <p className="mt-2 text-xs text-red-500 font-medium text-center">
                    {dashError}
                  </p>
                )}
              </>
            )}
          </div>
        </article>

        {/* 4. REPORTE NARRATIVO AI (igual que antes, solo "Leer Reporte") */}
        <article className={cardBase}>
          <div>
            <div className="mb-5 flex items-center justify-between">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
                {/* Icono AI/Documento */}
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  stroke="currentColor"
                  fill="none"
                  strokeWidth={2}
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                  <path d="M16 13H8" />
                  <path d="M16 17H8" />
                  <path d="M10 9H8" />
                </svg>
              </div>
              {narrativeReady ? <ReadyBadge /> : dashInProgress ? <GeneratingBadge /> : null}
            </div>
            <h3 className="text-base font-bold text-slate-900">
              Reporte Narrativo AI
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              Storytelling automático. La IA interpreta tus datos y genera
              conclusiones estratégicas.
            </p>
          </div>

          <div className="mt-6">
            {narrativeReady ? (
              <a
                href={narrativeHref ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center w-full rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white shadow-md hover:bg-indigo-700 focus:outline-none transition-all"
              >
                Leer Reporte
              </a>
            ) : (
              <div className="rounded-lg bg-slate-100 py-3 px-4 text-center">
                <span className="text-xs font-medium text-slate-500">
                  Se generará junto al Dashboard
                </span>
              </div>
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
