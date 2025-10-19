// src/pages/MyRuns.tsx
import React, { useMemo } from "react";
import Header from "../../components/Header";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/Authcontext";

type LocalRun = { id: string; created_at?: string; filename?: string };

export default function MyRunsPage() {
  const { user } = useAuth();

  const runs = useMemo<LocalRun[]>(() => {
    try {
      const raw = localStorage.getItem("process_ids") || "[]";
      return JSON.parse(raw);
    } catch { return []; }
  }, []);

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />
      <main className="mx-auto max-w-4xl px-4 sm:px-5 py-10">
        <h1 className="text-2xl font-semibold">Mis procesos</h1>

        {!user && (
          <div className="mt-3 rounded-md bg-yellow-50 px-3 py-2 text-yellow-800 text-sm">
            Para ver los detalles y artefactos privados debes <Link className="underline" to="/login">iniciar sesión</Link>.
          </div>
        )}

        <div className="mt-6 border rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2">ID</th>
                <th className="text-left px-3 py-2">Archivo</th>
                <th className="text-left px-3 py-2">Fecha</th>
                <th className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && (
                <tr><td className="px-3 py-4 text-slate-500" colSpan={4}>Aún no hay procesos guardados.</td></tr>
              )}
              {runs.map(r => (
                <tr key={r.id} className="border-t">
                  <td className="px-3 py-2 font-mono">{r.id}</td>
                  <td className="px-3 py-2">{r.filename || "—"}</td>
                  <td className="px-3 py-2">{r.created_at || "—"}</td>
                  <td className="px-3 py-2">
                    <Link className="text-sky-700 hover:underline" to={`/status/${r.id}`}>Ver estado</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
