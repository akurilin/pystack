import { fileURLToPath, URL } from "node:url";

import { clerkSetup } from "@clerk/testing/playwright";
import { config } from "dotenv";

// Tests run from frontend/, but secrets live in the repo-root .env (the same file
// the app and backend read), so load it explicitly before validating anything.
config({ path: fileURLToPath(new URL("../../.env", import.meta.url)) });

// The e2e suite drives a real Clerk sign-in, so it needs a Clerk dev instance and
// a test user. These are required, not optional: rather than silently skipping
// (which can hide a broken auth flow), fail the whole suite up front and say
// exactly which variables are missing. Names follow the repo convention:
// VITE_ for the client-exposed publishable key, PYSTACK_ for backend secrets.
const REQUIRED_ENV = [
  "VITE_CLERK_PUBLISHABLE_KEY",
  "PYSTACK_CLERK_SECRET_KEY",
  "E2E_CLERK_USER_USERNAME",
  "E2E_CLERK_USER_PASSWORD",
];

export default async function globalSetup() {
  const missing = REQUIRED_ENV.filter((name) => !process.env[name]);
  if (missing.length > 0) {
    throw new Error(
      `Missing required env vars for the e2e suite: ${missing.join(", ")}.\n` +
        "Create a Clerk dev instance and a test user, then set these (e.g. in the " +
        "repo-root .env) before running 'make test-e2e'.",
    );
  }

  // Fetches a Clerk testing token so the scripted sign-in isn't blocked by Clerk's
  // bot detection. clerkSetup reads VITE_CLERK_PUBLISHABLE_KEY natively but only
  // recognizes the un-prefixed secret name, so pass our PYSTACK_ one explicitly.
  await clerkSetup({ secretKey: process.env.PYSTACK_CLERK_SECRET_KEY });
}
