// src/pages/ProfilePreview.tsx
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

  // url = Enlace al HTML del perfilado (usado en el iframe y descarga HTML)
  const url = query.get("url");
  // pdf = Enlace al PDF generado
  const pdf = query.get("pdf");

  const [showDialog, setShowDialog] = useState(false);

  // Añade el parámetro ?download=1 o &download=1 para forzar la descarga en el backend
  const addDownloadParam = (base: string): string => {
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

  // Acepta "html" o "pdf" y descarga SOLO el tipo correspondiente
  const handleDownload = (kind: "html" | "pdf") => {
    let target: string | null = null;

    if (kind === "html") {
      // Para HTML usamos siempre la URL del reporte web
      target = url;
    } else {
      // Para PDF usamos únicamente el enlace PDF
      target = pdf;
    }

    if (!target) {
      alert(
        kind === "html"
          ? "No se encontró un enlace HTML para descargar este perfilado."
          : "No se encontró un enlace PDF para descargar este perfilado."
      );
      return;
    }

    const finalUrl = addDownloadParam(target);
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
            {/* Iframe con el reporte HTML */}
            <div className="mt-4 max-h-[70vh] rounded-2xl border bg-white overflow-auto">
              <iframe
                src={url}
                title="Reporte de perfilado"
                className="w-full h-[70vh] border-0"
              />
            </div>

            {/* Botones inferiores */}
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

        {/* Diálogo de selección HTML / PDF */}
        {showDialog && (
          <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
              <h2 className="text-base font-semibold text-slate-900">
                ¿En qué formato quieres descargar el perfilado?
              </h2>
              <p className="mt-2 text-xs text-slate-500">
                Elige HTML para interactividad o PDF para imprimir.
              </p>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowDialog(false)}
                  className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>

                {/* BOTÓN HTML */}
                <button
                  type="button"
                  onClick={() => handleDownload("html")}
                  className="rounded-full bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900"
                >
                  HTML
                </button>

                {/* BOTÓN PDF */}
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
