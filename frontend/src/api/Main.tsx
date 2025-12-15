// frontend/src/main.tsx
import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./Router";
import { AuthProvider } from "../context/Authcontext";
import "./index.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("No se encontró el elemento #root");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <AuthProvider>
      <Suspense
        fallback={
          <div className="min-h-screen grid place-items-center text-slate-600">
            Cargando…
          </div>
        }
      >
        <RouterProvider router={router} />
      </Suspense>
    </AuthProvider>
  </React.StrictMode>
);
