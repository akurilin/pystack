import * as Sentry from "@sentry/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { ClerkWithRouter } from "./auth/ClerkWithRouter";
// Side-effect import: configures the generated API client's base URL and attaches
// the Clerk session token to every request before any component issues one.
import "./api/config";
import "./styles.css";

// Error monitoring. Gated on the DSN so local dev (and any reuse without a DSN)
// stays a no-op; the value is injected per-deployment, never hardcoded.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 10_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* Catch render-time crashes anywhere below the app shell so production users
    see the controlled fallback instead of a blank page. */}
    <AppErrorBoundary>
      <BrowserRouter>
        <ClerkWithRouter>
          <QueryClientProvider client={queryClient}>
            <App />
          </QueryClientProvider>
        </ClerkWithRouter>
      </BrowserRouter>
    </AppErrorBoundary>
  </StrictMode>,
);
