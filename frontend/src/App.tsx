import { Board } from "./features/board/Board";

export function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Pystack smoke test</p>
          <h1>Product launch board</h1>
        </div>
        <p className="header-note">
          Drag tasks between columns or use the arrow controls.
        </p>
      </header>
      <Board />
    </main>
  );
}
