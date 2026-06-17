import { ClerkProvider } from "@clerk/react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

// Auth is required for the whole app, so fail loudly if the key is missing rather
// than rendering a broken sign-in box.
const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!publishableKey) {
  throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY environment variable.");
}

// Route Clerk's own navigations (post sign-in/out redirects) through react-router
// so they stay client-side instead of triggering full page reloads. This must
// render inside <BrowserRouter> so it can use the navigate hook.
export function ClerkWithRouter({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  return (
    <ClerkProvider
      publishableKey={publishableKey}
      afterSignOutUrl="/"
      routerPush={(to) => navigate(to)}
      routerReplace={(to) => navigate(to, { replace: true })}
    >
      {children}
    </ClerkProvider>
  );
}
