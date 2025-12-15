// src/api/pages/Login.tsx
import React, { useState } from "react";
import { Link } from "react-router-dom";
import Header from "../../components/Header";
import { useAuth } from "../../context/Authcontext";

export default function Login() {
  const auth = useAuth();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setOkMsg(null);

    if (!email.trim()) {
      setError("Ingresa un correo electrónico.");
      return;
    }

    try {
      setBusy(true);
      await auth.requestLogin(email.trim(), name.trim()); // ✅ backend /api/auth/request
      setOkMsg("Listo. Revisa tu correo: te enviamos un enlace mágico y un código (OTP).");
    } catch (err) {
      setError((err as Error).message || "No se pudo enviar el enlace.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      <Header />

      <main className="pt-32 pb-10 px-6 md:px-10 lg:pl-40">
        <div className="mx-auto max-w-xl">
          <h1 className="text-3xl font-semibold text-slate-900 text-center">
            Iniciar Sesión
          </h1>

          <form onSubmit={onSubmit} className="mt-10 mx-auto w-full max-w-md space-y-5">
            {/* Email */}
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-700">
                Correo electrónico
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@correoejemplo.com"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#1d7fd6] focus:outline-none focus:ring-2 focus:ring-[#1d7fd6]/30"
              />
            </div>

            {/* Nombre opcional */}
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-slate-700">
                Nombre de Usuario (opcional)
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Tu nombre"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#1d7fd6] focus:outline-none focus:ring-2 focus:ring-[#1d7fd6]/30"
              />
            </div>

            <p className="text-sm leading-relaxed text-slate-600">
              Te enviaremos un correo con un enlace y un código de un solo uso para completar el acceso.
            </p>

            {/* OK */}
            {okMsg && (
              <div className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
                {okMsg}
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Botón */}
            <div className="pt-4 flex justify-center">
              <button
                type="submit"
                disabled={busy}
                className="
                  inline-flex items-center justify-center
                  rounded-full
                  bg-[#F28C18] hover:bg-[#d9730d]
                  px-10 py-2.5
                  text-sm font-semibold text-white
                  shadow
                  focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40
                  disabled:opacity-60
                  w-full sm:w-auto
                "
              >
                {busy ? "Enviando…" : "Iniciar Sesión"}
              </button>
            </div>

            {/* Crear cuenta */}
            <p className="pt-2 text-sm text-slate-600 text-center">
              ¿Aún no tienes una cuenta?{" "}
              <Link to="/crear-cuenta" className="font-semibold text-[#1d7fd6] hover:underline">
                Crear Cuenta
              </Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
