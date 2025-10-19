// src/pages/Plans.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Header from "../../components/Header";
import { me } from "../../libs/api";

type TierId = "free" | "starter" | "pro";

type Tier = {
  id: TierId;
  name: string;
  price: string; // visual
  unit: string;
  highlight?: boolean;
  cta: string;
  quota: string;
  features: { label: string; included: boolean; note?: string }[];
};

export default function PlansPage() {
  const [user, setUser] = useState<{ id: string; email: string; plan?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [params] = useSearchParams();
  const nav = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await me(); // { user: {...} | null }
        if (!cancelled) {
          setUser(r?.user ?? null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const recommended: TierId = "starter";

  const TIERS: Tier[] = [
    {
      id: "free",
      name: "Gratis",
      price: "$0",
      unit: "/siempre",
      cta: "Usar gratis",
      quota: "Hasta 7 procesos sin cuenta",
      features: [
        { label: "Subir CSV, XLSX, XLS, ODS", included: true },
        { label: "Perfil exploratorio HTML", included: true },
        { label: "Dashboard interactivo", included: true },
        { label: "Informe PDF", included: false, note: "Solo con plan" },
        { label: "Descarga de artefactos", included: false, note: "Requiere autenticación" },
        { label: "Historial y reanudación", included: false },
        { label: "Tamaño máx. 20 MB", included: true },
        { label: "Soporte", included: false },
      ],
    },
    {
      id: "starter",
      name: "Starter",
      price: "$9",
      unit: "/mes",
      highlight: true,
      cta: "Elegir Starter",
      quota: "200 procesos/mes",
      features: [
        { label: "Subir CSV, XLSX, XLS, ODS", included: true },
        { label: "Perfil exploratorio HTML", included: true },
        { label: "Dashboard interactivo", included: true },
        { label: "Informe PDF", included: true },
        { label: "Descarga de artefactos (CSV, HTML, PDF)", included: true },
        { label: "Historial (30 días)", included: true },
        { label: "Tamaño máx. 20 MB", included: true },
        { label: "Soporte por email", included: true },
      ],
    },
    {
      id: "pro",
      name: "Pro",
      price: "$29",
      unit: "/mes",
      cta: "Elegir Pro",
      quota: "2.000 procesos/mes",
      features: [
        { label: "Todo en Starter", included: true },
        { label: "Historial (180 días)", included: true },
        { label: "Procesamiento priorizado", included: true },
        { label: "Plantillas de informes personalizadas", included: true },
        { label: "Exportaciones avanzadas", included: true },
        { label: "Soporte prioritario", included: true },
      ],
    },
  ];

  // Si viene ?plan= en la URL, resaltamos esa tarjeta
  const planQuery = (params.get("plan") as TierId | null) ?? null;

  function handleSelect(tier: Tier) {
    if (tier.id === "free") {
      // Sin cuenta: ir a Home para comenzar ya
      nav("/");
      return;
    }
    // Con cuenta: enviamos a login primero (passwordless), luego a checkout
    if (!user) {
      nav(`/login?plan=${tier.id}`);
      return;
    }
    // Usuario autenticado → llevar a checkout (stub de momento)
    nav(`/checkout?plan=${tier.id}`);
  }

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-6xl px-6 md:px-8 py-10 md:py-14">
        <header className="text-center max-w-2xl mx-auto">
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
            Elige tu plan
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Comienza gratis sin cuenta (hasta 7 procesos). Para historial, descargas y mayor capacidad, elige un plan.
          </p>
        </header>

        {/* Cards */}
        <section className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
          {TIERS.map((t) => {
            const isRecommended = t.id === (planQuery ?? recommended);
            // ✅ booleano estricto para que disabled no marque error
            const isCurrent = (user?.plan ?? "").toLowerCase() === t.id;

            return (
              <article
                key={t.id}
                className={[
                  "rounded-2xl border bg-white shadow-sm flex flex-col",
                  isRecommended ? "border-sky-300 ring-2 ring-sky-200" : "border-slate-200",
                ].join(" ")}
              >
                <div className="p-6 md:p-7 flex-1">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">{t.name}</h2>
                    {isRecommended && (
                      <span className="text-[10px] uppercase tracking-wide bg-sky-50 text-sky-700 border border-sky-200 rounded px-2 py-1">
                        Recomendado
                      </span>
                    )}
                    {isCurrent && (
                      <span className="text-[10px] uppercase tracking-wide bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-2 py-1">
                        Tu plan
                      </span>
                    )}
                  </div>

                  <div className="mt-3 flex items-baseline gap-1">
                    <div className="text-3xl font-semibold">{t.price}</div>
                    <div className="text-sm text-slate-500">{t.unit}</div>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">{t.quota}</div>

                  <ul className="mt-5 space-y-2 text-sm">
                    {t.features.map((f, i) => (
                      <li key={i} className="flex items-start gap-2">
                        {f.included ? (
                          <svg viewBox="0 0 24 24" className="w-4 h-4 mt-0.5" stroke="currentColor" fill="none">
                            <path d="M20 6L9 17l-5-5" strokeWidth="1.8" />
                          </svg>
                        ) : (
                          <svg viewBox="0 0 24 24" className="w-4 h-4 mt-0.5" stroke="currentColor" fill="none">
                            <path d="M6 6l12 12M18 6L6 18" strokeWidth="1.8" />
                          </svg>
                        )}
                        <span className={f.included ? "text-slate-700" : "text-slate-400 line-through"}>
                          {f.label}
                          {f.note ? <span className="text-slate-400"> — {f.note}</span> : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="p-6 md:p-7 pt-0">
                  <button
                    onClick={() => handleSelect(t)}
                    className={[
                      "w-full inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
                      t.id === "free"
                        ? "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                        : "bg-sky-600 text-white hover:bg-sky-700",
                      isCurrent ? "opacity-70 cursor-not-allowed" : "",
                    ].join(" ")}
                    disabled={isCurrent}
                  >
                    {isCurrent ? "Plan actual" : t.cta}
                  </button>
                </div>
              </article>
            );
          })}
        </section>

        {!loading && (
          <p className="mt-8 text-center text-xs text-slate-400">
            Los precios son de ejemplo. Ajusta moneda e impuestos según tu región. Puedes cancelar en cualquier momento.
          </p>
        )}
      </main>
    </div>
  );
}
