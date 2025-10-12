// src/api/http.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function getApiBase() {
  return API_BASE;
}

/** fetch que agrega Authorization: Bearer <JWT> si existe en localStorage */
export async function authFetch(input: string, init: RequestInit = {}) {
  const token = localStorage.getItem("jwt") || "";
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers });
  return res;
}

