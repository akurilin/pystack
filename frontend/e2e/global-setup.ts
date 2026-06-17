import { clerkSetup } from "@clerk/testing/playwright";

// Fetches a Clerk testing token so e2e runs bypass bot protection on the sign-in
// flow. Requires CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY (a Clerk dev
// instance) in the environment. When they're absent the auth-gated spec skips
// itself, so this setup no-ops rather than failing the run.
export default async function globalSetup() {
  if (!process.env.CLERK_PUBLISHABLE_KEY || !process.env.CLERK_SECRET_KEY) {
    return;
  }
  await clerkSetup();
}
