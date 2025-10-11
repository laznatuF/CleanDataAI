// src/pages/Settings.tsx
import React, { useState } from 'react';

export default function Settings() {
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function ping() {
    setMsg(null); setErr(null);
    try {
      const res = await fetch('/api/health');
      const json = await res.json();
      setMsg(`API ok: ${JSON.stringify(json)}`);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold">Configuración y diagnóstico</h1>
      <div className="text-sm text-gray-600">
        Base URL: <code>{import.meta.env.VITE_API_BASE_URL ?? '(proxy /api)'}</code>
      </div>
      <button
        className="px-3 py-2 rounded bg-blue-600 text-white"
        onClick={ping}
      >
        Probar conectividad
      </button>
      {msg && <div className="p-2 rounded bg-green-50 text-green-700 text-sm">{msg}</div>}
      {err && <div className="p-2 rounded bg-red-50 text-red-700 text-sm">{err}</div>}
    </div>
  );
}

