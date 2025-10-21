// src/api/pages/Login.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Header from "../../components/Header";
import { requestMagic, verifyMagic, me } from "../../libs/api";

export default function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Deep-link: si viene ?token=... lo verificamos directo
  useEffect(() => {
    const token = params.get("token");
    if (!token) return;
    (async () => {
      try {
        setBusy(true);
        await verifyMagic({ token });
        navigate("/");
      } catch (e: any) {
        setMsg(e.message);
      } finally {
        setBusy(false);
      }
    })();
  }, [params, navigate]);

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    try {
      setBusy(true);
      setMsg(null);
      await requestMagic(email, name);
      setSent(true);
      setMsg("Te enviamos un enlace mágico y un código a tu correo.");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    try {
      setBusy(true);
      setMsg(null);
      await verifyMagic({ email, code });
      navigate("/");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />
      <main className="mx-auto max-w-md px-4 py-10">
        <h1 className="text-2xl font-semibold mb-4">Accede sin contraseña</h1>

        {!sent ? (
          <form onSubmit={onRequest} className="space-y-3">
            <input
              type="email"
              required
              placeholder="tu@email.com"
              className="w-full rounded-md border px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              type="text"
              placeholder="Tu nombre (opcional)"
              className="w-full rounded-md border px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button
              disabled={busy}
              className="w-full rounded-md bg-sky-600 text-white py-2 hover:bg-sky-700 disabled:opacity-60"
            >
              Enviarme enlace / código
            </button>
          </form>
        ) : (
          <form onSubmit={onVerifyCode} className="space-y-3">
            <p className="text-sm text-slate-600">
              Revisa tu correo y haz clic en el enlace mágico. <br />
              O bien, ingresa el código de 6 dígitos:
            </p>
            <input
              type="text"
              placeholder="123456"
              className="w-full rounded-md border px-3 py-2 tracking-widest text-center"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            <button
              disabled={busy}
              className="w-full rounded-md bg-emerald-600 text-white py-2 hover:bg-emerald-700 disabled:opacity-60"
            >
              Verificar código
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setSent(false)}
              className="w-full rounded-md border py-2"
            >
              Cambiar email
            </button>
          </form>
        )}

        {msg && <div className="mt-4 text-sm text-slate-600">{msg}</div>}
      </main>
    </div>
  );
}
