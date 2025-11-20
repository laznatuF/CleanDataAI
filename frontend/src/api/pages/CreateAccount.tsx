// src/pages/CreateAccount.tsx
import React, { useState } from "react";
import { Link } from "react-router-dom";
import Header from "../../components/Header";
// Aquí iría tu función real para crear cuenta / enviar correo de verificación
// import { createAccount } from "../../libs/api";

export default function CreateAccount() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Ingresa un correo electrónico.");
      return;
    }

    try {
      setBusy(true);
      // 👉 Aquí va tu lógica real para crear la cuenta / enviar correo:
      // await createAccount({ email, name });
      console.log("Crear cuenta con", { email, name });
      // Podrías mostrar un toast o redirigir, según tu flujo
    } catch (err) {
      setError(
        (err as Error).message || "No se pudo crear la cuenta. Inténtalo de nuevo."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      {/* Menú lateral + iconos superiores, igual que en Login */}
      <Header />

      {/* Contenido principal (dejamos espacio a la izquierda para el menú) */}
      <main className="pt-32 pb-10 px-6 md:px-10 lg:pl-40">
        <div className="mx-auto max-w-xl">
          {/* Título */}
          <h1 className="text-3xl font-semibold text-slate-900 text-center">
            Crear Cuenta
          </h1>

          {/* Formulario */}
          <form
            onSubmit={onSubmit}
            className="mt-10 mx-auto max-w-md space-y-5"
          >
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
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

            {/* Nombre de usuario */}
            <div>
              <label
                htmlFor="name"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Nombre de Usuario
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Nombre de Usuario"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-[#1d7fd6] focus:outline-none focus:ring-2 focus:ring-[#1d7fd6]/30"
              />
            </div>

            {/* Texto explicativo (como en tu maqueta) */}
            <p className="text-sm leading-relaxed text-slate-600">
              Te enviaremos un correo para verificar y finalizar la creación de
              tu cuenta.
            </p>

            {/* Error si ocurre algo */}
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Botón principal */}
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
                {busy ? "Creando…" : "Crear Cuenta"}
              </button>
            </div>

            {/* Enlace a Iniciar sesión */}
            <p className="pt-2 text-sm text-slate-600 text-center">
              ¿Ya tienes una cuenta?{" "}
              <Link
                to="/login"
                className="font-semibold text-[#1d7fd6] hover:underline"
              >
                Iniciar Sesión
              </Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
