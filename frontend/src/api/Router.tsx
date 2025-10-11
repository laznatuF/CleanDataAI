// src/Router.tsx
import { createBrowserRouter, redirect } from "react-router-dom";
import Home from "./pages/Home";
import Status from "./pages/Status";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import LoginToken from "./pages/LoginToken";

export const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/status/:runId", element: <Status /> },
  { path: "/results/:runId", element: <Results /> },
  { path: "/settings", element: <Settings /> },
  { path: "/login", element: <LoginToken /> },
  { path: "/status", loader: () => redirect("/") },
  { path: "/results", loader: () => redirect("/") },
  { path: "*", element: <Home /> },
]);
