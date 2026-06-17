import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive the real frontend against the real backend and the
// local development database. `make test-e2e` migrates that database first;
// Playwright then starts (or reuses) both dev servers below.
export default defineConfig({
  testDir: "./e2e",
  // Validates required Clerk env vars and fetches a Clerk testing token before
  // the suite; fails fast with a clear message if anything is missing.
  globalSetup: "./e2e/global-setup.ts",
  // Test artifacts (traces, screenshots) are ephemeral; keep them out of the
  // repo. The list reporter prints results to stdout, so nothing else is
  // written here.
  outputDir: join(tmpdir(), "pystack-playwright"),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "uv run --directory ../backend uvicorn pystack_api.main:app --port 8000",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
