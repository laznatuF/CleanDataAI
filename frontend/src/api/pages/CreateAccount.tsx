// src/api/pages/CreateAccount.tsx
import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Header from "../../components/Header";
import { useAuth } from "../../context/Authcontext";

/* ===================== TIPOS ===================== */

type Feature = {
  label: string;
  included: boolean;
};

type PlanId = "free" | "standard" | "pro";

type Plan = {
  id: PlanId;
  name: string;
  priceUsd: number;
  frequency: string;
  processesText: string;
  features: Feature[];
  recommended?: boolean;
};

/* ===================== NORMALIZACIÓN DE PLAN DESDE URL ===================== */

function normalizePlan(p: string | null): PlanId {
  const raw = (p || "").trim().toLowerCase();
  if (raw === "pro") return "pro";
  if (raw === "standard" || raw === "normal" || raw === "estandar" || raw === "estándar")
    return "standard";
  if (raw === "free" || raw === "gratis" || raw === "gratuito") return "free";
  return "standard";
}

/* ===================== MONEDAS (MISMO ENFOQUE QUE /planes) ===================== */

type Currency =
  | "USD"
  | "EUR"
  | "MXN"
  | "COP"
  | "ARS"
  | "CLP"
  | "PEN"
  | "BOB"
  | "PYG"
  | "UYU"
  | "VES"
  | "GTQ"
  | "HNL"
  | "NIO"
  | "CRC"
  | "DOP";

type CurrencyConfig = {
  code: string;
  locale: string;
  rate: number;
  decimals: number;
  label: string;
};

const CURRENCIES: Record<Currency, CurrencyConfig> = {
  USD: { code: "USD", locale: "en-US", rate: 1, decimals: 2, label: "🇺🇸 USD – Dólar estadounidense" },
  EUR: { code: "EUR", locale: "es-ES", rate: 0.92, decimals: 2, label: "🇪🇸 EUR – Euro (España)" },
  MXN: { code: "MXN", locale: "es-MX", rate: 18, decimals: 2, label: "🇲🇽 MXN – Peso mexicano" },
  COP: { code: "COP", locale: "es-CO", rate: 3900, decimals: 0, label: "🇨🇴 COP – Peso colombiano" },
  ARS: { code: "ARS", locale: "es-AR", rate: 950, decimals: 0, label: "🇦🇷 ARS – Peso argentino" },
  CLP: { code: "CLP", locale: "es-CL", rate: 900, decimals: 0, label: "🇨🇱 CLP – Peso chileno" },
  PEN: { code: "PEN", locale: "es-PE", rate: 3.8, decimals: 2, label: "🇵🇪 PEN – Sol peruano" },
  BOB: { code: "BOB", locale: "es-BO", rate: 6.9, decimals: 2, label: "🇧🇴 BOB – Boliviano boliviano" },
  PYG: { code: "PYG", locale: "es-PY", rate: 7400, decimals: 0, label: "🇵🇾 PYG – Guaraní paraguayo" },
  UYU: { code: "UYU", locale: "es-UY", rate: 42, decimals: 2, label: "🇺🇾 UYU – Peso uruguayo" },
  VES: { code: "VES", locale: "es-VE", rate: 40, decimals: 2, label: "🇻🇪 VES – Bolívar venezolano" },
  GTQ: { code: "GTQ", locale: "es-GT", rate: 7.8, decimals: 2, label: "🇬🇹 GTQ – Quetzal guatemalteco" },
  HNL: { code: "HNL", locale: "es-HN", rate: 25, decimals: 2, label: "🇭🇳 HNL – Lempira hondureño" },
  NIO: { code: "NIO", locale: "es-NI", rate: 37, decimals: 2, label: "🇳🇮 NIO – Córdoba nicaragüense" },
  CRC: { code: "CRC", locale: "es-CR", rate: 520, decimals: 0, label: "🇨🇷 CRC – Colón costarricense" },
  DOP: { code: "DOP", locale: "es-DO", rate: 60, decimals: 2, label: "🇩🇴 DOP – Peso dominicano" },
};

function formatPrice(priceUsd: number, currency: Currency): string {
  const cfg = CURRENCIES[currency];
  const amount = priceUsd * cfg.rate;

  return new Intl.NumberFormat(cfg.locale, {
    style: "currency",
    currency: cfg.code,
    minimumFractionDigits: cfg.decimals === 0 ? 0 : 2,
    maximumFractionDigits: cfg.decimals,
  }).format(amount);
}

/* ===================== PLANES (IGUAL QUE /planes) ===================== */

const plans: Plan[] = [
  {
    id: "free",
    name: "Gratis",
    priceUsd: 0,
    frequency: "/siempre",
    processesText: "Hasta 7 procesos con cuenta versión gratis.",
    features: [
      { label: "Subir archivo CSV, XLSX, XLS, ODS", included: true },
      { label: "Perfilado de datos (HTML)", included: true },
      { label: "Visualización de dashboard", included: true },
      { label: "Tamaño máximo 20 MB", included: true },
      { label: "Descarga de CSV limpio", included: true },
      { label: "Visualización de detalle de limpieza", included: false },
      { label: "Descarga de artefactos en PDF y otros formatos", included: false },
      { label: "Soporte por correo", included: false },
      { label: "Reporte narrativo inteligente", included: false },
    ],
  },
  {
    id: "standard",
    name: "Normal",
    priceUsd: 8,
    frequency: "/mes",
    processesText: "Hasta 100 procesos con cuenta versión Estándar.",
    recommended: true,
    features: [
      { label: "Subir archivo CSV, XLSX, XLS, ODS", included: true },
      { label: "Perfilado de datos (HTML)", included: true },
      { label: "Visualización de dashboard", included: true },
      { label: "Tamaño máximo 20 MB", included: true },
      { label: "Descarga de CSV limpio", included: true },
      { label: "Visualización de detalle de limpieza", included: true },
      { label: "Descarga de artefactos en PDF y otros formatos (limitado)", included: true },
      { label: "Soporte por correo prioritario", included: true },
      { label: "Reporte narrativo inteligente", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    priceUsd: 20,
    frequency: "/mes",
    processesText: "Procesos ilimitados con cuenta versión Pro.",
    features: [
      { label: "Todo lo que ofrece la versión Estándar", included: true },
      { label: "Descarga de artefactos en PDF y otros formatos (ilimitado)", included: true },
      { label: "Reporte narrativo inteligente", included: true },
    ],
  },
];

/* ===================== COMPONENTE ===================== */

export default function CreateAccount() {
  const auth = useAuth();
  const nav = useNavigate();
  const [qp] = useSearchParams();

  const initialPlan = useMemo<PlanId>(() => normalizePlan(qp.get("plan")), [qp]);

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [plan, setPlan] = useState<PlanId>(initialPlan);

  // moneda para visualizar precios
  const [currency, setCurrency] = useState<Currency>("CLP");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPlanName =
    plans.find((p) => p.id === plan)?.name ?? plan;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Ingresa un correo electrónico.");
      return;
    }

    try {
      setBusy(true);
      await auth.register(email.trim(), name.trim(), plan);
      nav("/settings");
    } catch (err) {
      setError((err as Error).message || "No se pudo crear la cuenta. Inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      <Header />

      <main className="pt-32 pb-10 px-6 md:px-10 lg:pl-40">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-3xl font-semibold text-slate-900 text-center">
            Crear Cuenta
          </h1>

          {/* ✅ TODO dentro del mismo <form> para mantener el botón abajo */}
          <form onSubmit={onSubmit} className="mt-10 space-y-10">
            {/* ===================== FORM ARRIBA (EMAIL + NOMBRE) ===================== */}
            <div className="mx-auto max-w-md space-y-5">
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

              {/* Nombre */}
              <div>
                <label htmlFor="name" className="mb-1 block text-sm font-medium text-slate-700">
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
            </div>

            {/* ===================== MONEDA (DEBAJO DEL FORM, ARRIBA DE PLANES) ===================== */}
            <div className="flex flex-col items-center gap-2 md:flex-row md:justify-center">
              <span className="text-xs text-slate-500">Moneda</span>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as Currency)}
                className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
              >
                {Object.entries(CURRENCIES).map(([code, cfg]) => (
                  <option key={code} value={code}>
                    {cfg.label}
                  </option>
                ))}
              </select>
            </div>

            {/* ===================== PLANES (TARJETAS) ===================== */}
            <section>
              <div className="text-sm font-medium text-slate-700 mb-3 text-center">
                Elige tu plan
              </div>

              <div className="grid gap-6 md:grid-cols-3">
                {plans.map((p) => {
                  const selected = plan === p.id;
                  const displayPrice = formatPrice(p.priceUsd, currency);

                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setPlan(p.id)}
                      aria-pressed={selected}
                      className={[
                        "text-left flex flex-col rounded-3xl bg-white shadow-sm px-6 py-7 border transition",
                        selected
                          ? "border-[#F28C18] ring-2 ring-[#F28C18]/30"
                          : "border-[#F28C18]/40 hover:border-[#F28C18]",
                      ].join(" ")}
                    >
                      <div className="mb-4">
                        <div className="flex items-start justify-between gap-3">
                          <h3 className="text-lg font-semibold text-slate-900">{p.name}</h3>
                          {p.recommended && (
                            <span className="inline-flex items-center rounded-full bg-[#FFF3E6] px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#F28C18]">
                              Recomendado
                            </span>
                          )}
                        </div>

                        <div className="mt-2 flex items-baseline gap-1 text-slate-900">
                          <span className="text-2xl font-bold">{displayPrice}</span>
                          <span className="text-xs font-medium text-slate-500">{p.frequency}</span>
                        </div>

                        <p className="mt-1 text-xs text-slate-500">{p.processesText}</p>
                      </div>

                      <ul className="mt-3 space-y-2 text-sm flex-1">
                        {p.features.map((feat, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span
                              className={[
                                "mt-[3px] flex h-4 w-4 items-center justify-center rounded-full border text-[10px]",
                                feat.included
                                  ? "border-[#F28C18] text-[#F28C18] bg-[#FFF3E6]"
                                  : "border-slate-300 text-slate-300 bg-white",
                              ].join(" ")}
                            >
                              {feat.included ? "✓" : "✕"}
                            </span>
                            <span
                              className={
                                feat.included ? "text-slate-700" : "text-slate-400 line-through"
                              }
                            >
                              {feat.label}
                            </span>
                          </li>
                        ))}
                      </ul>

                      <div className="mt-6">
                        <div
                          className={[
                            "w-full rounded-full px-6 py-2.5 text-center text-sm font-semibold",
                            selected ? "bg-[#F28C18] text-white" : "bg-slate-100 text-slate-600",
                          ].join(" ")}
                        >
                          {selected ? "Seleccionado" : "Seleccionar"}
                        </div>
                      </div>

                      <p className="mt-3 text-[11px] text-slate-400 text-center">
                        *Demo local: sin pasarela de pago, solo asignación de plan.
                      </p>
                    </button>
                  );
                })}
              </div>

              <p className="mt-3 text-center text-xs text-slate-500">
                Plan seleccionado: <b className="text-slate-700">{selectedPlanName}</b>
              </p>
            </section>

            {/* ===================== NOTA + ERRORES + BOTÓN ABAJO ===================== */}
            <div className="mx-auto max-w-md space-y-4">
              <p className="text-sm leading-relaxed text-slate-600">
                En esta demo, el sistema crea tu usuario y asigna tu plan de forma local (sin cobro).
              </p>

              {error && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="pt-2 flex justify-center">
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

              <p className="pt-2 text-sm text-slate-600 text-center">
                ¿Ya tienes una cuenta?{" "}
                <Link to="/login" className="font-semibold text-[#1d7fd6] hover:underline">
                  Iniciar Sesión
                </Link>
              </p>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
