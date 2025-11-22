// src/api/pages/ProfilePreview.tsx
import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../../components/Header";

function useQuery() {
  const location = useLocation();
  return new URLSearchParams(location.search);
}

export default function ProfilePreview() {
  const query = useQuery();
  const navigate = useNavigate();

  const url = query.get("url");  // HTML del perfilado (iframe)
  const csv = query.get("csv");  // dataset_limpio.csv
  const pdf = query.get("pdf");  // reporte_integrado (HTML o PDF)

  const [showDialog, setShowDialog] = useState(false);

  // Añade el parámetro ?download=1 o &download=1 según corresponda
  const addDownloadParam = (base: string) => {
    try {
      const u = new URL(base);
      if (!u.searchParams.has("download")) {
        u.searchParams.set("download", "1");
      }
      return u.toString();
    } catch {
      const sep = base.includes("?") ? "&" : "?";
      return `${base}${sep}download=1`;
    }
  };

  const handleDownload = (kind: "csv" | "pdf") => {
    let target: string | null = null;

    if (kind === "csv") {
      // Prioridad: CSV que vino por query, si no, la propia URL del perfilado
      target = csv || url;
    } else {
      // Prioridad: PDF/reporte integrado que vino por query, si no, la URL del perfilado
      target = pdf || url;
    }

    if (!target) {
      alert("No se encontró un enlace para descargar este perfilado.");
      return;
    }

    const finalUrl = addDownloadParam(target);
    // Esto abre una nueva pestaña/descarga, no debería ser bloqueado porque viene de un click
    window.open(finalUrl, "_blank");
    setShowDialog(false);
  };

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[1400px] px-6 md:px-8 py-8">
        <h1 className="text-xl font-semibold text-slate-900">
          Perfilado de datos
        </h1>

        {!url && (
          <p className="mt-4 text-sm text-red-600">
            No se indicó la URL del reporte de perfilado.
          </p>
        )}

        {url && (
          <>
            {/* marco con el reporte HTML embebido */}
            <div className="mt-4 max-h-[70vh] rounded-2xl border bg-white overflow-auto">
              <iframe
                src={url}
                title="Reporte de perfilado"
                className="w-full h-[70vh] border-0"
              />
            </div>

            {/* botones ABAJO */}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => window.open(url, "_blank")}
                className="rounded-full border border-[#F28C18]/60 bg-white px-4 py-2 text-sm font-medium text-[#F28C18] hover:bg-[#FFF3E6]"
              >
                Ver en otra ventana
              </button>

              <button
                type="button"
                onClick={() => setShowDialog(true)}
                className="rounded-full bg-[#F28C18] px-4 py-2 text-sm font-medium text-white hover:bg-[#d9730d]"
              >
                Descargar
              </button>

              <button
                type="button"
                onClick={() => navigate(-1)}
                className="rounded-full bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900"
              >
                Volver
              </button>
            </div>
          </>
        )}

        {/* Diálogo de selección CSV / PDF */}
        {showDialog && (
          <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
              <h2 className="text-base font-semibold text-slate-900">
                ¿En qué formato quieres descargar el perfilado?
              </h2>
              <p className="mt-2 text-xs text-slate-500">
                CSV descarga el archivo limpio; PDF descarga el reporte.
              </p>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowDialog(false)}
                  className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => handleDownload("csv")}
                  className="rounded-full bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900"
                >
                  CSV
                </button>
                <button
                  type="button"
                  onClick={() => handleDownload("pdf")}
                  className="rounded-full bg-[#F28C18] px-4 py-2 text-sm font-medium text-white hover:bg-[#d9730d]"
                >
                  PDF
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
