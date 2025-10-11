// src/api/client.ts

/**
 * Descubre la URL base de la API en este orden:
 * 1) import.meta.env.VITE_API_BASE_URL  (Vite)
 * 2) (opcional) window.__API_BASE__     (inyectable en index.html si hiciera falta)
 * 3) http://127.0.0.1:8000              (fallback de desarrollo)
 *
 * Además, se normaliza quitando la barra final si viene con ella.
 */
let __API_BASE: string =
  (typeof import.meta !== "undefined" &&
    (import.meta as any).env &&
    (import.meta as any).env.VITE_API_BASE_URL) ||
  // @ts-ignore opcional: variable global inyectable
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  "http://127.0.0.1:8000";

__API_BASE = __API_BASE.replace(/\/+$/, "");
export const API_BASE = __API_BASE;

/** Clave donde guardar un JWT si más adelante protegemos endpoints privados. */
const TOKEN_KEY = "jwt";

/** Error estructurado para respuestas HTTP no-OK. */
export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Estados posibles del proceso. Incluimos 'completed' por compatibilidad, lo normalizamos a 'done' en getStatus. */
export type ProcessStatus = "queued" | "running" | "done" | "failed" | "completed";

/** Respuesta al crear proceso. */
export type ProcessCreated = { process_id: string };

/** Carga de estado enriquecida. */
export interface StatusPayload {
  status: ProcessStatus;
  progress?: number; // 0..100
  step?: string; // etapa actual
  updated_at?: string; // ISO timestamp
  metrics?: {
    rows?: number;
    cols?: number;
    duration_ms?: number;
  };
  steps?: Array<{
    name: string;
    status: ProcessStatus | "pending";
    started_at?: string;
    finished_at?: string;
    duration_ms?: number;
  }>;
  error_message?: string;
}

/* ========================= Helpers HTTP ========================= */

type ApiFetchOptions = Omit<RequestInit, "signal"> & {
  /** Timeout en ms (por defecto 30s). */
  timeoutMs?: number;
  /** Adjuntar Authorization: Bearer <jwt> si existe en localStorage. */
  withAuth?: boolean;
};

async function apiFetch<T = unknown>(
  input: string,
  { timeoutMs = 30000, withAuth = true, headers, ...init }: ApiFetchOptions = {}
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const finalHeaders = new Headers(headers || {});
  if (withAuth) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !finalHeaders.has("Authorization")) {
      finalHeaders.set("Authorization", `Bearer ${token}`);
    }
  }

  let res: Response;
  try {
    res = await fetch(input, {
      ...init,
      headers: finalHeaders,
      signal: controller.signal,
    });
  } catch (e: any) {
    clearTimeout(timer);
    throw new ApiError(`No se pudo conectar con la API: ${e?.message || e}`, 0);
  }

  clearTimeout(timer);

  // Intentar parsear JSON si lo hay
  let data: unknown = undefined;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      data = await res.json();
    } catch {
      // si no se puede parsear, lo dejamos indefinido
    }
  } else {
    // si no es JSON, leer texto por si hay mensaje útil
    try {
      const txt = await res.text();
      if (txt) data = txt;
    } catch {
      /* ignore */
    }
  }

  if (!res.ok) {
    // Mensajes más claros por códigos habituales
    let msg = (data as any)?.detail || res.statusText || "Error de API";
    if (res.status === 413) {
      msg = "El archivo supera el límite permitido (HTTP 413).";
    } else if (res.status === 415) {
      msg = "Tipo de contenido no soportado (HTTP 415).";
    } else if (res.status === 400) {
      msg = typeof data === "string" ? data : (data as any)?.detail || "Solicitud inválida (HTTP 400).";
    }
    throw new ApiError(msg, res.status, data);
  }

  return data as T;
}

/* ========================= Endpoints ========================= */

/** Sube un archivo para procesar. Devuelve { process_id }. */
export async function uploadFile(file: File): Promise<ProcessCreated> {
  const fd = new FormData();
  fd.append("file", file);

  // No seteamos Content-Type; el navegador añade el boundary correcto.
  const raw = await apiFetch<any>(`${API_BASE}/process`, {
    method: "POST",
    body: fd,
    withAuth: true,
    timeoutMs: 120000, // subir archivos puede tardar más
  });

  // Mapeo robusto del id que devuelve el backend
  const process_id =
    (raw?.process_id ??
      raw?.id ??
      raw?.processId ??
      raw?.uuid ??
      "").toString();

  if (!process_id) {
    throw new ApiError("La API no devolvió un id del proceso.", 500, raw);
  }
  return { process_id };
}

/** Consulta el estado de un proceso. Normaliza 'completed' -> 'done'. */
export async function getStatus(id: string): Promise<StatusPayload> {
  const payload = await apiFetch<StatusPayload>(`${API_BASE}/status/${encodeURIComponent(id)}`, {
    method: "GET",
    withAuth: true,
  });

  // Normalización de estado por compatibilidad
  if (payload && payload.status === "completed") {
    (payload as any).status = "done";
  }

  return payload;
}

/**
 * URL directa al artefacto (si el backend NO exige cabecera Authorization para descarga).
 * Si tu backend protege la descarga con JWT en header, usa `downloadArtifact`.
 */
export function artifactUrl(id: string, name: string) {
  return `${API_BASE}/process/${encodeURIComponent(id)}/artifact/${encodeURIComponent(name)}`;
}

/**
 * Descarga un artefacto protegido (requiere Authorization). Devuelve un Blob.
 * Úsalo si tu backend exige JWT para descargar archivos.
 */
export async function downloadArtifact(id: string, name: string): Promise<Blob> {
  const url = `${API_BASE}/process/${encodeURIComponent(id)}/artifact/${encodeURIComponent(name)}`;
  const token = localStorage.getItem(TOKEN_KEY) || "";

  const res = await fetch(url, {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => res.statusText);
    throw new ApiError(txt || "Error al descargar artefacto", res.status);
  }
  return res.blob();
}

/** Diagnóstico rápido: hace GET /health y retorna true/false. */
export async function ping(): Promise<boolean> {
  try {
    await apiFetch(`${API_BASE}/health`, { method: "GET", withAuth: false, timeoutMs: 5000 });
    return true;
  } catch {
    return false;
  }
}

/** Utilidades opcionales para manejar JWT desde el cliente. */
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
