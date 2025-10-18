// src/components/Header.tsx
import React, { useEffect, useRef, useState } from "react";

export default function Header() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Cerrar con Escape y bloquear scroll de fondo
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    if (open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.removeEventListener("keydown", onKey);
        document.body.style.overflow = prev;
      };
    }
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Cerrar al hacer click fuera del panel
  function onOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
      setOpen(false);
    }
  }

  return (
    <>
      <header className="border-b border-slate-200">
        <div className="mx-auto max-w-6xl px-5 h-14 flex items-center justify-between">
          <div className="font-semibold text-base sm:text-lg">
            <span className="text-sky-600">Clean</span>DataAI
          </div>

          {/* Navegación en desktop */}
          <nav className="hidden sm:flex gap-6 text-sm text-slate-600">
            <a href="#" className="hover:text-slate-900">
              Ayuda
            </a>
            <a href="#" className="hover:text-slate-900">
              Acerca de
            </a>
          </nav>

          {/* Botón hamburguesa en móvil */}
          <button
            type="button"
            className="sm:hidden inline-flex items-center justify-center w-9 h-9 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300"
            aria-label="Abrir menú"
            aria-controls="mobile-menu"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <svg viewBox="0 0 24 24" stroke="currentColor" fill="none" className="w-5 h-5">
              <path strokeWidth="1.8" d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
        </div>
      </header>

      {/* Overlay + panel móvil */}
      {open && (
        <div
          id="mobile-menu"
          className="sm:hidden fixed inset-0 z-50 bg-black/40"
          role="dialog"
          aria-modal="true"
          onClick={onOverlayClick}
        >
          <div
            ref={panelRef}
            className="ml-auto h-full w-72 bg-white shadow-xl p-4 flex flex-col"
          >
            <div className="flex items-center justify-between">
              <div className="font-semibold text-lg">
                <span className="text-sky-600">Clean</span>DataAI
              </div>
              <button
                type="button"
                className="inline-flex items-center justify-center w-9 h-9 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-300"
                aria-label="Cerrar menú"
                onClick={() => setOpen(false)}
              >
                <svg viewBox="0 0 24 24" stroke="currentColor" fill="none" className="w-5 h-5">
                  <path strokeWidth="1.8" d="M6 6l12 12M18 6l-12 12" />
                </svg>
              </button>
            </div>

            <nav className="mt-6 flex flex-col gap-2 text-slate-700">
              <a
                href="#"
                className="rounded-md px-3 py-2 hover:bg-slate-50"
                onClick={() => setOpen(false)}
              >
                Ayuda
              </a>
              <a
                href="#"
                className="rounded-md px-3 py-2 hover:bg-slate-50"
                onClick={() => setOpen(false)}
              >
                Acerca de
              </a>
            </nav>

            <div className="mt-auto text-[11px] text-slate-400 px-3">
              © {new Date().getFullYear()} CleanDataAI
            </div>
          </div>
        </div>
      )}
    </>
  );
}
