// src/lib/api.ts
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''; // dev: vacío → usa proxy

type StepState = 'pending' | 'queued' | 'running' | 'ok' | 'failed' | string;

export interface Step { name: string; status: StepState }
export interface StatusResponse {
  id?: string; status?: string; progress?: number | null;
  updated_at?: string | null; current_step?: string | null;
  steps?: Step[]; artifacts?: Record<string,string>; metrics?: Record<string,unknown>;
  error?: string;
}
export interface UploadResponse { id: string; process_id?: string; status?: string }

function friendlyError(res: Response, body: string) {
  if (res.status === 415) return "Formato no soportado. Usa CSV, XLSX, XLS u ODS.";
  if (res.status === 413) return body || "Archivo demasiado grande. Reduce el tamaño e intenta de nuevo.";
  if (res.status === 400) return body || "Solicitud inválida.";
  if (res.status === 404) return body || "Proceso no encontrado.";
  return body || `Error ${res.status} ${res.statusText}`;
}

async function parseJsonSafe(res: Response) {
  const ct = res.headers.get('content-type') ?? '';
  const txt = await res.text();
  if (!ct.includes('application/json')) {
    throw new Error(friendlyError(res, txt.slice(0,160)));
  }
  try { return JSON.parse(txt) } catch { throw new Error(friendlyError(res, txt.slice(0,160))) }
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData(); fd.append('file', file);
  const res = await fetch(`${API_BASE}/api/process`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text().then(t => friendlyError(res, t)));
  return (await parseJsonSafe(res)) as UploadResponse;
}

export async function getStatus(processId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/status/${encodeURIComponent(processId)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(await res.text().then(t => friendlyError(res, t)));
  return (await parseJsonSafe(res)) as StatusResponse;
}

export function artifactUrl(relOrAbsPath: string): string {
  if (!relOrAbsPath) return '';
  return relOrAbsPath.startsWith('/') ? relOrAbsPath : `/${relOrAbsPath}`;
}
