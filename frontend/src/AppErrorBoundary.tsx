import * as Sentry from "@sentry/react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

// Top-level crash guard for React render failures. It keeps an unexpected
// component error from blanking the whole SPA and sends the details to Sentry
// while the user sees only the generic fallback below.
type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  hasError: boolean;
};

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo.componentStack,
        },
      },
    });
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main className="grid min-h-screen place-items-center px-4 py-8 text-foreground">
        <section
          aria-labelledby="app-error-title"
          className="grid w-full max-w-md justify-items-center gap-5 text-center"
        >
          <div className="grid size-12 place-items-center rounded-full border border-destructive/30 bg-destructive/10 text-destructive">
            <AlertTriangle aria-hidden="true" className="size-6" />
          </div>
          <div className="grid gap-2">
            <h1
              className="text-3xl leading-tight font-semibold"
              id="app-error-title"
            >
              Something went wrong
            </h1>
            <p className="text-sm leading-6 text-muted-foreground">
              Refresh the page and try again.
            </p>
          </div>
          <Button onClick={() => window.location.reload()} type="button">
            <RotateCcw data-icon="inline-start" />
            Reload page
          </Button>
        </section>
      </main>
    );
  }
}
