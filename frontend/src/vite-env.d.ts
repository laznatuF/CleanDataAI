/// <reference types="vite/client" />

/**
 * Declara tus variables de entorno accesibles como import.meta.env.VITE_*
 * (añade aquí todas las que uses).
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
