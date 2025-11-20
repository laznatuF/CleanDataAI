// src/pages/Status.tsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Header from "../../components/Header";
import { getStatus, artifactUrl /* , getHistory */ } from "../../libs/api";

const PROCESS_FINISHED = new Set(["ok", "done", "finished", "completed", "success"]);

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

  // Bitácora (oculta por ahora)
  // const [history, setHistory] = useState<any[]>([]);
  // const [showHistory, setShowHistory] = useState(false);

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

  const perfilRel = data?.artifacts?.["reporte_perfilado.html"];
  const dashRel = data?.artifacts?.["dashboard.html"];
  const csvRel = data?.artifacts?.["dataset_limpio.csv"];
  const repRel = data?.artifacts?.["reporte_integrado.html"];

  const perfilHref = perfilRel ? artifactUrl(perfilRel) : null;
  const dashHref = dashRel ? artifactUrl(dashRel) : null;
  const csvHref = csvRel ? artifactUrl(csvRel) : null;
  const repHref = repRel ? artifactUrl(repRel) : null;

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-[1400px] px-6 md:px-8 py-8 md:py-10">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 md:p-10">
          {/* Avisos (solo cuando aplica) */}
          <div className="space-y-2 mb-4">
            {queued && (
              <div className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                El proceso está en cola… empezará en breve.
              </div>
            )}
            {!runId && (
              <div className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                Falta el <code>runId</code> en la ruta. Vuelve al inicio y procesa un
                archivo para empezar.
              </div>
            )}
            {failed && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                Proceso fallido. {data?.error ? `Detalle: ${data.error}` : null}
              </div>
            )}
          </div>

          {loading && (
            <div className="mb-4 text-sm text-slate-500">Cargando estado…</div>
          )}

          {/* ======= Tarjetas de artefactos (prototipo) ======= */}
          <ArtifactsPanel
            perfilHref={perfilHref}
            csvHref={csvHref}
            dashHref={dashHref}
            repHref={repHref}
          />

          {/* ======= Bitácora OCULTA ======= */}
          {/*
          <section className="mt-10">
            ...
          </section>
          */}
        </div>
      </main>
    </div>
  );
}

/* ---------- Tarjetas de artefactos (prototipo) ---------- */

type ArtifactsPanelProps = {
  perfilHref: string | null;
  csvHref: string | null;
  dashHref: string | null;
  repHref: string | null;
};

function ArtifactsPanel({ perfilHref, csvHref, dashHref, repHref }: ArtifactsPanelProps) {
  const btnPrimary =
    "inline-flex items-center justify-center rounded-full bg-[#F28C18] px-5 py-2 text-sm font-semibold text-white shadow hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40 disabled:opacity-60";
  const btnSecondary =
    "inline-flex items-center justify-center rounded-full border border-[#F28C18] bg-white px-5 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-[#FFF3E6] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/30 disabled:opacity-60";
  const cardBase =
    "flex flex-col justify-between rounded-3xl border border-[#E4DCCB] bg-white px-5 py-6 shadow-sm";

  const isFree = true; // versión gratis por defecto

  const ReadyBadge = () => (
    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
      <svg
        viewBox="0 0 24 24"
        className="mr-1 h-3.5 w-3.5"
        stroke="currentColor"
        fill="none"
      >
        <path
          d="M5 13l4 4 10-10"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Listo
    </span>
  );

  const GeneratingBadge = () => (
    <span className="inline-flex items-center rounded-full bg-orange-50 px-2.5 py-1 text-[11px] font-medium text-[#F28C18]">
      <span className="mr-1 h-3.5 w-3.5 rounded-full border-2 border-[#F28C18]/40 border-t-[#F28C18] animate-spin" />
      Generando…
    </span>
  );

  const StatusBadge = ({ ready }: { ready: boolean }) =>
    ready ? <ReadyBadge /> : <GeneratingBadge />;

  const perfilReady = !!perfilHref;
  const csvReady = !!csvHref;
  const dashReady = !!dashHref;
  // repReady no se muestra porque ese artefacto es solo de planes de pago

  return (
    <>
      {/* Grid de artefactos */}
      <section className="mt-2">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {/* PERFILADO */}
          <article className={cardBase}>
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <circle cx="11" cy="11" r="4.5" strokeWidth={1.8} />
                    <path
                      d="m15 15 3.5 3.5"
                      strokeWidth={1.8}
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <StatusBadge ready={perfilReady} />
              </div>

              <h3 className="text-sm font-semibold text-slate-900">Perfilado</h3>
              <p className="mt-1 text-xs text-slate-500">
                Vista rápida de calidad, tipos de datos y valores atípicos.
              </p>
            </div>

            <div className="mt-4 flex justify-center">
              <a
                href={perfilHref ?? undefined}
                target="_blank"
                rel="noreferrer"
                className={
                  btnPrimary +
                  (!perfilHref ? " pointer-events-none opacity-40 cursor-default" : "")
                }
              >
                Ver
              </a>
            </div>
          </article>

          {/* ARCHIVO LIMPIO */}
          <article className={cardBase}>
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="6"
                      y="3"
                      width="12"
                      height="18"
                      rx="2"
                      strokeWidth={1.8}
                    />
                    <path d="M9 9h6M9 13h4" strokeWidth={1.6} />
                  </svg>
                </div>
                <StatusBadge ready={csvReady} />
              </div>

              <h3 className="text-sm font-semibold text-slate-900">
                Archivo limpio (CSV)
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Datos listos para análisis o carga en tu herramienta favorita.
              </p>
            </div>

            <div className="mt-4 flex flex-col gap-2">
              <a
                href={csvHref ?? undefined}
                target="_blank"
                rel="noreferrer"
                className={
                  btnPrimary +
                  (!csvHref ? " pointer-events-none opacity-40 cursor-default" : "")
                }
              >
                Ver
              </a>
              <a
                href={csvHref ?? undefined}
                download
                className={
                  btnSecondary +
                  (!csvHref ? " pointer-events-none opacity-40 cursor-default" : "")
                }
              >
                Descargar
              </a>
            </div>
          </article>

          {/* DASHBOARD */}
          <article className={cardBase}>
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="4"
                      y="4"
                      width="16"
                      height="16"
                      rx="2"
                      strokeWidth={1.7}
                    />
                    <path
                      d="M8 16v-3M12 16V8M16 16v-4"
                      strokeWidth={1.7}
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <StatusBadge ready={dashReady} />
              </div>

              <h3 className="text-sm font-semibold text-slate-900">Dashboard</h3>
              <p className="mt-1 text-xs text-slate-500">
                Gráficos interactivos listos para compartir con tu equipo.
              </p>
            </div>

            <div className="mt-4 flex flex-col gap-2">
              <a
                href={dashHref ?? undefined}
                target="_blank"
                rel="noreferrer"
                className={
                  btnPrimary +
                  (!dashHref ? " pointer-events-none opacity-40 cursor-default" : "")
                }
              >
                Ver
              </a>
              <a
                href={dashHref ?? undefined}
                download
                className={
                  btnSecondary +
                  (!dashHref ? " pointer-events-none opacity-40 cursor-default" : "")
                }
              >
                Descargar
              </a>
            </div>
          </article>

          {/* REPORTE ANALÍTICO / DESCRIPTIVO */}
          <article className={cardBase}>
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="5"
                      y="3"
                      width="14"
                      height="18"
                      rx="2"
                      strokeWidth={1.8}
                    />
                    <path d="M8 9h8M8 12h6M8 15h5" strokeWidth={1.5} />
                  </svg>
                </div>

                {/* Candado / solo planes de pago */}
                <span className="inline-flex items-center text-[11px] font-medium text-slate-500">
                  <svg
                    viewBox="0 0 24 24"
                    className="mr-1 h-3.5 w-3.5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="5"
                      y="11"
                      width="14"
                      height="9"
                      rx="2"
                      strokeWidth={1.6}
                    />
                    <path d="M9 11V9a3 3 0 0 1 6 0v2" strokeWidth={1.6} />
                  </svg>
                  Solo planes de pago
                </span>
              </div>

              <h3 className="text-sm font-semibold text-slate-900">
                Reporte analítico y descriptivo
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Documento listo para descargar, compartir o adjuntar en informes.
              </p>
            </div>

            <div className="mt-4 flex justify-center">
              <button
                type="button"
                className={btnPrimary + " opacity-40 cursor-not-allowed"}
                disabled={isFree || !repHref}
              >
                Generar reporte
              </button>
            </div>
          </article>
        </div>
      </section>

      {/* Texto de versión gratis */}
      <section className="mt-8">
        <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 shadow-sm">
          <div className="mt-1 flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-white">
            i
          </div>
          <div className="text-sm text-slate-700">
            <p>
              Esta es la{" "}
              <span className="font-semibold">versión gratis</span>. Permite
              descargar solo el archivo limpio y el dashboard del primer proceso
              completado.
            </p>
            <p className="mt-1">
              Para crear el reporte y desbloquear funciones extra,&nbsp;
              <Link
                to="/planes"
                className="font-semibold text-[#1d7fd6] hover:underline"
              >
                actualiza tu plan
              </Link>
              .
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
