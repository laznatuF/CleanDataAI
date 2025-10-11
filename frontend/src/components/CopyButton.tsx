// src/components/CopyButton.tsx
import { useState } from "react";

export default function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="px-2 py-1 rounded border"
      aria-label="Copiar ID"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
    >
      {copied ? "Copiado" : "Copiar"}
    </button>
  );
}
