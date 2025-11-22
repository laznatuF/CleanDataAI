// src/api/pages/CsvPreview.tsx
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../../components/Header";

function useQuery() {
  const location = useLocation();
  return new URLSearchParams(location.search);
}

function CsvPreview() {
  const query = useQuery();
  const navigate = useNavigate();
  const url = query.get("url"); // viene desde Status.tsx

  const [rows, setRows] = useState<string[][] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setError("No se indicó el archivo CSV a visualizar.");
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);

        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) {
          throw new Error("No se pudo cargar el CSV limpio.");
        }

        const text = await res.text();
        if (cancelled) return;

        const lines = text.trim().split(/\r?\n/);

        const data = lines.map((line) =>
          // separa por comas respetando comillas
          line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
        );

        setRows(data);
      } catch (e) {
        if (!cancelled) {
          setError((e as Error).message);
          setRows(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [url]);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            Archivo limpio (CSV)
          </h1>

          <div className="flex gap-2">
            {url && (
              <a
                href={url}
                download
                className="rounded-full border border-[#F28C18]/50 px-4 py-2 text-sm font-medium text-[#F28C18]"
              >
                Descargar CSV
              </a>
            )}
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="rounded-full border px-4 py-2 text-sm text-slate-600"
            >
              Volver
            </button>
          </div>
        </div>

        {loading && (
          <p className="text-sm text-slate-500">Cargando CSV…</p>
        )}

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}

        {rows && (
          <div className="mt-4 max-h-[70vh] overflow-auto rounded-xl border bg-white">
            <table className="min-w-full border-collapse text-xs">
              <tbody>
                {rows.map((row, i) => (
                  <tr
                    key={i}
                    className={i === 0 ? "bg-slate-50 font-semibold" : ""}
                  >
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        className="border px-3 py-1 whitespace-nowrap"
                      >
                        {/* quita comillas al principio/fin */}
                        {cell.replace(/^"|"$/g, "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-3 py-2 text-[10px] text-slate-500">
              Se muestra el CSV completo. Usa la barra de scroll para explorar filas y columnas.
            </p>
          </div>
        )}
      </main>
    </>
  );
}

export default CsvPreview;
