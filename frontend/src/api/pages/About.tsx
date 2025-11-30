// src/api/pages/About.tsx
import React from "react";
import Header from "../../components/Header";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[#FDFBF6] text-slate-800">
      <Header />
      <main className="mx-auto w-full max-w-4xl px-6 md:px-8 py-16">
        <section className="rounded-3xl border border-[#E4DCCB] bg-white p-8 shadow-sm">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-4">
            Acerca de CleanDataAI
          </h1>
          <p className="text-sm text-slate-500 mb-6">
            CleanDataAI es una plataforma que automatiza el perfilado, limpieza y
            visualización de datos en archivos CSV/Excel, pensada para usuarios
            de negocio que no quieren pelear con scripts ni fórmulas.
          </p>

          <div className="space-y-4 text-sm leading-relaxed text-slate-700">
            <p>
              A partir de un archivo con datos, CleanDataAI genera un{" "}
              <strong>reporte de calidad</strong>, sugiere correcciones,
              construye un <strong>dataset limpio</strong> y arma un{" "}
              <strong>dashboard interactivo</strong> con métricas clave.
            </p>
            <p>
              Nuestro objetivo es reducir el tiempo que las personas pasan
              luchando con planillas, para que puedan concentrarse en{" "}
              <strong>analizar y decidir</strong>, no en limpiar datos.
            </p>
            <p>
              Esta versión que estás utilizando corresponde al prototipo
              desarrollado como parte de un proyecto de título de Ingeniería
              Informática.
            </p>
          </div>

          <div className="mt-8 text-xs text-slate-500 border-t border-slate-100 pt-4">
            <p>
              © {new Date().getFullYear()} CleanDataAI – Proyecto académico.  
              Para soporte o consultas específicas, utiliza la sección{" "}
              <strong>Ayuda</strong> del menú.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
