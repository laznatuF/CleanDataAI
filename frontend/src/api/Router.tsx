// src/Router.tsx
import { createBrowserRouter, redirect } from "react-router-dom";
import Home from "./pages/Home";
import Status from "./pages/Status";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import LoginToken from "./pages/LoginToken";
import DiagnosticsPage from "./pages/Diagnostics";
import PlansPage from "./pages/Plans"; // ⬅️ NUEVO
import CreateAccount from "./pages/CreateAccount";

export const router = createBrowserRouter([
  // Home
  { path: "/", element: <Home /> },

  // Proceso / resultados
  { path: "/status/:runId", element: <Status /> },
  { path: "/results/:runId", element: <Results /> },

  // Ajustes / diagnóstico
  { path: "/settings", element: <Settings /> },
  { path: "/diagnostico", element: <DiagnosticsPage /> },

  // Auth passwordless
  { path: "/login", element: <Login /> },
  { path: "/login/token", element: <LoginToken /> },

  // Crear cuenta
  { path: "/crear-cuenta", element: <CreateAccount /> },

  // Planes
  { path: "/planes", element: <PlansPage /> }, // ⬅️ ya no redirige

  // Rutas sin parámetro → redirigen al home
  { path: "/status", loader: () => redirect("/") },
  { path: "/results", loader: () => redirect("/") },

  // Enlaces aún no implementados
  { path: "/mis-procesos", loader: () => redirect("/") },
  { path: "/help", loader: () => redirect("/") },
  { path: "/about", loader: () => redirect("/") },

  // Fallback
  { path: "*", element: <Home /> },
]);
