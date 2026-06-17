import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Load env (e.g. VITE_CLERK_PUBLISHABLE_KEY) from the repo-root .env, the same
  // file the backend reads, so dev secrets live in one place. Only VITE_-prefixed
  // vars reach the client; backend PYSTACK_ secrets stay server-side.
  envDir: fileURLToPath(new URL("..", import.meta.url)),
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright owns e2e/; keep Vitest from collecting its *.spec.ts files.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
