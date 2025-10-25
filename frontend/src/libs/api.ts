// src/libs/api.ts
const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/** Wrapper con credentials y manejo de Content-Type.
 * No forzamos "application/json" si el body es FormData. */
async function http<T = any>(url: string, opts: RequestInit = {}): Promise<T> {
  const headers =
    opts.body instanceof FormData
      ? { ...(opts.headers || {}) }
      : { "Content-Type": "application/json", ...(opts.headers || {}) };

  const res = await fetch(API + url, {
    credentials: "include",
    ...opts,
    headers,
  });

  if (!res.ok) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${detail || res.statusText}`.trim());
  }

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    // p.ej. 204 No Content o descargas de archivo
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

/* ======================== AUTH (passwordless) ======================== */

export type User = { id: string; email: string; name?: string; plan?: string } | null;

export const requestMagic = (email: string, name?: string) =>
  http<{ ok: true }>("/api/auth/request", {
    method: "POST",
    body: JSON.stringify({ email, name }),
  });

export const verifyMagic = (params: { token?: string; email?: string; code?: string }) =>
  http<{ ok: true; user: NonNullable<User> }>("/api/auth/verify", {
    method: "POST",
    body: JSON.stringify(params),
  });

export const logout = () => http<{ ok: true }>("/api/auth/logout", { method: "POST" });

export const me = () => http<{ user: User }>("/api/auth/me");

/** Aliases (compat) */
export const authRequestLogin = (email: string, name = "") => requestMagic(email, name);
export const authVerifyToken = (token: string) => verifyMagic({ token });
export const authVerifyOtp = (email: string, code: string) => verifyMagic({ email, code });
export const authLogout = () => logout();
export const authMe = () => me();

/* ======================== API de procesos ======================== */

export async function uploadFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  // NO agregamos Content-Type, el navegador pone el boundary correcto.
  const res = await fetch(API + "/api/process", {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const getStatus = (id: string) => http(`/api/status/${id}`);

/** Construye URL a artefactos protegidos por el backend.
 * Si recibe "runs/<id>/artifacts/<name>", lo mapea a "/api/artifacts/<id>/<name>".
 * Para cualquier otra ruta relativa, hace fallback a `${API}/${rel}`. */
export function artifactUrl(rel: string) {
  const clean = (rel || "").replace(/^\/+/, "");
  const m = clean.match(/^runs\/([^/]+)\/artifacts\/([^/]+)$/i);
  if (m) {
    const [, pid, name] = m;
    return `${API}/api/artifacts/${encodeURIComponent(pid)}/${encodeURIComponent(name)}`;
  }
  return `${API}/${clean}`;
}

/** Igual que artifactUrl, pero fuerza descarga con `?download=1` */
export function artifactDownloadUrl(rel: string) {
  const url = artifactUrl(rel);
  return `${url}${url.includes("?") ? "&" : "?"}download=1`;
}

/* ======================== Bitácora ======================== */

export const getHistory = (id: string, limit?: number) =>
  http<{ items: any[]; count: number }>(
    `/api/history/${encodeURIComponent(id)}${limit ? `?limit=${limit}` : ""}`
  );
