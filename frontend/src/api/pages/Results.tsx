// src/pages/Results.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { artifactUrl } from "../../api/client";
import { authFetch } from "../../api/http";
import { toaster as toast } from "../../components/UI";

const FILES = [
  { name: "clean_data.csv", label: "CSV limpio" },
  { name: "profile.html", label: "Perfil HTML" },
  { name: "dashboard.html", label: "Dashboard HTML" },
  { name: "report.html", label: "Informe HTML" },
  { name: "report.pdf", label: "Informe PDF" },
  { name: "artifacts.zip", label: "ZIP final" },
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
    <div className="overflow-auto border rounded mt-6">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="p-2 text-left">Timestamp</th>
            <th className="p-2 text-left">Paso</th>
            <th className="p-2 text-left">Mensaje</th>
            <th className="p-2 text-right">Filas</th>
            <th className="p-2 text-right">ms</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t">
              <td className="p-2">{r.timestamp}</td>
              <td className="p-2">{r.step}</td>
              <td className="p-2">{r.message}</td>
              <td className="p-2 text-right">{r.rows_affected ?? ""}</td>
              <td className="p-2 text-right">{r.duration_ms ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ResultsPage() {
  const { id = "" } = useParams();

  const tryOpen = async (name: string) => {
    const url = artifactUrl(id, name);
    try {
      // Chequeo rápido (si el backend no soporta HEAD, puedes omitirlo)
      const r = await authFetch(url, { method: "HEAD" });
      if (!r.ok) throw new Error("No disponible");
      window.open(url, "_blank");
    } catch (e) {
      toast.error(`${name}: ${(e as Error).message}`);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-4">Descargas del proceso {id.slice(0, 8)}…</h1>

      <ul className="space-y-3">
        {FILES.map((f) => (
          <li key={f.name} className="flex justify-between items-center border rounded p-3">
            <span>{f.label}</span>
            <button className="px-3 py-2 border rounded" onClick={() => tryOpen(f.name)}>
              Descargar
            </button>
          </li>
        ))}
      </ul>

      <HistoryTable id={id} />

      <div className="mt-8 flex gap-2">
        <a href={`/status/${id}`} className="px-3 py-2 border rounded">
          Ver estado
        </a>
        <a href="/" className="px-3 py-2 border rounded">
          Nuevo proceso
        </a>
      </div>
    </div>
  );
}
