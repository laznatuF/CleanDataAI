// src/components/Header.tsx
import React from "react";
import { Link } from "react-router-dom";

export default function Header() {
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b border-slate-200">
      {/* ancho completo, con muy poco padding para “esquinas” */}
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

          {/* Derecha: enlaces */}
          <nav className="flex items-center gap-6 text-sm">
            <Link
              to="/help"
              className="text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-300 rounded"
            >
              Ayuda
            </Link>
            <Link
              to="/about"
              className="text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-300 rounded"
            >
              Acerca de
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
