import { PointerEvent, useState } from "react";

import { AssistantPane } from "./features/assistant/AssistantPane";
import { Board } from "./features/board/Board";

const MIN_ASSISTANT_WIDTH = 320;
const MAX_ASSISTANT_WIDTH = 620;
const DEFAULT_ASSISTANT_WIDTH = 420;

export function App() {
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [assistantWidth, setAssistantWidth] = useState(DEFAULT_ASSISTANT_WIDTH);

  const startResize = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const pointerId = event.pointerId;
    const handle = event.currentTarget;
    handle.setPointerCapture(pointerId);

    const resize = (moveEvent: globalThis.PointerEvent) => {
      const viewportWidth = window.innerWidth;
      const nextWidth = viewportWidth - moveEvent.clientX;
      setAssistantWidth(
        Math.min(MAX_ASSISTANT_WIDTH, Math.max(MIN_ASSISTANT_WIDTH, nextWidth)),
      );
    };

    const stopResize = () => {
      handle.releasePointerCapture(pointerId);
      window.removeEventListener("pointermove", resize);
      window.removeEventListener("pointerup", stopResize);
    };

    window.addEventListener("pointermove", resize);
    window.addEventListener("pointerup", stopResize);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Pystack smoke test</p>
          <h1>Product launch board</h1>
        </div>
        <div className="header-actions">
          <p className="header-note">
            Drag tasks between columns or use the arrow controls.
          </p>
          <button
            className="assistant-toggle"
            onClick={() => setAssistantOpen((isOpen) => !isOpen)}
            type="button"
          >
            {assistantOpen ? "Hide assistant" : "Show assistant"}
          </button>
        </div>
      </header>
      <div className="workspace">
        <section className="board-workspace" aria-label="Board workspace">
          <Board />
        </section>
        {assistantOpen && (
          <>
            <button
              aria-label="Resize assistant pane"
              className="assistant-resize-handle"
              onPointerDown={startResize}
              type="button"
            />
            <div
              className="assistant-pane-wrap"
              style={{ width: assistantWidth }}
            >
              <AssistantPane />
            </div>
          </>
        )}
      </div>
    </main>
  );
}
