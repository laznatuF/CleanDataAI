// src/pages/Results.tsx
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom"; 
import { artifactUrl } from "../../api/client";
import { authFetch } from "../../api/http";
import { toaster as toast } from "../../components/UI";

// 1. AQUÍ AGREGAMOS EL "REPORTE NARRATIVO" A LA LISTA
const FILES = [
  { name: "reporte_narrativo.html", label: "📄 Reporte Narrativo (AI) - ¡NUEVO!" },
  { name: "clean_data.csv", label: "CSV limpio" },
  { name: "profile.html", label: "Perfil de Datos (HTML)" },
  { name: "reporte_integrado.html", label: "Informe Técnico (HTML)" },
  { name: "reporte_integrado.pdf", label: "Informe Técnico (PDF)" },
  { name: "artifacts.zip", label: "ZIP Completo" },
  { name: "history.json", label: "Bitácora (JSON)" },
];

type Hist = {
  timestamp: string;
  step: string;
  level?: string;
  message: string;
  rows_affected?: number;
  duration_ms?: number;
};

function HistoryTable({ id }: { id: string }) {
  const [rows, setRows] = useState<Hist[]>([]);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const r = await authFetch(artifactUrl(id, "history.json"));
        if (!r.ok) throw new Error("No se pudo obtener la bitácora");
        const data = await r.json();
        setRows(Array.isArray(data) ? data : data?.events || []);
      } catch (e) {
        setErr((e as Error).message);
      }
    })();
  }, [id]);

  if (err) return <div className="text-sm text-red-600 mt-4">{err}</div>;
  if (!rows.length) return <div className="text-sm text-gray-500 mt-4">Sin registros…</div>;

  return (
    <div className="overflow-auto border rounded mt-4 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="p-2 text-left text-gray-600 font-medium">Timestamp</th>
            <th className="p-2 text-left text-gray-600 font-medium">Paso</th>
            <th className="p-2 text-left text-gray-600 font-medium">Mensaje</th>
            <th className="p-2 text-right text-gray-600 font-medium">Filas</th>
            <th className="p-2 text-right text-gray-600 font-medium">ms</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t hover:bg-gray-50">
              <td className="p-2 text-gray-500 whitespace-nowrap">{r.timestamp.split("T")[1]?.slice(0,8)}</td>
              <td className="p-2 font-medium text-gray-700">{r.step}</td>
              <td className="p-2 text-gray-600">{r.message}</td>
              <td className="p-2 text-right text-gray-500">{r.rows_affected ?? "-"}</td>
              <td className="p-2 text-right text-gray-500">{r.duration_ms ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ResultsPage() {
  const { id = "" } = useParams();

  // URL para el dashboard visual
  const dashboardSrc = artifactUrl(id, "dashboard.html");

  const tryOpen = async (name: string) => {
    const url = artifactUrl(id, name);
    try {
      const r = await authFetch(url, { method: "HEAD" });
      if (!r.ok) throw new Error("No disponible (¿Ya generaste el dashboard?)");
      window.open(url, "_blank");
    } catch (e) {
      toast.error(`${name}: ${(e as Error).message}`);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      
      {/* HEADER */}
      <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm shrink-0">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            Resultados del Proceso
            <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-1 rounded-full">{id.slice(0, 8)}</span>
          </h1>
        </div>
        <div className="flex gap-3">
           
           {/* 2. AQUÍ ESTÁ EL BOTÓN DESTACADO NUEVO */}
           <button 
             onClick={() => tryOpen("reporte_narrativo.html")}
             className="px-4 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 font-medium transition-colors shadow-sm flex items-center gap-2"
           >
             📄 Ver Reporte Narrativo
           </button>

           <a 
             href={artifactUrl(id, "dataset_limpio.csv")} 
             className="px-4 py-2 text-sm border border-blue-200 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 font-medium transition-colors"
             download
           >
             Descargar CSV
           </a>
           <Link to="/" className="px-4 py-2 text-sm border border-gray-300 text-gray-700 rounded hover:bg-gray-100 transition-colors">
             Nuevo Proceso
           </Link>
        </div>
      </header>

      {/* MAIN */}
      <main className="flex-1 overflow-y-auto p-6">
        
        {/* A. Dashboard Visual */}
        <section className="mb-8">
          <div className="w-full h-[850px] bg-white rounded-xl shadow-lg overflow-hidden border border-gray-200 relative">
             <div className="absolute top-0 right-0 bg-white/80 backdrop-blur px-2 py-1 text-xs text-gray-500 z-10 border-b border-l rounded-bl">
                Dashboard Interactivo
             </div>
            <iframe
              src={dashboardSrc}
              title="Dashboard Visual"
              width="100%"
              height="100%"
              className="block"
              style={{ border: "none" }}
            />
          </div>
        </section>

        {/* B. Grid Inferior */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Descargas */}
          <section className="lg:col-span-1">
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Descargas Disponibles</h2>
            <ul className="space-y-2 bg-white p-4 rounded-lg shadow-sm border border-gray-200">
              {FILES.map((f) => (
                <li key={f.name} className="flex justify-between items-center py-2 border-b last:border-0 border-gray-100">
                  <span className="text-sm text-gray-700 font-medium">{f.label}</span>
                  <button 
                    className="text-xs font-bold text-blue-600 hover:text-blue-800 hover:underline px-2 py-1 bg-blue-50 hover:bg-blue-100 rounded" 
                    onClick={() => tryOpen(f.name)}
                  >
                    Abrir
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-4 text-center">
              <a href={`/status/${id}`} className="text-sm text-gray-500 hover:text-gray-800 underline">
                Ver JSON de estado técnico
              </a>
            </div>
          </section>

          {/* Historial */}
          <section className="lg:col-span-2">
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Bitácora de Ejecución</h2>
            <HistoryTable id={id} />
          </section>

        </div>
      </main>
    </div>
  );
}