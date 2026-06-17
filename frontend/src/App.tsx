import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AssistantPane } from "./features/assistant/AssistantPane";
import { Board } from "./features/board/Board";

export function App() {
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
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                Pystack smoke test
              </p>
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
