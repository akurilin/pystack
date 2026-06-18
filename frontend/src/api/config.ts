import { getToken } from "@clerk/react";

import { client } from "./generated/client.gen";

// Point the generated SDK at the backend. In production the frontend and API
// live on different origins (separate Render services), so the build injects
// the absolute backend URL via VITE_API_URL. In dev the var is unset, leaving
// baseUrl empty so requests stay relative and Vite's /api proxy forwards them.
client.setConfig({ baseUrl: import.meta.env.VITE_API_URL ?? "" });

// Every endpoint requires a signed-in user, so attach the Clerk session token to
// each request. `getToken` is the framework-agnostic accessor — it waits for
// Clerk to initialize and is safe to call here in a plain module (no hook).
client.interceptors.request.use(async (request) => {
  request.headers.set("X-Request-ID", createRequestId());

  const token = await getToken();
  if (token) {
    request.headers.set("Authorization", `Bearer ${token}`);
  }
  return request;
});

function createRequestId(): string {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  // Old browsers are unlikely here, but keep the header present if the native
  // UUID helper is missing.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
