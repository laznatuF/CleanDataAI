// src/pages/Settings.tsx
import React, { useState } from "react";
import Header from "../../components/Header";
import { useAuth } from "../../context/Authcontext";

type PlanId = "free" | "standard" | "pro";

export default function Settings() {
  const auth = useAuth();

  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<PlanId>(
    ((auth.user?.plan as PlanId) || "free") as PlanId
  );

  async function ping() {
    setMsg(null);
    setErr(null);
    try {
      const res = await fetch((import.meta.env.VITE_API_BASE ?? "") + "/api/health", {
        credentials: "include",
      });
      const json = await res.json();
      setMsg(`API ok: ${JSON.stringify(json)}`);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function applyPlan() {
    setMsg(null);
    setErr(null);
    if (!auth.user) {
      setErr("Debes iniciar sesión para cambiar el plan.");
      return;
    }
    try {
      setBusy(true);
      await auth.setPlan(plan);
      setMsg(`Plan actualizado a "${plan}".`);
    } catch (e) {
      setErr((e as Error).message || "No se pudo actualizar el plan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      <Header />

      <main className="pt-32 pb-10 px-6 md:px-10 lg:pl-40">
        <div className="max-w-xl mx-auto p-6 space-y-4 bg-white rounded-2xl shadow-sm border border-slate-200">
          <h1 className="text-xl font-semibold">Configuración y diagnóstico</h1>

          <div className="text-sm text-slate-600">
            API Base:{" "}
            <code className="px-1 py-0.5 rounded bg-slate-100">
              {import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"}
            </code>
          </div>

          {/* Sesión */}
          <div className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-800">Cuenta</h2>

            {!auth.user ? (
              <p className="mt-2 text-sm text-slate-600">
                No hay sesión iniciada. Ve a <b>Iniciar Sesión</b>.
              </p>
            ) : (
              <div className="mt-2 space-y-1 text-sm text-slate-700">
                <div>
                  Email: <b>{auth.user.email}</b>
                </div>
                <div>
                  Nombre: <b>{auth.user.name ?? ""}</b>
                </div>
                <div>
                  Plan actual: <b>{auth.user.plan ?? "free"}</b>
                </div>
              </div>
            )}

            {/* Cambiar plan (demo local) */}
            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Cambiar plan (demo local)
              </label>
              <div className="flex gap-2">
                <select
                  value={plan}
                  onChange={(e) => setPlan(e.target.value as PlanId)}
                  className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/30"
                >
                  <option value="free">Gratis</option>
                  <option value="standard">Normal</option>
                  <option value="pro">Pro</option>
                </select>

                <button
                  type="button"
                  onClick={applyPlan}
                  disabled={!auth.user || busy}
                  className="px-4 py-2 rounded-full bg-[#F28C18] text-white text-sm font-semibold shadow hover:bg-[#d9730d] disabled:opacity-60"
                >
                  {busy ? "Aplicando…" : "Aplicar"}
                </button>
              </div>
              <p className="mt-2 text-[11px] text-slate-400">
                *Modo demo: no hay pago real, solo asignación de plan en el backend.
              </p>
            </div>
          </div>

          {/* Diagnóstico */}
          <div className="rounded-lg border border-slate-200 p-4 space-y-3">
            <h2 className="text-sm font-semibold text-slate-800">Diagnóstico</h2>
            <button
              className="px-3 py-2 rounded bg-blue-600 text-white text-sm"
              onClick={ping}
            >
              Probar conectividad
            </button>

            {msg && (
              <div className="p-2 rounded bg-green-50 text-green-700 text-sm">
                {msg}
              </div>
            )}
            {err && (
              <div className="p-2 rounded bg-red-50 text-red-700 text-sm">
                {err}
              </div>
            )}
          </div>

          {/* Logout */}
          {auth.user && (
            <div className="pt-2">
              <button
                type="button"
                onClick={() => auth.logout()}
                className="px-4 py-2 rounded-full border border-slate-300 text-slate-700 text-sm hover:bg-slate-50"
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
