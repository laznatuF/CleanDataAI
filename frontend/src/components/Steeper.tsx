// src/components/Stepper.tsx

export const STEP_STATES = ['pending', 'running', 'done', 'failed'] as const;
export type StepState = typeof STEP_STATES[number];

export interface StepItem {
  label: string;
  /** Acepta "ok" pero se normaliza a "done" internamente */
  state: StepState | 'ok';
}

export function Stepper({
  steps,
  className = '',
}: {
  steps: StepItem[];
  className?: string;
}) {
  return (
    <ol className={`flex gap-4 flex-wrap ${className}`} role="list">
      {steps.map((s, i) => {
        // Normalizamos "ok" → "done" para el render/estilos
        const normalized: StepState = s.state === 'ok' ? 'done' : s.state;
        return (
          <li key={i} className="flex items-center gap-2">
            <span
              aria-hidden
              className={`inline-block w-3 h-3 rounded-full ${dotColor(normalized)}`}
            />
            <span className="text-sm">{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function dotColor(state: StepState): string {
  switch (state) {
    case 'done':
      return 'bg-green-500';
    case 'running':
      return 'bg-blue-500 animate-pulse';
    case 'failed':
      return 'bg-red-500';
    default:
      return 'bg-gray-300';
  }
}

export default Stepper;
