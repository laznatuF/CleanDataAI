// src/pages/Status.tsx
import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import Stepper, { type StepItem } from '../../components/Steeper';
import { getStatus } from '../../libs/api';

const STAGES = ['Subir archivo', 'Perfilado', 'Limpieza', 'Dashboard', 'Reporte'] as const;
const PROCESS_FINISHED = new Set(['ok', 'done', 'finished', 'completed', 'success']);
const PROCESS_QUEUED   = new Set(['queued', 'pending']);
const STEP_FINISHED    = new Set(['ok', 'done', 'finished', 'success']);
const STEP_RUNNING     = new Set(['running', 'in_progress']);

type ApiStep = { name: string; status?: string | null };
type StatusResponse = {
  status?: string | null; steps?: ApiStep[]; progress?: number | null;
  updated_at?: string | null; current_step?: string | null; error?: string | null;
};

export default function StatusPage() {
  const params = useParams();
  const runId = ((params.runId as string) ?? (params.id as string) ?? '').trim();

  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) return;
    let timer: number | undefined;
    let canceled = false;

    const tick = async () => {
      try {
        const json = await getStatus(runId);
        if (canceled) return;
        setData(json);
        setLoading(false);
        const s = String(json?.status ?? '');
        if (!PROCESS_FINISHED.has(s) && s !== 'failed') {
          timer = window.setTimeout(tick, 1500);
        }
      } catch (err) {
        if (canceled) return;
        setData(d => d ?? { status: 'failed', error: (err as Error).message });
        setLoading(false);
      }
    };

    tick();
    return () => { canceled = true; if (timer) clearTimeout(timer); };
  }, [runId]);

  const currentIdx = useMemo(() => {
    if (!data) return -1;
    if (data.current_step) {
      const i = STAGES.indexOf(data.current_step as any);
      if (i >= 0) return i;
    }
    const list = data.steps ?? [];
    for (let i = 0; i < STAGES.length; i++) {
      const s = list.find(x => x.name === STAGES[i]);
      if (!s || !STEP_FINISHED.has(String(s.status ?? ''))) return i;
    }
    return -1;
  }, [data]);

  const steps: StepItem[] = useMemo(() => {
    if (!data) return STAGES.map(label => ({ label, state: 'pending' as const }));

    const proc = String(data.status ?? '');
    if (PROCESS_FINISHED.has(proc)) return STAGES.map(label => ({ label, state: 'ok' as const }));
    if (proc === 'failed')         return STAGES.map(label => ({ label, state: 'failed' as const }));

    // queued → muestra todo pending
    if (PROCESS_QUEUED.has(proc))  return STAGES.map(label => ({ label, state: 'pending' as const }));

    return STAGES.map<StepItem>((label, idx) => {
      let state: StepItem['state'] = 'pending';
      const backend = (data.steps ?? []).find(s => s.name === label);
      if (backend) {
        const b = String(backend.status ?? '').toLowerCase();
        if (STEP_FINISHED.has(b)) state = 'ok';
        else if (STEP_RUNNING.has(b)) state = 'running';
        else if (b === 'failed') state = 'failed';
      }
      if (state === 'pending' && currentIdx > -1) {
        if (idx < currentIdx) state = 'ok';
        else if (idx === currentIdx) state = 'running';
      }
      return { label, state };
    });
  }, [data, currentIdx]);

  const progress   = Math.max(0, Math.min(100, Number(data?.progress ?? 0)));
  const lastUpdate = data?.updated_at ? new Date(data.updated_at).toLocaleString('es-ES') : '—';
  const failed     = String(data?.status ?? '') === 'failed';
  const queued     = PROCESS_QUEUED.has(String(data?.status ?? ''));

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-semibold">Ejecución</h1>

      {queued && (
        <div className="p-3 rounded-md bg-yellow-50 text-yellow-800 text-sm">
          El proceso está en cola… empezará en breve.
        </div>
      )}

      {!runId && (
        <div className="p-3 rounded-md bg-yellow-50 text-yellow-800 text-sm">
          Falta el <code>runId</code> en la ruta. Vuelve al inicio y procesa un archivo para empezar.
        </div>
      )}

      <Stepper steps={steps} />

      <div className="space-y-2">
        <div className="w-full h-2 bg-gray-200 rounded">
          <div
            className="h-2 rounded bg-green-600 transition-all"
            style={{ width: `${progress}%` }}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            role="progressbar"
          />
        </div>
        <div className="text-xs text-gray-500">
          Progreso: {progress}% · Última actualización: {lastUpdate}
        </div>
      </div>

      {failed && (
        <div className="p-3 rounded-md bg-red-50 text-red-700 text-sm">
          Proceso fallido. {data?.error ? `Detalle: ${data.error}` : null}
        </div>
      )}

      {loading && <div className="text-sm text-gray-500">Cargando…</div>}
    </div>
  );
}
