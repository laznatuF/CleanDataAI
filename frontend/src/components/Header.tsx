// src/components/Header.tsx
import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { me, logout as apiLogout } from "../libs/api";

type SessionUser = {
  id: string;
  email: string;
  name?: string;
  plan?: string;
} | null;

type MenuItem = {
  href: string;
  label: string;
  locked?: boolean;
};

export default function Header() {
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<SessionUser>(null);
  const loc = useLocation();
  const nav = useNavigate();

  // Carga / refresca la sesión (cookie HttpOnly)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await me();
        if (!cancelled) setUser(r?.user ?? null);
      } catch {
        if (!cancelled) setUser(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loc.pathname]);

  async function onLogout() {
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setOpen(false);
      nav("/");
    }
  }

  const isActive = (href: string) =>
    loc.pathname === href || (href !== "/" && loc.pathname.startsWith(href));

  // Items del menú lateral
  const guestItems: MenuItem[] = [
    { href: "/", label: "Principal" },
    { href: "/login", label: "Iniciar sesión" },
    { href: "/crear-cuenta", label: "Crear cuenta" },
    { href: "/planes", label: "Planes" },
    { href: "/mis-procesos", label: "Mis procesos", locked: true },
    { href: "/about", label: "Acerca de" },
    { href: "/help", label: "Ayuda" },
  ];

  const userItems: MenuItem[] = [
    { href: "/", label: "Principal" },
    { href: "/mis-procesos", label: "Mis procesos", locked: false },
    { href: "/planes", label: "Planes" },
    { href: "/about", label: "Acerca de" },
    { href: "/help", label: "Ayuda" },
  ];

  const menuItems: MenuItem[] = user ? userItems : guestItems;

  return (
    <>
      {/* Tarjeta flotante con logo + hamburguesa */}
      <div className="fixed top-4 left-4 z-40">
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-md">
          <Link
            to="/"
            className="flex items-center justify-center"
            aria-label="Ir al inicio de CleanDataAI"
          >
            {/* Logo más grande para que se lea bien el texto */}
            <img
              src="/brand/cleandataai-logo.png"
              alt=""
              className="h-10 w-auto md:h-11"
              loading="eager"
              decoding="async"
            />
          </Link>

          <button
            type="button"
            aria-label="Menú principal"
            aria-expanded={open}
            onClick={() => setOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 bg-[#FDFBF6] text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
          >
            {/* ícono hamburguesa */}
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5"
              stroke="currentColor"
              fill="none"
            >
              <path strokeWidth={1.8} d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Menú lateral / drawer */}
      {open && (
        <div className="fixed inset-0 z-30">
          {/* fondo semitransparente */}
          <div
            className="absolute inset-0 bg-black/10"
            onClick={() => setOpen(false)}
          />
          <aside className="relative z-40 flex h-full w-[260px] flex-col border-r border-slate-200 bg-white pt-16 pb-6 shadow-xl">
            {/* botón cerrar */}
            <button
              type="button"
              aria-label="Cerrar menú"
              onClick={() => setOpen(false)}
              className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
            >
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                stroke="currentColor"
                fill="none"
              >
                <path strokeWidth={1.8} d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>

            {/* Logo pequeño arriba del menú */}
            <div className="px-4 pb-4">
              <img
                src="/brand/cleandataai-logo-full.png"
                alt="CleanDataAI"
                className="h-8 w-auto"
              />
            </div>

            <nav className="mt-2 flex-1 space-y-1 px-2 text-sm">
              {menuItems.map((item) => {
                const active = isActive(item.href);
                const locked = item.locked;

                const base =
                  "flex items-center justify-between rounded-md px-3 py-2 transition-colors";
                const colors = locked
                  ? "text-slate-400 cursor-not-allowed pointer-events-none bg-slate-50"
                  : active
                  ? "bg-[#FFF3E6] text-slate-900"
                  : "text-slate-700 hover:bg-slate-50";

                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={() => !locked && setOpen(false)}
                    className={`${base} ${colors}`}
                  >
                    <span>{item.label}</span>
                    {locked && (
                      <span className="ml-2 inline-flex items-center">
                        {/* icono candado */}
                        <svg
                          viewBox="0 0 24 24"
                          className="h-4 w-4 text-slate-400"
                          stroke="currentColor"
                          fill="none"
                        >
                          <rect
                            x="5"
                            y="10"
                            width="14"
                            height="9"
                            rx="2"
                            strokeWidth={1.6}
                          />
                          <path
                            d="M9 10V8a3 3 0 0 1 6 0v2"
                            strokeWidth={1.6}
                          />
                        </svg>
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>

            {/* zona inferior: sesión */}
            <div className="mt-2 border-t border-slate-100 pt-3 px-4 text-xs text-slate-400">
              {user ? (
                <div className="flex items-center justify-between">
                  <span className="truncate">
                    Sesión:{" "}
                    <span className="font-medium text-slate-600">
                      {user.email}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={onLogout}
                    className="ml-2 text-[11px] font-medium text-[#F28C18] hover:text-[#d9730d]"
                  >
                    Cerrar
                  </button>
                </div>
              ) : (
                <span>© {new Date().getFullYear()} </span>
              )}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
