/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Clerk publishable key; required — the app refuses to boot without it. */
  readonly VITE_CLERK_PUBLISHABLE_KEY: string;
  /** Absolute backend URL in production; unset in dev (relative via Vite proxy). */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
