// src/pages/LoginToken.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import Header from "../../components/Header";
import { verifyMagic } from "../../libs/api";

export default function LoginToken() {
  const nav = useNavigate();
  const [qp] = useSearchParams();
  const token = qp.get("token") || "";
  const redirectTo = qp.get("redirect") || "/";
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (!token) throw new Error("Falta token en la URL.");
        await verifyMagic({ token });
        if (!cancelled) nav(redirectTo);
      } catch (e) {
        if (!cancelled) setErr((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [token, redirectTo, nav]);

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />
      <main className="mx-auto w-full max-w-[720px] px-6 md:px-8 py-10">
        {!err ? (
          <div className="text-center text-slate-600">Validando enlace mágico…</div>
        ) : (
          <div className="max-w-lg mx-auto space-y-4">
            <div className="rounded-md bg-red-50 px-3 py-2 text-red-700">{err}</div>
            <Link to="/login" className="inline-block text-sky-600 hover:underline">
              Volver a iniciar sesión
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
