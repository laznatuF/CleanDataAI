// src/pages/Home.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Dropzone from '../../components/dropzone';
import { uploadFile } from '../../libs/api';

export default function Home() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(f: File) {
    try {
      setBusy(true);
      setError(null);
      const res = await uploadFile(f);
      const pid = res.process_id || res.id;
      navigate(`/status/${pid}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold">Subir archivo</h1>
      <Dropzone onFile={handleFile} onError={(m) => setError(m)} />
      {busy && <div className="text-sm text-gray-500">Subiendo y creando proceso…</div>}
      {error && <div className="p-3 rounded bg-red-50 text-red-700 text-sm">{error}</div>}
    </div>
  );
}
