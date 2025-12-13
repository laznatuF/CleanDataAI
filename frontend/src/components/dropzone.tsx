// frontend/src/components/dropzone.tsx
import React, { useRef, useState } from 'react';

type Props = {
  onFile: (f: File) => void;
  accept?: string;          // ej: ".csv,.xlsx,.xls,.ods"
  maxSizeMB?: number;       // por defecto 20
  onError?: (msg: string) => void;
};

export default function Dropzone({ onFile, accept = ".csv,.xlsx,.xls,.ods", maxSizeMB = 20, onError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function handleFiles(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;

    const okType = accept.split(",").some(ext => f.name.toLowerCase().endsWith(ext.trim()));
    if (!okType) {
      onError?.("Formato no soportado. Usa CSV, XLSX, XLS u ODS.");
      return;
    }
    const maxBytes = maxSizeMB * 1024 * 1024;
    if (f.size > maxBytes) {
      const mb = (f.size / (1024*1024)).toFixed(2);
      onError?.(`Archivo demasiado grande (${mb} MB). Límite permitido: ${maxSizeMB} MB.`);
      return;
    }
    onFile(f);
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Zona para arrastrar o seleccionar archivo"
      className={`border-2 border-dashed rounded p-6 text-center outline-none ${over ? 'bg-blue-50' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); handleFiles(e.dataTransfer.files); }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
    >
      <input
        ref={inputRef}
        id="file-input"
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <button
        type="button"
        className="cursor-pointer inline-block px-4 py-2 rounded bg-blue-600 text-white focus:ring-2 focus:ring-offset-2 focus:ring-blue-600"
        onClick={() => inputRef.current?.click()}
      >
        Seleccionar archivo
      </button>
      <p className="text-xs text-gray-500 mt-2">
        Acepta CSV, XLSX, XLS u ODS.
      </p>
    </div>
  );
}


