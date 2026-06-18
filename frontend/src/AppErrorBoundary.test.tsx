import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { AppErrorBoundary } from "./AppErrorBoundary";

const sentry = vi.hoisted(() => ({
  captureException: vi.fn(),
}));

vi.mock("@sentry/react", () => ({
  captureException: sentry.captureException,
}));

function BrokenChild(): ReactNode {
  throw new Error("private crash detail");
}

beforeEach(() => {
  sentry.captureException.mockClear();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("shows a generic fallback and reports render errors", () => {
  render(
    <AppErrorBoundary>
      <BrokenChild />
    </AppErrorBoundary>,
  );

  expect(
    screen.getByRole("heading", { name: "Something went wrong" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Reload page" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("private crash detail")).not.toBeInTheDocument();
  expect(sentry.captureException).toHaveBeenCalledWith(
    expect.any(Error),
    expect.objectContaining({
      contexts: expect.objectContaining({
        react: expect.objectContaining({
          componentStack: expect.any(String),
        }),
      }),
    }),
  );
});
