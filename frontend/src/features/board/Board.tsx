import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import {
  CircleAlert,
  GripHorizontal,
  LoaderCircle,
  Pencil,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  createTaskMutation,
  deleteTaskMutation,
  listTasksOptions,
  listTasksQueryKey,
  moveTaskMutation,
  updateTaskMutation,
} from "../../api/generated/@tanstack/react-query.gen";
import type { TaskRead, TaskStatus } from "../../api/generated/types.gen";

const COLUMNS: ReadonlyArray<{
  status: TaskStatus;
  label: string;
  marker: string;
}> = [
  { status: "backlog", label: "Backlog", marker: "01" },
  { status: "ready", label: "Ready", marker: "02" },
  { status: "in_progress", label: "In progress", marker: "03" },
  { status: "review", label: "Review", marker: "04" },
  { status: "done", label: "Done", marker: "05" },
];

const STATUS_MARKER_CLASSES: Record<TaskStatus, string> = {
  backlog: "bg-sky-500/10 text-sky-300 ring-sky-500/25",
  ready: "bg-violet-500/10 text-violet-300 ring-violet-500/25",
  in_progress: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  review: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  done: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
};

export function Board() {
  const queryClient = useQueryClient();
  const tasksQuery = useQuery(listTasksOptions());
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const [isCreateTaskOpen, setIsCreateTaskOpen] = useState(false);

  const refreshTasks = async () => {
    await queryClient.invalidateQueries({ queryKey: listTasksQueryKey() });
  };

  const createTask = useMutation({
    ...createTaskMutation(),
    onSuccess: refreshTasks,
  });
  const updateTask = useMutation({
    ...updateTaskMutation(),
    onSuccess: refreshTasks,
  });
  const moveTask = useMutation({
    ...moveTaskMutation(),
    onSuccess: refreshTasks,
  });
  const deleteTask = useMutation({
    ...deleteTaskMutation(),
    onSuccess: refreshTasks,
  });

  const tasks = tasksQuery.data ?? [];
  const mutationFailed =
    createTask.isError ||
    updateTask.isError ||
    moveTask.isError ||
    deleteTask.isError;

  const move = (taskId: string, status: TaskStatus, position: number) => {
    moveTask.mutate({
      body: { status, position },
      path: { task_id: taskId },
    });
  };

  // Dropping on a card inserts at that card's position; dropping on the column's
  // empty space (see onDrop below) appends to the end.
  const dropTask = (status: TaskStatus, position: number) => {
    if (draggedTaskId !== null) {
      move(draggedTaskId, status, position);
      setDraggedTaskId(null);
    }
  };

  if (tasksQuery.isPending) {
    return (
      <Alert className="bg-card/80">
        <LoaderCircle className="animate-spin" />
        <AlertDescription>Loading board...</AlertDescription>
      </Alert>
    );
  }

  if (tasksQuery.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertDescription>The board could not be loaded.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid min-w-0 gap-3">
      {mutationFailed && (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertDescription>
            That change could not be saved. Please try again.
          </AlertDescription>
        </Alert>
      )}
      <section
        aria-label="Task board"
        className="grid min-w-0 grid-cols-[repeat(5,minmax(11.5rem,1fr))] gap-3 overflow-x-auto pb-4 max-[900px]:grid-cols-[repeat(5,minmax(280px,82vw))]"
      >
        {COLUMNS.map((column) => {
          const columnTasks = tasks
            .filter((task) => task.status === column.status)
            .sort((left, right) => left.position - right.position);
          const showCreateTaskForm =
            column.status === "backlog" && isCreateTaskOpen;

          return (
            <section
              className="min-h-[65vh] rounded-xl border border-border/80 bg-card/85 p-3 shadow-2xl shadow-black/15"
              key={column.status}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => dropTask(column.status, columnTasks.length)}
            >
              <header className="mb-3 grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-border/70 px-1 pb-3">
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full text-[0.68rem] font-semibold ring-1",
                    STATUS_MARKER_CLASSES[column.status],
                  )}
                >
                  {column.marker}
                </span>
                <h2 className="text-xs font-semibold uppercase text-foreground">
                  {column.label}
                </h2>
                <Badge variant="outline">{columnTasks.length}</Badge>
              </header>

              <div className="grid min-h-32 content-start gap-3">
                {columnTasks.map((task, position) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    isPending={updateTask.isPending || deleteTask.isPending}
                    onDelete={() =>
                      deleteTask.mutate({ path: { task_id: task.id } })
                    }
                    onDragStart={() => setDraggedTaskId(task.id)}
                    onDrop={() => dropTask(column.status, position)}
                    onUpdate={(title, description) =>
                      updateTask.mutate({
                        body: { title, description },
                        path: { task_id: task.id },
                      })
                    }
                  />
                ))}
                {showCreateTaskForm && (
                  <CreateTaskForm
                    isPending={createTask.isPending}
                    onCancel={() => setIsCreateTaskOpen(false)}
                    onCreate={(title, description) =>
                      createTask.mutate(
                        { body: { title, description } },
                        { onSuccess: () => setIsCreateTaskOpen(false) },
                      )
                    }
                  />
                )}
                {columnTasks.length === 0 && !showCreateTaskForm && (
                  <p className="rounded-lg border border-dashed border-border/80 px-3 py-6 text-center text-xs text-muted-foreground">
                    Drop a task here
                  </p>
                )}
                {column.status === "backlog" && !showCreateTaskForm && (
                  <Button
                    className="h-auto w-full justify-start px-2 py-2 text-muted-foreground"
                    onClick={() => setIsCreateTaskOpen(true)}
                    type="button"
                    variant="ghost"
                  >
                    <Plus data-icon="inline-start" />
                    Add task
                  </Button>
                )}
              </div>
            </section>
          );
        })}
      </section>
    </div>
  );
}

function CreateTaskForm({
  isPending,
  onCancel,
  onCreate,
}: {
  isPending: boolean;
  onCancel: () => void;
  onCreate: (title: string, description: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (title.trim() === "") {
      return;
    }
    onCreate(title.trim(), description.trim());
    setTitle("");
    setDescription("");
  };

  return (
    <form
      aria-label="Create task"
      className="grid gap-3 rounded-xl border border-border bg-card/90 p-3"
      onSubmit={submit}
    >
      <div className="grid gap-1.5">
        <Label className="text-xs font-semibold uppercase" htmlFor="task-title">
          Task title
        </Label>
        <Input
          autoFocus
          id="task-title"
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="What needs doing?"
          required
          value={title}
        />
      </div>
      <div className="grid gap-1.5">
        <Label
          className="text-xs font-semibold uppercase"
          htmlFor="task-description"
        >
          Description
        </Label>
        <Textarea
          id="task-description"
          maxLength={5000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Add useful context"
          rows={2}
          value={description}
        />
      </div>
      <div className="flex gap-2">
        <Button disabled={isPending} type="submit">
          {isPending ? (
            <LoaderCircle className="animate-spin" data-icon="inline-start" />
          ) : (
            <Plus data-icon="inline-start" />
          )}
          {isPending ? "Adding..." : "Add task"}
        </Button>
        <Button onClick={onCancel} type="button" variant="outline">
          <X data-icon="inline-start" />
          Cancel
        </Button>
      </div>
    </form>
  );
}

function TaskCard({
  task,
  isPending,
  onDelete,
  onDragStart,
  onDrop,
  onUpdate,
}: {
  task: TaskRead;
  isPending: boolean;
  onDelete: () => void;
  onDragStart: () => void;
  onDrop: () => void;
  onUpdate: (title: string, description: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (title.trim() !== "") {
      onUpdate(title.trim(), description.trim());
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <form
        aria-label={`Edit ${task.title}`}
        className="grid gap-3 rounded-xl border border-border bg-card p-3 shadow-lg shadow-black/10"
        onSubmit={submit}
      >
        <div className="grid gap-1.5">
          <Label
            className="text-xs font-semibold uppercase"
            htmlFor={`task-title-${task.id}`}
          >
            Task title
          </Label>
          <Input
            aria-label={`Title for ${task.title}`}
            id={`task-title-${task.id}`}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </div>
        <div className="grid gap-1.5">
          <Label
            className="text-xs font-semibold uppercase"
            htmlFor={`task-description-${task.id}`}
          >
            Description
          </Label>
          <Textarea
            aria-label={`Description for ${task.title}`}
            id={`task-description-${task.id}`}
            maxLength={5000}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            value={description}
          />
        </div>
        <div className="flex gap-2">
          <Button disabled={isPending} type="submit">
            <Save data-icon="inline-start" />
            Save
          </Button>
          <Button
            onClick={() => setIsEditing(false)}
            type="button"
            variant="outline"
          >
            <X data-icon="inline-start" />
            Cancel
          </Button>
        </div>
      </form>
    );
  }

  return (
    <article
      aria-label={`Task ${task.title}`}
      className="grid cursor-grab gap-3 rounded-xl border border-border bg-card p-3 shadow-lg shadow-black/10 active:cursor-grabbing"
      draggable
      onDragOver={(event) => event.preventDefault()}
      onDragStart={onDragStart}
      onDrop={(event) => {
        // Stop the column's onDrop from also firing and appending to the end.
        event.stopPropagation();
        onDrop();
      }}
    >
      <div
        className="flex items-center gap-1 text-[0.65rem] font-semibold uppercase text-muted-foreground"
        aria-hidden="true"
      >
        <GripHorizontal className="size-3" />
        Drag
      </div>
      <h3 className="text-sm leading-5 font-medium text-foreground">
        {task.title}
      </h3>
      {task.description !== "" && (
        <p className="text-xs leading-5 text-muted-foreground">
          {task.description}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          onClick={() => setIsEditing(true)}
          size="xs"
          type="button"
          variant="outline"
        >
          <Pencil data-icon="inline-start" />
          Edit
        </Button>
        <Button
          className="ml-auto"
          disabled={isPending}
          onClick={onDelete}
          size="xs"
          type="button"
          variant="destructive"
        >
          <Trash2 data-icon="inline-start" />
          Delete
        </Button>
      </div>
    </article>
  );
}
