/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FDE_API_BASE_URL?: string;
  readonly VITE_FDE_WS_BASE_URL?: string;
  readonly VITE_FDE_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
