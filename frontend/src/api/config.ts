import { client } from "./generated/client.gen";

// Point the generated SDK at the backend. In production the frontend and API
// live on different origins (separate Render services), so the build injects
// the absolute backend URL via VITE_API_URL. In dev the var is unset, leaving
// baseUrl empty so requests stay relative and Vite's /api proxy forwards them.
client.setConfig({ baseUrl: import.meta.env.VITE_API_URL ?? "" });
