// src/pages/Home.tsx
import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadFile } from "../../libs/api";
import Header from "../../components/Header";

const ACCEPT = ".csv,.ods,.xlsx,.xls";
const MAX_MB = 20; // visual; el backend valida con MAX_FILE_SIZE_MB

export default function Home() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [over, setOver] = useState(false);           // estado de drag-over
  const [busy, setBusy] = useState(false);           // subiendo/procesando
  const [error, setError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null); // archivo seleccionado (no subido)

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

  // Solo guarda/valida el archivo. No sube ni navega aún.
  function pickFile(f: File | null) {
    if (!f) return;
    const msg = validateClient(f);
    if (msg) {
      setError(msg);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    pickFile(e.target.files?.[0] ?? null);
    clearInputControl(); // permite volver a elegir el mismo archivo luego
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    pickFile(e.dataTransfer.files?.[0] ?? null);
  }

  async function onProcess() {
    if (!file) {
      setError("Selecciona un archivo antes de procesar.");
      return;
    }
    try {
      setBusy(true);
      setError(null);
      const res = await uploadFile(file); // aquí recién llamamos al backend
      const pid = res.process_id || res.id;
      navigate(`/status/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function removeFile() {
    setFile(null);
    setError(null);
  }

  const fileInfo =
    file &&
    `${file.name} — ${(file.size / 1024 / 1024).toFixed(2)} MB`;

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-[1200px] px-6 md:px-8 py-8 md:py-10">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 md:p-10">
          <h1 className="text-xl md:text-2xl font-semibold">Sube tu archivo</h1>
          <p className="mt-1 text-sm text-slate-500">
            Automatiza la limpieza y prepara tus planillas en minutos.
          </p>

          <div className="mt-8">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={onDrop}
              className={[
                "rounded-xl border-2 border-dashed transition-colors",
                "px-4 sm:px-6 py-10 sm:py-14 text-center",
                over ? "bg-slate-50 border-slate-400" : "border-slate-300",
              ].join(" ")}
              aria-label="Zona para arrastrar o seleccionar archivo"
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
                className="hidden"
                onChange={onInputChange}
              />

              <div className="mx-auto mb-3 h-8 w-8 text-slate-400">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-full h-full">
                  <path d="M20 16.5a4.5 4.5 0 0 0-3.6-4.41A6 6 0 1 0 4.5 13" />
                  <path d="M12 12v7" />
                  <path d="m8.5 15.5 3.5-3.5 3.5 3.5" />
                </svg>
              </div>

              <div className="text-sm text-slate-600">
                {file ? "Archivo listo para procesar" : "Arrastra tu archivo aquí"}
              </div>

              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={openDialog}
                  className="inline-flex items-center rounded-md bg-sky-600 px-4 py-2 text-white text-sm font-medium hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-600 disabled:opacity-60"
                  disabled={busy}
                >
                  {file ? "Cambiar" : "Examinar"}
                </button>

                {file && (
                  <button
                    type="button"
                    onClick={removeFile}
                    className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300 disabled:opacity-60"
                    disabled={busy}
                  >
                    Quitar
                  </button>
                )}
              </div>

              {/* Info del archivo seleccionado */}
              {file && (
                <div className="mt-4 text-sm text-slate-500">
                  {fileInfo}
                </div>
              )}
            </div>

            <div className="mt-3 text-center text-[12px] text-slate-500">
              (.csv, .ods, .xlsx, .xls) — Máx. {MAX_MB} MB
            </div>
          </div>

          <div className="mt-8 flex items-center gap-4">
            <button
              type="button"
              onClick={onProcess}
              className="inline-flex items-center rounded-md border border-slate-300 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300 disabled:opacity-60"
              disabled={busy || !file}
              title={!file ? "Selecciona un archivo para continuar" : "Procesar"}
            >
              Procesar
            </button>

            {busy && (
              <span className="text-sm text-slate-500">Subiendo y creando proceso…</span>
            )}
          </div>

          {error && (
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <p className="mt-6 text-[11px] text-slate-400">
            En cumplimiento de privacidad: los archivos temporales se eliminan tras el proceso.
          </p>
        </div>
      </main>
    </div>
  );
}
