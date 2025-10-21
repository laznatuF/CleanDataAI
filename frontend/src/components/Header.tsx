// src/components/Header.tsx
import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { me, logout as apiLogout } from "../libs/api";

type SessionUser = { id: string; email: string; name?: string; plan?: string } | null;

export default function Header() {
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<SessionUser>(null);
  const nav = useNavigate();
  const loc = useLocation();

  // Cierra el menú al cambiar de ruta
  useEffect(() => {
    setOpen(false);
  }, [loc.pathname]);

  // Carga/actualiza estado de sesión (cookie HttpOnly)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await me(); // { user: {...} | null }
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
      nav("/");
    }
  }

  const isActive = useMemo(() => {
    const p = loc.pathname;
    return (href: string) => (p === href || (href !== "/" && p.startsWith(href)));
  }, [loc.pathname]);

  const baseLink =
    "text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-300 rounded";
  const activeLink = "text-slate-900 font-medium";

  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b border-slate-200">
      {/* ancho completo, padding mínimo para “esquinas” */}
      <div className="w-full px-3 sm:px-4">
        <div className="h-14 flex items-center justify-between">
          {/* Izquierda: marca */}
          <Link
            to="/"
            className="select-none text-lg sm:text-xl font-semibold tracking-tight text-sky-700 hover:text-sky-800"
            aria-label="CleanDataAI — Inicio"
          >
            Clean<span className="text-slate-900">DataAI</span>
          </Link>

          {/* Derecha: enlaces (desktop) */}
          <nav className="hidden md:flex items-center gap-6 text-sm">
            <Link to="/planes" className={`${baseLink} ${isActive("/planes") ? activeLink : ""}`}>
              Planes
            </Link>

            {user ? (
              <>
                <Link
                  to="/mis-procesos"
                  className={`${baseLink} ${isActive("/mis-procesos") ? activeLink : ""}`}
                >
                  Mis procesos
                </Link>
                <button onClick={onLogout} className={baseLink}>
                  Cerrar sesión
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className={`${baseLink} ${isActive("/login") ? activeLink : ""}`}
              >
                Iniciar sesión
              </Link>
            )}

            <Link to="/help" className={`${baseLink} ${isActive("/help") ? activeLink : ""}`}>
              Ayuda
            </Link>
            <Link to="/about" className={`${baseLink} ${isActive("/about") ? activeLink : ""}`}>
              Acerca de
            </Link>
          </nav>

          {/* Botón hamburguesa (mobile) */}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Menú"
            aria-expanded={open}
            className="md:hidden inline-flex items-center justify-center h-9 w-9 rounded-md border border-slate-300 text-slate-700"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" stroke="currentColor" fill="none">
              {open ? (
                <path strokeWidth="1.8" d="M6 6l12 12M18 6L6 18" />
              ) : (
                <path strokeWidth="1.8" d="M4 7h16M4 12h16M4 17h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Menú móvil */}
      {open && (
        <div className="md:hidden border-t border-slate-200 bg-white">
          <div className="w-full px-3 sm:px-4 py-3 flex flex-col gap-1 text-sm">
            <Link
              to="/planes"
              className={`py-2 ${isActive("/planes") ? "text-slate-900 font-medium" : "text-slate-700"}`}
            >
              Planes
            </Link>

            {user ? (
              <>
                <Link
                  to="/mis-procesos"
                  className={`py-2 ${isActive("/mis-procesos") ? "text-slate-900 font-medium" : "text-slate-700"}`}
                >
                  Mis procesos
                </Link>
                <button onClick={onLogout} className="py-2 text-left text-slate-700">
                  Cerrar sesión
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className={`py-2 ${isActive("/login") ? "text-slate-900 font-medium" : "text-slate-700"}`}
              >
                Iniciar sesión
              </Link>
            )}

            <Link
              to="/help"
              className={`py-2 ${isActive("/help") ? "text-slate-900 font-medium" : "text-slate-700"}`}
            >
              Ayuda
            </Link>
            <Link
              to="/about"
              className={`py-2 ${isActive("/about") ? "text-slate-900 font-medium" : "text-slate-700"}`}
            >
              Acerca de
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

