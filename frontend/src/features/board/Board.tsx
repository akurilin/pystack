import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

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

export function Board() {
  const queryClient = useQueryClient();
  const tasksQuery = useQuery(listTasksOptions());
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);

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
    return <p className="state-message">Loading board...</p>;
  }

  if (tasksQuery.isError) {
    return (
      <p className="state-message state-message--error">
        The board could not be loaded.
      </p>
    );
  }

  return (
    <>
      {mutationFailed && (
        <p className="state-message state-message--error" role="alert">
          That change could not be saved. Please try again.
        </p>
      )}
      <section className="board" aria-label="Task board">
        {COLUMNS.map((column, columnIndex) => {
          const columnTasks = tasks
            .filter((task) => task.status === column.status)
            .sort((left, right) => left.position - right.position);

          return (
            <section
              className={`board-column board-column--${column.status}`}
              key={column.status}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => dropTask(column.status, columnTasks.length)}
            >
              <header className="column-header">
                <span className="column-marker">{column.marker}</span>
                <h2>{column.label}</h2>
                <span className="task-count">{columnTasks.length}</span>
              </header>

              {column.status === "backlog" && (
                <CreateTaskForm
                  isPending={createTask.isPending}
                  onCreate={(title, description) =>
                    createTask.mutate({ body: { title, description } })
                  }
                />
              )}

              <div className="task-list">
                {columnTasks.map((task, position) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    canMoveLeft={columnIndex > 0}
                    canMoveRight={columnIndex < COLUMNS.length - 1}
                    isPending={
                      updateTask.isPending ||
                      moveTask.isPending ||
                      deleteTask.isPending
                    }
                    onDelete={() =>
                      deleteTask.mutate({ path: { task_id: task.id } })
                    }
                    onDragStart={() => setDraggedTaskId(task.id)}
                    onDrop={() => dropTask(column.status, position)}
                    onMoveLeft={() =>
                      move(task.id, COLUMNS[columnIndex - 1].status, 0)
                    }
                    onMoveRight={() =>
                      move(task.id, COLUMNS[columnIndex + 1].status, 0)
                    }
                    onUpdate={(title, description) =>
                      updateTask.mutate({
                        body: { title, description },
                        path: { task_id: task.id },
                      })
                    }
                  />
                ))}
                {columnTasks.length === 0 && (
                  <p className="empty-column">Drop a task here</p>
                )}
              </div>
            </section>
          );
        })}
      </section>
    </>
  );
}

function CreateTaskForm({
  isPending,
  onCreate,
}: {
  isPending: boolean;
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
    <form className="create-task" onSubmit={submit}>
      <label>
        <span>Task title</span>
        <input
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="What needs doing?"
          required
          value={title}
        />
      </label>
      <label>
        <span>Description</span>
        <textarea
          maxLength={5000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Add useful context"
          rows={2}
          value={description}
        />
      </label>
      <button className="primary-button" disabled={isPending} type="submit">
        {isPending ? "Adding..." : "Add task"}
      </button>
    </form>
  );
}

function TaskCard({
  task,
  canMoveLeft,
  canMoveRight,
  isPending,
  onDelete,
  onDragStart,
  onDrop,
  onMoveLeft,
  onMoveRight,
  onUpdate,
}: {
  task: TaskRead;
  canMoveLeft: boolean;
  canMoveRight: boolean;
  isPending: boolean;
  onDelete: () => void;
  onDragStart: () => void;
  onDrop: () => void;
  onMoveLeft: () => void;
  onMoveRight: () => void;
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
      <form className="task-card task-card--editing" onSubmit={submit}>
        <label>
          <span>Task title</span>
          <input
            aria-label={`Title for ${task.title}`}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </label>
        <label>
          <span>Description</span>
          <textarea
            aria-label={`Description for ${task.title}`}
            maxLength={5000}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            value={description}
          />
        </label>
        <div className="card-actions">
          <button className="primary-button" disabled={isPending} type="submit">
            Save
          </button>
          <button
            className="text-button"
            onClick={() => setIsEditing(false)}
            type="button"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <article
      className="task-card"
      draggable
      onDragOver={(event) => event.preventDefault()}
      onDragStart={onDragStart}
      onDrop={(event) => {
        // Stop the column's onDrop from also firing and appending to the end.
        event.stopPropagation();
        onDrop();
      }}
    >
      <div className="task-card__grabber" aria-hidden="true">
        Drag
      </div>
      <h3>{task.title}</h3>
      {task.description !== "" && <p>{task.description}</p>}
      <div className="move-actions">
        <button
          aria-label={`Move ${task.title} left`}
          disabled={!canMoveLeft || isPending}
          onClick={onMoveLeft}
          type="button"
        >
          Previous
        </button>
        <button
          aria-label={`Move ${task.title} right`}
          disabled={!canMoveRight || isPending}
          onClick={onMoveRight}
          type="button"
        >
          Next
        </button>
      </div>
      <div className="card-actions">
        <button
          className="text-button"
          onClick={() => setIsEditing(true)}
          type="button"
        >
          Edit
        </button>
        <button
          className="text-button text-button--danger"
          onClick={onDelete}
          type="button"
        >
          Delete
        </button>
      </div>
    </article>
  );
}
