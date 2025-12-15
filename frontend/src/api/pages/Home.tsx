// frontend/src/pages/Home.tsx
import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadFile, uploadMultiFiles } from "../../libs/api";
import Header from "../../components/Header";

const ACCEPT = ".csv,.ods,.xlsx,.xls";
const MAX_MB = 20; // visual; el backend valida con MAX_FILE_SIZE_MB

export default function Home() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [over, setOver] = useState(false); // estado de drag-over
  const [busy, setBusy] = useState(false); // subiendo/procesando
  const [error, setError] = useState<string | null>(null);

  const [files, setFiles] = useState<File[]>([]); // ahora puede haber 1 o varios archivos

  function openDialog() {
    inputRef.current?.click();
  }

  function clearInputControl() {
    if (inputRef.current) inputRef.current.value = "";
  }

  function validateClient(f: File): string | null {
    const okType = ACCEPT.split(",").some((ext) =>
      f.name.toLowerCase().endsWith(ext.trim())
    );
    if (!okType) return "Formato no soportado. Usa CSV, ODS, XLSX o XLS.";
    const maxBytes = MAX_MB * 1024 * 1024;
    if (f.size > maxBytes) {
      const mb = (f.size / 1024 / 1024).toFixed(2);
      return `Archivo demasiado grande (${mb} MB). Límite permitido: ${MAX_MB} MB.`;
    }
    return null;
  }

  // Ahora admite 1 o más archivos
  function pickFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;

    const arr = Array.from(fileList);
    const next: File[] = [];

    for (const f of arr) {
      const msg = validateClient(f);
      if (msg) {
        setError(msg);
        setFiles([]);
        return;
      }
      next.push(f);
    }

    setError(null);
    setFiles(next);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    pickFiles(e.target.files);
    clearInputControl(); // permite volver a elegir el mismo archivo luego
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    pickFiles(e.dataTransfer.files);
  }

  async function onProcess() {
    if (!files.length) {
      setError("Selecciona al menos un archivo antes de procesar.");
      return;
    }
    try {
      setBusy(true);
      setError(null);

      let res: any;
      if (files.length === 1) {
        // MODO NORMAL (1 archivo)
        res = await uploadFile(files[0]);
      } else {
        // MODO MULTICANAL (Shopify + Mercado Libre, etc.)
        res = await uploadMultiFiles(files);
      }

      const pid = res.process_id || res.id;
      navigate(`/status/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function removeFiles() {
    setFiles([]);
    setError(null);
  }

  const fileInfo =
    files.length === 1
      ? `${files[0].name} — ${(files[0].size / 1024 / 1024).toFixed(2)} MB`
      : files.length > 1
      ? `${files.length} archivos seleccionados`
      : null;

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      {/* Logo + menú (modo flotante / barra responsiva) */}
      <Header />

      {/* Contenido principal */}
     <main className="pt-28 pb-16 px-4 md:pt-32 md:px-6 lg:pt-40 lg:pl-40 lg:pr-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-10 lg:flex-row lg:items-start">
          {/* Columna principal: subir archivo(s) */}
          <section className="flex-1">
          <header className="mb-6 text-center relative">
  {/* Título flotante (no empuja nada) */}
  <div className="absolute left-1/2 -translate-x-1/2 -top-24 md:-top-28 lg:-top-32 z-10">
    <div className="inline-flex flex-col items-center pointer-events-none select-none">
      <h1
        className="
          text-4xl md:text-5xl font-extrabold tracking-tight
          bg-gradient-to-r from-[#F6A04D] via-[#FFD1A1] to-[#E88A2E]

          bg-clip-text text-transparent drop-shadow-sm
        "
      >
        CleanDataAI
      </h1>
      <div className="mt-2 h-[3px] w-24 rounded-full bg-gradient-to-r from-[#F6A04D] to-[#E88A2E] opacity-80" />

    </div>
  </div>

  {/* Esto queda en su posición normal (la de antes) */}
  <h1 className="text-2xl font-semibold text-slate-900">
    Sube tu archivo
  </h1>
  <p className="mt-1 text-sm text-slate-500">
    Automatiza la limpieza y prepara tus planillas en segundos.
  </p>
</header>


            <div className="rounded-3xl border border-[#E4DCCB] bg-white px-4 py-6 shadow-sm sm:px-6 sm:py-7 md:px-10 md:py-9">
              {/* Zona de carga */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setOver(true);
                }}
                onDragLeave={() => setOver(false)}
                onDrop={onDrop}
                className={[
                  "rounded-2xl border-2 border-dashed transition-colors",
                  "px-4 sm:px-6 py-10 sm:py-14 text-center",
                  over
                    ? "bg-slate-50 border-[#F28C18]/60"
                    : "border-slate-300 bg-[#FDFBF6]",
                ].join(" ")}
                aria-label="Zona para arrastrar o seleccionar archivo(s)"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") openDialog();
                }}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  multiple
                  className="hidden"
                  onChange={onInputChange}
                />

                <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-[#F28C18]/10 text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <path d="M20 16.5a4.5 4.5 0 0 0-3.6-4.41A6 6 0 1 0 4.5 13" />
                    <path d="M12 12v7" />
                    <path d="m8.5 15.5 3.5-3.5 3.5 3.5" />
                  </svg>
                </div>

                {/* ✅ Cambiado el texto del dropzone */}
                <p className="text-sm text-slate-600">
                  Arrastra tus archivos aquí o haz clic para examinar
                </p>

                <div className="mt-5 flex items-center justify-center gap-3">
                  <button
                    type="button"
                    onClick={openDialog}
                    className="inline-flex items-center rounded-full bg-[#F28C18] px-5 py-2 text-sm font-medium text-white shadow hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#F28C18] disabled:opacity-60"
                    disabled={busy}
                  >
                    {files.length ? "Cambiar archivos" : "Examinar"}
                  </button>

                  {files.length > 0 && (
                    <button
                      type="button"
                      onClick={removeFiles}
                      className="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300 disabled:opacity-60"
                      disabled={busy}
                    >
                      Quitar
                    </button>
                  )}
                </div>

                {/* Info del archivo/archivos seleccionados */}
                {fileInfo && (
                  <div className="mt-4 text-xs text-slate-500">{fileInfo}</div>
                )}

                <div className="mt-3 text-[11px] text-slate-500">
                  (.csv, .ods, .xlsx, .xls) — Máx. {MAX_MB} MB por archivo
                </div>
              </div>

              {/* Botón procesar + mensajes */}
              <div className="mt-6 flex items-center justify-center gap-4">
                <button
                  type="button"
                  onClick={onProcess}
                  className="inline-flex items-center rounded-full bg-[#333A46] px-5 py-2 text-sm font-medium text-white hover:bg-[#252a33] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#333A46] disabled:opacity-60"
                  disabled={busy || !files.length}
                  title={
                    !files.length
                      ? "Selecciona al menos un archivo para continuar"
                      : "Procesar"
                  }
                >
                  Procesar
                </button>

                {busy && (
                  <span className="text-xs text-slate-500">
                    Subiendo y creando proceso…
                  </span>
                )}
              </div>

              {error && (
                <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              )}

              <p className="mt-6 text-[11px] text-slate-400 text-center">
                En cumplimiento de privacidad: los archivos temporales se
                eliminan tras el proceso.
              </p>
            </div>
          </section>

          {/* Columna derecha: GENERA */}
          <aside className="w-full shrink-0 lg:w-[320px] lg:mt-14">
            <h2 className="text-[11px] font-semibold tracking-[0.18em] text-slate-500">
              GENERA
            </h2>

            <div className="mt-3 space-y-3">
              {/* Perfilado de datos */}
              <div className="flex items-center gap-3 rounded-2xl border border-[#E4DCCB] bg-white px-4 py-3 shadow-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
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
                <p className="text-sm font-medium text-slate-900">
                  Perfilado de datos
                </p>
              </div>

              {/* Archivo limpio */}
              <div className="flex items-center gap-3 rounded-2xl border border-[#E4DCCB] bg-white px-4 py-3 shadow-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="6"
                      y="4"
                      width="12"
                      height="16"
                      rx="2"
                      strokeWidth={1.8}
                    />
                    <path d="M9 9h6M9 13h4" strokeWidth={1.6} />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-900">
                  Archivo limpio (descargable)
                </p>
              </div>

              {/* Dashboard */}
              <div className="flex items-center gap-3 rounded-2xl border border-[#E4DCCB] bg-white px-4 py-3 shadow-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    stroke="currentColor"
                    fill="none"
                  >
                    <path
                      d="M6 17v-4M11 17V7M16 17v-6"
                      strokeWidth={1.8}
                      strokeLinecap="round"
                    />
                    <rect
                      x="4"
                      y="4"
                      width="16"
                      height="16"
                      rx="2"
                      strokeWidth={1.5}
                    />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-900">Dashboard</p>
              </div>

              {/* Reporte analítico y descriptivo */}
              <div className="flex items-center gap-3 rounded-2xl border border-[#E4DCCB] bg-white px-4 py-3 shadow-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    stroke="currentColor"
                    fill="none"
                  >
                    <rect
                      x="5"
                      y="4"
                      width="14"
                      height="16"
                      rx="2"
                      strokeWidth={1.8}
                    />
                    <path d="M8 9h8M8 12h6M8 15h5" strokeWidth={1.5} />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-900">
                  Reporte analítico y descriptivo
                </p>
              </div>

              {/* Exporta en PDF */}
              <div className="flex items-center gap-3 rounded-2xl border border-[#E4DCCB] bg-white px-4 py-3 shadow-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFE4C2] text-[#F28C18]">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
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
                    <path
                      d="M9 16h2.2c1.2 0 1.8-.6 1.8-1.6 0-.9-.6-1.6-1.8-1.6H9v3.2Z"
                      strokeWidth={1.4}
                    />
                    <path d="M9 9h6" strokeWidth={1.4} />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-900">
                  Exporta en PDF (descargable)
                </p>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
