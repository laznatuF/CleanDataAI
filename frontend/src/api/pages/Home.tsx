// src/pages/Home.tsx
import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadFile } from "../../libs/api";

const ACCEPT = ".csv,.ods,.xlsx,.xls";
const MAX_MB = 20; // solo visual; el backend valida con MAX_FILE_SIZE_MB

export default function Home() {
  const navigate = useNavigate();

  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openDialog() {
    inputRef.current?.click();
  }

  function validateClient(file: File): string | null {
    // tipo por extensión
    const okType = ACCEPT.split(",").some((ext) =>
      file.name.toLowerCase().endsWith(ext.trim())
    );
    if (!okType) return "Formato no soportado. Usa CSV, ODS, XLSX o XLS.";

    // tamaño
    const maxBytes = MAX_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      const mb = (file.size / 1024 / 1024).toFixed(2);
      return `Archivo demasiado grande (${mb} MB). Límite permitido: ${MAX_MB} MB.`;
    }
    return null;
  }

  async function handlePicked(file: File | null) {
    if (!file) return;
    const msg = validateClient(file);
    if (msg) {
      setError(msg);
      return;
    }
    // Mantengo el comportamiento que ya funciona: subir y navegar inmediatamente
    try {
      setBusy(true);
      setError(null);
      const res = await uploadFile(file);
      const pid = res.process_id || res.id;
      navigate(`/status/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    handlePicked(e.target.files?.[0] ?? null);
    // limpiamos para permitir volver a elegir el mismo archivo
    if (inputRef.current) inputRef.current.value = "";
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    handlePicked(e.dataTransfer.files?.[0] ?? null);
  }

  return (
    <div className="min-h-screen bg-white text-slate-800">
      {/* Top bar */}
      <header className="border-b border-slate-200">
        <div className="mx-auto max-w-6xl px-5 h-14 flex items-center justify-between">
          <div className="font-semibold text-lg">
            <span className="text-sky-600">Clean</span>DataAI
          </div>
          <nav className="flex gap-6 text-sm text-slate-600">
            <a href="#" className="hover:text-slate-900">Ayuda</a>
            <a href="#" className="hover:text-slate-900">Acerca de</a>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-6xl px-5 py-10">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-8 md:p-10">
          <h1 className="text-2xl font-semibold">Sube tu archivo</h1>
          <p className="mt-1 text-sm text-slate-500">
            Automatiza limpiar y preparar tus planillas en minutos.
          </p>

          {/* Dropzone card */}
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
                "px-6 py-14 text-center",
                over ? "bg-slate-50 border-slate-400" : "border-slate-300",
              ].join(" ")}
              aria-label="Zona para arrastrar o seleccionar archivo"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") openDialog();
              }}
            >
              {/* input oculto */}
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={onInputChange}
              />

              {/* Icono */}
              <div className="mx-auto mb-3 h-8 w-8 text-slate-400">
                {/* nube flecha */}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  className="w-full h-full"
                >
                  <path d="M20 16.5a4.5 4.5 0 0 0-3.6-4.41A6 6 0 1 0 4.5 13" />
                  <path d="M12 12v7" />
                  <path d="m8.5 15.5 3.5-3.5 3.5 3.5" />
                </svg>
              </div>

              <div className="text-sm text-slate-600">
                Arrastra tu archivo aquí
              </div>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={openDialog}
                  className="inline-flex items-center rounded-md bg-sky-600 px-4 py-2 text-white text-sm font-medium hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-600 disabled:opacity-60"
                  disabled={busy}
                >
                  Examinar
                </button>
              </div>
            </div>

            {/* línea de formatos */}
            <div className="mt-3 text-center text-[12px] text-slate-500">
              (.csv, .ods, .xlsx, .xls) — Máx. {MAX_MB} MB
            </div>
          </div>

          {/* Botón Procesar + notas */}
          <div className="mt-8 flex items-center gap-4">
            <button
              type="button"
              onClick={openDialog}
              className="inline-flex items-center rounded-md border border-slate-300 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300 disabled:opacity-60"
              disabled={busy}
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
