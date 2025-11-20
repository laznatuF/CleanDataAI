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

// --- Iconos simples para los accesos rápidos ---
function IconHome() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <path
        d="M4 11.5 12 4l8 7.5"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6.5 11.5V19h11v-7.5"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconLogin() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <rect x="4" y="3.5" width="11" height="17" rx="2" strokeWidth={1.6} />
      <path
        d="M11 12h8m0 0-2-2m2 2-2 2"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconUserPlus() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <circle cx="10" cy="8" r="3" strokeWidth={1.6} />
      <path
        d="M4.5 18.5c.8-2.2 2.7-3.5 5.5-3.5 2.8 0 4.7 1.3 5.5 3.5"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <path d="M17.5 8.5h3m-1.5-1.5v3" strokeWidth={1.6} strokeLinecap="round" />
    </svg>
  );
}

function IconPlans() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <rect x="5" y="4" width="6" height="14" rx="1.5" strokeWidth={1.6} />
      <rect x="13" y="6" width="6" height="12" rx="1.5" strokeWidth={1.6} />
    </svg>
  );
}

function IconProcesses() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <circle cx="7" cy="7" r="2.3" strokeWidth={1.6} />
      <circle cx="17" cy="7" r="2.3" strokeWidth={1.6} />
      <circle cx="7" cy="17" r="2.3" strokeWidth={1.6} />
      <circle cx="17" cy="17" r="2.3" strokeWidth={1.6} />
    </svg>
  );
}

function IconInfo() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <circle cx="12" cy="12" r="8" strokeWidth={1.6} />
      <path d="M12 10v5" strokeWidth={1.6} strokeLinecap="round" />
      <circle cx="12" cy="7" r="0.9" fill="currentColor" />
    </svg>
  );
}

function IconHelp() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
      <circle cx="12" cy="12" r="8" strokeWidth={1.6} />
      <path
        d="M9.7 9.2a2.4 2.4 0 0 1 4.6.9c0 1.3-1 1.9-1.6 2.3-.5.3-.7.6-.7 1.1v.5"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <circle cx="12" cy="16.3" r="0.9" fill="currentColor" />
    </svg>
  );
}

// Icono usuario con X (sin sesión)
function IconUserOff() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" stroke="currentColor" fill="none">
      <circle cx="10" cy="8" r="3" strokeWidth={1.8} />
      <path
        d="M4.5 18.5c.8-2.2 2.7-3.5 5.5-3.5 1 0 1.9.2 2.7.5"
        strokeWidth={1.8}
        strokeLinecap="round"
      />
      <path
        d="M17 6.5l3 3M20 6.5l-3 3"
        strokeWidth={1.8}
        strokeLinecap="round"
      />
    </svg>
  );
}

// Icono usuario "on" (con sesión)
function IconUserOn() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" stroke="currentColor" fill="none">
      <circle cx="10" cy="8" r="3" strokeWidth={1.8} />
      <path
        d="M4.5 18.5c.8-2.2 2.7-3.5 5.5-3.5 2.8 0 4.7 1.3 5.5 3.5"
        strokeWidth={1.8}
        strokeLinecap="round"
      />
      <path
        d="M16.5 7.8 18 9.5 20.7 6"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Botón de modo oscuro
function DarkModeToggle({ dark, onToggle }: { dark: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
      aria-label="Cambiar modo oscuro"
    >
      {/* Luna */}
      <svg viewBox="0 0 24 24" className="h-4 w-4" stroke="currentColor" fill="none">
        <path
          d="M19 14.5A7 7 0 0 1 11.5 5 5.5 5.5 0 1 0 19 14.5Z"
          strokeWidth={1.7}
          fill={dark ? "#FBBF24" : "none"}
        />
      </svg>
    </button>
  );
}

// Bloque estado autenticación
function AuthStatus({ user }: { user: SessionUser }) {
  const isLogged = !!user;

  return (
    <Link
      to={isLogged ? "/mis-procesos" : "/login"}
      className="flex flex-col items-center text-xs text-slate-600 hover:text-[#F28C18]"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white shadow-sm mb-1">
        {isLogged ? <IconUserOn /> : <IconUserOff />}
      </div>
      <span className="leading-none">
        {isLogged ? (user?.name || "Sesión") : "sin"}
      </span>
      <span className="leading-none font-semibold">
        {isLogged ? "Mi cuenta" : "Acceder"}
      </span>
    </Link>
  );
}

export default function Header() {
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<SessionUser>(null);
  const [dark, setDark] = useState(false);

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

  // Inicializar modo oscuro desde la clase del documento (si la hubiera)
  useEffect(() => {
    if (typeof document === "undefined") return;
    const hasDark = document.documentElement.classList.contains("dark");
    setDark(hasDark);
  }, []);

  function toggleDark() {
    if (typeof document === "undefined") return;
    setDark((prev) => {
      const next = !prev;
      const root = document.documentElement;
      if (next) root.classList.add("dark");
      else root.classList.remove("dark");
      return next;
    });
  }

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

  // Mapeo simple href → icono para la barra compacta
  function iconFor(href: string) {
    if (href === "/") return <IconHome />;
    if (href.startsWith("/login")) return <IconLogin />;
    if (href.startsWith("/crear-cuenta")) return <IconUserPlus />;
    if (href.startsWith("/planes")) return <IconPlans />;
    if (href.startsWith("/mis-procesos")) return <IconProcesses />;
    if (href.startsWith("/about")) return <IconInfo />;
    if (href.startsWith("/help")) return <IconHelp />;
    return <IconHome />;
  }

  return (
    <>
      {/* === Barra compacta / accesos rápidos cuando el menú está CERRADO === */}
      {!open && (
        <>
          {/* Desktop: tarjeta vertical pegada a la esquina superior izquierda */}
          <div className="fixed left-0 top-0 z-40 hidden md:flex">
            <div className="m-4 flex flex-col items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-4 shadow-md">
              {/* Logo grande */}
              <Link
                to="/"
                className="flex items-center justify-center"
                aria-label="Ir al inicio de CleanDataAI"
              >
                <img
                  src="/brand/cleandataai-logo.png"
                  alt="CleanDataAI"
                  className="h-16 w-auto"
                  loading="eager"
                  decoding="async"
                />
              </Link>

              {/* Botón hamburguesa (abre el drawer) */}
              <button
                type="button"
                aria-label="Abrir menú principal"
                aria-expanded={open}
                onClick={() => setOpen(true)}
                className="mb-1 inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 bg-[#FDFBF6] text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" stroke="currentColor" fill="none">
                  <path strokeWidth={1.8} d="M4 7h16M4 12h16M4 17h16" />
                </svg>
              </button>

              {/* Iconos de navegación */}
              <div className="flex flex-col items-center gap-3">
                {menuItems.map((item) => {
                  const active = isActive(item.href);
                  const locked = item.locked;

                  return (
                    <Link
                      key={item.href}
                      to={item.href}
                      className={[
                        "flex h-9 w-9 items-center justify-center rounded-full border text-slate-600 transition-colors",
                        locked
                          ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-300 pointer-events-none"
                          : active
                          ? "border-[#F28C18] bg-[#FFF3E6] text-[#F28C18]"
                          : "border-slate-200 bg-white hover:bg-slate-50",
                      ].join(" ")}
                    >
                      {iconFor(item.href)}
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Mobile: barra horizontal arriba */}
          <div className="fixed inset-x-0 top-0 z-40 flex items-center justify-between bg-white/95 px-3 py-2 shadow md:hidden">
            {/* Logo + accesos rápidos básicos (home + hamburguesa) */}
            <div className="flex items-center gap-2">
              <Link
                to="/"
                aria-label="Ir al inicio de CleanDataAI"
                className="flex items-center"
              >
                <img
                  src="/brand/cleandataai-logo.png"
                  alt="CleanDataAI"
                  className="h-10 w-auto"
                />
              </Link>

              <div className="flex items-center gap-1">
                {/* Hamburguesa */}
                <button
                  type="button"
                  aria-label="Abrir menú principal"
                  aria-expanded={open}
                  onClick={() => setOpen(true)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-[#FDFBF6] text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#F28C18]/40"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    stroke="currentColor"
                    fill="none"
                  >
                    <path strokeWidth={1.8} d="M4 7h16M4 12h16M4 17h16" />
                  </svg>
                </button>

                {/* Home rápido */}
                <Link
                  to="/"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  aria-label="Ir a Principal"
                >
                  <IconHome />
                </Link>
              </div>
            </div>

            {/* A la derecha: modo oscuro + estado autenticación */}
            <div className="flex items-center gap-3">
              <DarkModeToggle dark={dark} onToggle={toggleDark} />
              <AuthStatus user={user} />
            </div>
          </div>

          {/* Desktop: bloque superior derecho (modo oscuro + auth) */}
          <div className="fixed right-4 top-4 z-40 hidden items-center gap-4 md:flex">
            <DarkModeToggle dark={dark} onToggle={toggleDark} />
            <AuthStatus user={user} />
          </div>
        </>
      )}

      {/* === Menú lateral / drawer cuando está ABIERTO === */}
      {open && (
        <div className="fixed inset-0 z-30">
          {/* fondo semitransparente */}
          <div
            className="absolute inset-0 bg-black/10"
            onClick={() => setOpen(false)}
          />
          <aside className="relative z-40 flex h-full w-[260px] flex-col border-r border-slate-200 bg-white pt-16 pb-6 shadow-xl">
            {/* botón cerrar (la X grande) */}
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

            {/* Logo en el menú abierto */}
            <div className="px-4 pb-4">
              <img
                src="/brand/cleandataai-logo.png"
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
