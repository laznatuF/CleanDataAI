// src/pages/LoginToken.tsx
import { useState } from "react";

export default function LoginToken() {
  const [jwt, setJwt] = useState(localStorage.getItem("jwt") || "");
  return (
    <div className="max-w-md mx-auto p-6 space-y-3">
      <h1 className="text-xl font-semibold">Autenticación</h1>
      <input
        value={jwt}
        onChange={(e) => setJwt(e.target.value)}
        placeholder="Pega tu JWT aquí"
        className="w-full border rounded px-3 py-2"
      />
      <div className="flex gap-2">
        <button
          className="px-3 py-2 border rounded"
          onClick={() => {
            localStorage.setItem("jwt", jwt);
            alert("Guardado");
          }}
        >
          Guardar token
        </button>
        <button
          className="px-3 py-2 border rounded"
          onClick={() => {
            localStorage.removeItem("jwt");
            setJwt("");
          }}
        >
          Borrar
        </button>
      </div>
      <p className="text-sm text-gray-600">El token se adjunta en descargas (endpoints privados).</p>
    </div>
  );
}
