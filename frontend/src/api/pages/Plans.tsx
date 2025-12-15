// src/pages/Plans.tsx
import React from "react";
import { useNavigate } from "react-router-dom";
import Header from "../../components/Header";
import { useAuth } from "../../context/Authcontext";

type Feature = {
  label: string;
  included: boolean;
};

type Plan = {
  id: "free" | "standard" | "pro";
  name: string;
  priceUsd: number;
  frequency: string;
  processesText: string;
  features: Feature[];
  cta: string;
  recommended?: boolean;
};

/* ===================== MONEDAS ===================== */

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

/* ===================== PLANES ===================== */

const plans: Plan[] = [
  {
    id: "free",
    name: "Gratis",
    priceUsd: 0,
    frequency: "/siempre",
    processesText: "Hasta 7 procesos con cuenta versión gratis.",
    cta: "Usar gratis",
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
    cta: "Elegir Normal",
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
    cta: "Elegir Pro",
    features: [
      { label: "Todo lo que ofrece la versión Estándar", included: true },
      { label: "Descarga de artefactos en PDF y otros formatos (ilimitado)", included: true },
      { label: "Reporte narrativo inteligente", included: true },
    ],
  },
];

/* ===================== COMPONENTE ===================== */

export default function PlansPage() {
  const auth = useAuth();
  const nav = useNavigate();

  // ✅ Siempre iniciar en CLP (puedes cambiar a detectInitialCurrency() si quieres)
  const [currency, setCurrency] = React.useState<Currency>("CLP");
  const [busyPlan, setBusyPlan] = React.useState<Plan["id"] | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [ok, setOk] = React.useState<string | null>(null);

  async function onChoose(planId: Plan["id"]) {
    setErr(null);
    setOk(null);

    // Si no hay sesión: lo mandamos a crear cuenta preseleccionando plan
    if (!auth.user) {
      nav(`/crear-cuenta?plan=${encodeURIComponent(planId)}`);
      return;
    }

    // Si hay sesión: cambiamos el plan (demo local)
    try {
      setBusyPlan(planId);
      await auth.setPlan(planId); // ✅ backend /api/auth/set-plan
      setOk(`Plan actualizado a "${planId}".`);
      nav("/settings");
    } catch (e) {
      setErr((e as Error).message || "No se pudo actualizar el plan.");
    } finally {
      setBusyPlan(null);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      <Header />

      <main className="pt-32 pb-16 px-6 md:px-10 lg:pl-40">
        <div className="mx-auto max-w-6xl">
          <header className="text-center mb-6">
            <h1 className="text-3xl font-semibold text-slate-900">Elige tu plan</h1>
            <p className="mt-2 text-sm text-slate-600 max-w-2xl mx-auto">
              Comienza sin cuenta y prueba el flujo completo del sistema (hasta 7 procesos).
              Para más procesos, elige un plan según tu preferencia.
            </p>

            {/* Estado sesión */}
            {auth.user && (
              <p className="mt-3 text-xs text-slate-500">
                Sesión: <b>{auth.user.email}</b> — Plan actual:{" "}
                <b>{auth.user.plan ?? "free"}</b>
              </p>
            )}

            {/* Selector de moneda */}
            <div className="mt-4 flex flex-col items-center gap-2 md:flex-row md:justify-center">
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

            {ok && (
              <div className="mt-4 mx-auto max-w-xl rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
                {ok}
              </div>
            )}
            {err && (
              <div className="mt-4 mx-auto max-w-xl rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {err}
              </div>
            )}
          </header>

          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => {
              const isRecommended = plan.recommended;
              const displayPrice = formatPrice(plan.priceUsd, currency);
              const isBusy = busyPlan === plan.id;

              return (
                <section
                  key={plan.id}
                  className={[
                    "flex flex-col rounded-3xl bg-white shadow-sm px-6 py-7 md:px-8 md:py-8",
                    "border",
                    isRecommended
                      ? "border-[#F28C18] ring-2 ring-[#F28C18]/30"
                      : "border-[#F28C18]/40",
                  ].join(" ")}
                >
                  <div className="mb-4">
                    <h2 className="text-lg font-semibold text-slate-900">{plan.name}</h2>
                    <div className="mt-2 flex items-baseline gap-1 text-slate-900">
                      <span className="text-2xl font-bold">{displayPrice}</span>
                      <span className="text-xs font-medium text-slate-500">{plan.frequency}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{plan.processesText}</p>
                    {isRecommended && (
                      <span className="mt-3 inline-flex items-center rounded-full bg-[#FFF3E6] px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#F28C18]">
                        Recomendado
                      </span>
                    )}
                  </div>

                  <ul className="mt-3 space-y-2 text-sm flex-1">
                    {plan.features.map((feat, idx) => (
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
                    <button
                      type="button"
                      onClick={() => onChoose(plan.id)}
                      disabled={isBusy}
                      className="inline-flex w-full items-center justify-center rounded-full bg-[#F28C18] px-6 py-2.5 text-sm font-semibold text-white shadow hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40 disabled:opacity-60"
                    >
                      {isBusy ? "Aplicando…" : plan.cta}
                    </button>
                  </div>

                  <p className="mt-3 text-[11px] text-slate-400 text-center">
                    *Demo local: sin pasarela de pago, solo asignación de plan.
                  </p>
                </section>
              );
            })}
          </div>

          <p className="mt-10 text-center text-[11px] text-slate-400">Planes</p>
        </div>
      </main>
    </div>
  );
}
