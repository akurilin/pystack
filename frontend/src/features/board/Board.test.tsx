import {
  QueryClient,
  QueryClientProvider,
  queryOptions,
} from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskRead, TaskStatus } from "../../api/generated/types.gen";
import { Board } from "./Board";

const api = vi.hoisted(() => ({
  tasks: [] as TaskRead[],
}));

vi.mock("../../api/generated/@tanstack/react-query.gen", () => ({
  listTasksQueryKey: () => ["tasks"],
  listTasksOptions: () =>
    queryOptions({
      queryKey: ["tasks"],
      queryFn: async () => [...api.tasks],
    }),
  createTaskMutation: () => ({
    mutationFn: async ({
      body,
    }: {
      body: { title: string; description?: string };
    }) => {
      const task = makeTask(
        body.title,
        "backlog",
        api.tasks.length,
        body.description,
      );
      api.tasks.push(task);
      return task;
    },
  }),
  updateTaskMutation: () => ({
    mutationFn: async ({
      body,
      path,
    }: {
      body: { title?: string; description?: string };
      path: { task_id: string };
    }) => {
      const task = api.tasks.find(
        (candidate) => candidate.id === path.task_id,
      )!;
      Object.assign(task, body);
      return task;
    },
  }),
  moveTaskMutation: () => ({
    mutationFn: async ({
      body,
      path,
    }: {
      body: { status: TaskStatus; position: number };
      path: { task_id: string };
    }) => {
      const task = api.tasks.find(
        (candidate) => candidate.id === path.task_id,
      )!;
      task.status = body.status;
      task.position = body.position;
      return task;
    },
  }),
  deleteTaskMutation: () => ({
    mutationFn: async ({ path }: { path: { task_id: string } }) => {
      api.tasks = api.tasks.filter((task) => task.id !== path.task_id);
    },
  }),
}));

function makeTask(
  title: string,
  status: TaskStatus = "backlog",
  position = 0,
  description = "",
): TaskRead {
  return {
    id: `${title}-${position}`,
    title,
    description,
    status,
    position,
    created_at: "2026-06-15T00:00:00Z",
    updated_at: "2026-06-15T00:00:00Z",
  };
}

function renderBoard() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <Board />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.tasks = [];
});

describe("Board", () => {
  it("creates a task in the backlog", async () => {
    const user = userEvent.setup();
    renderBoard();

    await user.type(
      await screen.findByLabelText("Task title"),
      "Write release notes",
    );
    await user.type(
      screen.getByLabelText("Description"),
      "Capture the important changes",
    );
    await user.click(screen.getByRole("button", { name: "Add task" }));

    expect(await screen.findByText("Write release notes")).toBeInTheDocument();
    expect(
      screen.getByText("Capture the important changes"),
    ).toBeInTheDocument();
  });

  it("moves a task to the next column", async () => {
    api.tasks = [makeTask("Move me")];
    const user = userEvent.setup();
    renderBoard();

    await user.click(
      await screen.findByRole("button", { name: "Move Move me right" }),
    );

    const readyColumn = screen
      .getByRole("heading", { name: "Ready" })
      .closest("section")!;
    expect(await within(readyColumn).findByText("Move me")).toBeInTheDocument();
  });

  it("edits and deletes a task", async () => {
    api.tasks = [makeTask("Original")];
    const user = userEvent.setup();
    renderBoard();

    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const title = screen.getByLabelText("Title for Original");
    await user.clear(title);
    await user.type(title, "Revised");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Revised")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(screen.queryByText("Revised")).not.toBeInTheDocument(),
    );
  });
});
