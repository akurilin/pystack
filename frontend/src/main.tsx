import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ClerkWithRouter } from "./auth/ClerkWithRouter";
// Side-effect import: configures the generated API client's base URL and attaches
// the Clerk session token to every request before any component issues one.
import "./api/config";
import "./styles.css";

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
    <BrowserRouter>
      <ClerkWithRouter>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </ClerkWithRouter>
    </BrowserRouter>
  </StrictMode>,
);
