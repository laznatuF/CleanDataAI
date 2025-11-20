// src/pages/Plans.tsx
import React from "react";
import Header from "../../components/Header";

type Feature = {
  label: string;
  included: boolean;
};

type Plan = {
  id: "free" | "standard" | "pro";
  name: string;
  price: string;
  frequency: string;
  processesText: string;
  features: Feature[];
  cta: string;
  recommended?: boolean;
};

const plans: Plan[] = [
  {
    id: "free",
    name: "Gratis",
    price: "$0",
    frequency: "/siempre",
    processesText: "Hasta 7 procesos con cuenta versión gratis.",
    cta: "Usar gratis",
    features: [
      { label: "Subir archivo CSV, XLSX, XLS, ODS", included: true },
      { label: "Perfilado de datos (HTML)", included: true },
      { label: "Dashboard interactivo", included: true },
      { label: "Informe en PDF", included: false },
      { label: "Tamaño máximo 20 MB", included: true },
      {
        label: "Descarga de artefactos (solo la primera vez)",
        included: false,
      },
      { label: "Historial de procesos", included: false },
      { label: "Soporte básico", included: false },
    ],
  },
  {
    id: "standard",
    name: "Estandar",
    price: "$8",
    frequency: "/mes",
    processesText: "Hasta 100 procesos con cuenta versión Estandar.",
    cta: "Elegir Estandar",
    recommended: true,
    features: [
      { label: "Subir archivo CSV, XLSX, XLS, ODS", included: true },
      { label: "Perfilado de datos (HTML)", included: true },
      { label: "Dashboard interactivo", included: true },
      { label: "Informe en PDF", included: true },
      { label: "Tamaño máximo 20 MB", included: true },
      { label: "Descarga de artefactos (ilimitado)", included: true },
      { label: "Historial de procesos (30 días)", included: true },
      { label: "Soporte por email", included: true },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "$20",
    frequency: "/mes",
    processesText: "Procesos ilimitados con cuenta versión Pro.",
    cta: "Elegir Pro",
    features: [
      {
        label: "Todo lo que ofrece la versión Estandar",
        included: true,
      },
      {
        label: "Historial de procesos permanente",
        included: true,
      },
      {
        label: "Plantillas de informes personalizadas",
        included: true,
      },
      { label: "CLI para usuarios especializados", included: true },
      { label: "Soporte prioritario", included: true },
    ],
  },
];

export default function PlansPage() {
  function onChoose(planId: Plan["id"]) {
    // Aquí conectarás con tu flujo real (checkout, cambio de plan, etc.)
    console.log("Elegir plan:", planId);
  }

  return (
    <div className="min-h-screen bg-[#F5F1E4] text-slate-800">
      <Header />

      <main className="pt-32 pb-16 px-6 md:px-10 lg:pl-40">
        <div className="mx-auto max-w-6xl">
          {/* Título y subtítulo */}
          <header className="text-center mb-10">
            <h1 className="text-3xl font-semibold text-slate-900">
              Elige tu plan
            </h1>
            <p className="mt-2 text-sm text-slate-600 max-w-2xl mx-auto">
              Comienza gratis sin cuenta (hasta 7 procesos). Para historial,
              descargas y mayor capacidad, elige un plan de pago.
            </p>
          </header>

          {/* Tarjetas de planes */}
          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => {
              const isRecommended = plan.recommended;

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
                  {/* Encabezado del plan */}
                  <div className="mb-4">
                    <h2 className="text-lg font-semibold text-slate-900">
                      {plan.name}
                    </h2>
                    <div className="mt-2 flex items-baseline gap-1 text-slate-900">
                      <span className="text-3xl font-bold">
                        {plan.price}
                      </span>
                      <span className="text-xs font-medium text-slate-500">
                        {plan.frequency}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {plan.processesText}
                    </p>
                    {isRecommended && (
                      <span className="mt-3 inline-flex items-center rounded-full bg-[#FFF3E6] px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#F28C18]">
                        Recomendado
                      </span>
                    )}
                  </div>

                  {/* Lista de características */}
                  <ul className="mt-3 space-y-2 text-sm flex-1">
                    {plan.features.map((feat, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2"
                      >
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
                            feat.included
                              ? "text-slate-700"
                              : "text-slate-400 line-through"
                          }
                        >
                          {feat.label}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {/* Botón CTA */}
                  <div className="mt-6">
                    <button
                      type="button"
                      onClick={() => onChoose(plan.id)}
                      className="inline-flex w-full items-center justify-center rounded-full bg-[#F28C18] px-6 py-2.5 text-sm font-semibold text-white shadow hover:bg-[#d9730d] focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                    >
                      {plan.cta}
                    </button>
                  </div>
                </section>
              );
            })}
          </div>

          {/* Pie de página pequeño */}
          <p className="mt-10 text-center text-[11px] text-slate-400">
            Los valores y límites son referenciales y pueden ajustarse según la
            versión final del servicio.
          </p>
        </div>
      </main>
    </div>
  );
}
