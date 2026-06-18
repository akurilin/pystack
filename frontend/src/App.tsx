import { Show, SignIn, UserButton } from "@clerk/react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AssistantPane } from "./features/assistant/AssistantPane";
import { Board } from "./features/board/Board";
import { SentryTest } from "./SentryTest";

// The public landing (with the login box) lives at "/", separate from the
// internal app at "/board". Only the landing is public; "/board" is gated, so
// signed-out visitors are bounced back to the landing.
export function App() {
  return (
    <Routes>
      <Route path="/" element={<SignInLanding />} />
      <Route path="/board" element={<ProtectedBoard />} />
      {/* Throwaway page for verifying Sentry error capture; safe to remove. */}
      <Route path="/sentry-test" element={<SentryTest />} />
      {/* Unknown paths fall back to the landing. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function SignInLanding() {
  // Shown to everyone. When the visitor already has a session, Clerk's <SignIn>
  // surfaces a "continue" affordance that routes them on to /board.
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8 text-foreground">
      <div className="grid w-full max-w-sm justify-items-center gap-6">
        <div className="text-center">
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
            Pystack
          </p>
          <h1 className="text-3xl leading-none font-semibold text-balance">
            Your personal board
          </h1>
        </div>
        <SignIn fallbackRedirectUrl="/board" />
      </div>
    </main>
  );
}

// `<Show>` renders null while auth is still resolving, so the board and the
// redirect never flash before Clerk knows whether there's a session.
function ProtectedBoard() {
  return (
    <>
      <Show when="signed-in">
        <BoardApp />
      </Show>
      <Show when="signed-out">
        <Navigate to="/" replace />
      </Show>
    </>
  );
}

function BoardApp() {
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [isNarrow, setIsNarrow] = useState(false);

  useEffect(() => {
    if (!("matchMedia" in window)) {
      return;
    }

    const media = window.matchMedia("(max-width: 900px)");
    const updateLayout = () => setIsNarrow(media.matches);
    updateLayout();
    media.addEventListener("change", updateLayout);

    return () => media.removeEventListener("change", updateLayout);
  }, []);

  const ToggleIcon = assistantOpen ? PanelRightClose : PanelRightOpen;

  return (
    <TooltipProvider>
      <main className="min-h-screen px-4 py-8 text-foreground sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-8">
          <header className="flex items-end justify-between gap-6 max-[900px]:flex-col max-[900px]:items-start">
            <div className="min-w-0">
              <h1 className="text-4xl leading-none font-semibold text-balance sm:text-6xl lg:text-7xl">
                Product launch board
              </h1>
            </div>
            <div className="flex items-center gap-3 max-[900px]:w-full max-[900px]:flex-col max-[900px]:items-start">
              <p className="max-w-md text-sm leading-6 text-muted-foreground">
                Drag tasks between columns or use the card controls.
              </p>
              <Button
                className="max-[900px]:w-full"
                onClick={() => setAssistantOpen((isOpen) => !isOpen)}
                type="button"
                variant="outline"
              >
                <ToggleIcon data-icon="inline-start" />
                {assistantOpen ? "Hide assistant" : "Show assistant"}
              </Button>
              <UserButton />
            </div>
          </header>

          {isNarrow ? (
            <div className="grid gap-3">
              <section aria-label="Board workspace" className="min-w-0">
                <Board />
              </section>
              {assistantOpen && <AssistantPane />}
            </div>
          ) : (
            <ResizablePanelGroup
              className="min-h-[68vh] min-w-0 gap-3"
              orientation="horizontal"
            >
              <ResizablePanel
                className="min-w-0 overflow-hidden"
                defaultSize={assistantOpen ? "72%" : "100%"}
                minSize="35%"
              >
                <section
                  aria-label="Board workspace"
                  className="h-full min-w-0"
                >
                  <Board />
                </section>
              </ResizablePanel>
              {assistantOpen && (
                <>
                  <ResizableHandle
                    className="rounded-full bg-border/70 transition-colors hover:bg-primary/60 focus-visible:bg-primary/60"
                    withHandle
                  />
                  <ResizablePanel
                    className="min-w-0"
                    defaultSize="28%"
                    maxSize="38.75rem"
                    minSize="20rem"
                  >
                    <AssistantPane />
                  </ResizablePanel>
                </>
              )}
            </ResizablePanelGroup>
          )}
        </div>
      </main>
    </TooltipProvider>
  );
}
