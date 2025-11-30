// src/api/pages/Help.tsx
import React, { useState } from "react";
import Header from "../../components/Header";
import { sendHelpRequest, type HelpPayload } from "../../libs/api";

type Status = "idle" | "sending" | "ok" | "error";

export default function HelpPage() {
  const [form, setForm] = useState<HelpPayload>({
    name: "",
    email: "",
    category: "ayuda",
    subject: "",
    message: "",
  });

  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");

  function onChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");
    setErrorMsg("");

    try {
      await sendHelpRequest(form);
      setStatus("ok");
      // limpiamos mensaje pero mantenemos nombre/email por comodidad
      setForm((f) => ({ ...f, subject: "", message: "" }));
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err?.message || "Error al enviar el mensaje.");
      setStatus("error");
    }
  }

  const disabled = status === "sending";

  return (
    <div className="min-h-screen bg-[#FDFBF6] text-slate-800">
      <Header />
      <main className="mx-auto w-full max-w-3xl px-6 md:px-8 py-16">
        <section className="rounded-3xl border border-[#E4DCCB] bg-white p-8 shadow-sm">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">
            Ayuda y soporte
          </h1>
          <p className="text-sm text-slate-500 mb-6">
            ¿Tienes una duda, encontraste un problema o quieres sugerir una
            mejora? Completa este formulario y te responderemos por correo.
          </p>

          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Nombre
                </label>
                <input
                  type="text"
                  name="name"
                  value={form.name}
                  onChange={onChange}
                  required
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                  placeholder="Tu nombre"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Correo electrónico
                </label>
                <input
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={onChange}
                  required
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                  placeholder="tucorreo@ejemplo.com"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Tipo de mensaje
                </label>
                <select
                  name="category"
                  value={form.category}
                  onChange={onChange}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                >
                  <option value="ayuda">Pedido de ayuda</option>
                  <option value="queja">Queja</option>
                  <option value="sugerencia">Sugerencia</option>
                  <option value="comentario">Comentario</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Asunto (opcional)
                </label>
                <input
                  type="text"
                  name="subject"
                  value={form.subject ?? ""}
                  onChange={onChange}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                  placeholder="Ej: Problema al descargar el dashboard"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Mensaje
              </label>
              <textarea
                name="message"
                value={form.message}
                onChange={onChange}
                required
                rows={6}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40 resize-y"
                placeholder="Describe tu problema, sugerencia o comentario con el mayor detalle posible."
              />
            </div>

            {status === "ok" && (
              <p className="text-xs text-emerald-600">
                ✅ Mensaje enviado correctamente. Te responderemos al correo indicado.
              </p>
            )}
            {status === "error" && (
              <p className="text-xs text-red-600">❌ {errorMsg}</p>
            )}

            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                type="submit"
                disabled={disabled}
                className="inline-flex items-center rounded-full bg-[#F28C18] px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === "sending" ? "Enviando..." : "Enviar mensaje"}
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
