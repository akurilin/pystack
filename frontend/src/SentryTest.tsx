import { Button } from "@/components/ui/button";

// Throwaway verification page at /sentry-test. Clicking the button throws an
// uncaught error; React re-throws event-handler errors to the browser, where
// Sentry's global handler captures and reports it. Use this once to confirm the
// DSN is wired up, then it can be removed.
export function SentryTest() {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8 text-foreground">
      <div className="grid w-full max-w-sm justify-items-center gap-4 text-center">
        <h1 className="text-2xl font-semibold">Sentry test</h1>
        <p className="text-sm text-muted-foreground">
          Clicking below throws an uncaught error for Sentry to capture.
        </p>
        <Button
          onClick={() => {
            throw new Error("This is your first error!");
          }}
          type="button"
          variant="destructive"
        >
          Break the world
        </Button>
      </div>
    </main>
  );
}
