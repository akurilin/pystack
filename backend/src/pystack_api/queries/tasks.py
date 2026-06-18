from collections.abc import Callable, Mapping
from dataclasses import dataclass
from string.templatelib import Template
from uuid import UUID

from psycopg import sql

# Every query is scoped by ``user_id`` (the Clerk user id) so a request can only
# ever read or change rows the authenticated user owns. The id is supplied by the
# auth dependency, never by the client.


def list_tasks_query(user_id: str) -> Template:
    """Fetch the user's tasks ordered by board column (left to right), then position."""
    return t"""
        SELECT id, title, description, status, position, created_at, updated_at
        FROM tasks
        WHERE user_id = {user_id}
        ORDER BY
            CASE status
                WHEN 'backlog' THEN 0
                WHEN 'ready' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'review' THEN 3
                WHEN 'done' THEN 4
            END,
            position,
            created_at
    """


def task_by_id_query(task_id: UUID, user_id: str) -> Template:
    return t"""
        SELECT id, title, description, status, position, created_at, updated_at
        FROM tasks
        WHERE id = {task_id} AND user_id = {user_id}
    """


def count_tasks_query(user_id: str) -> Template:
    return t"SELECT count(*) FROM tasks WHERE user_id = {user_id}"


def lock_user_board_query(user_id: str) -> Template:
    """Serialize position mutations for one user's board within the transaction."""
    return t"SELECT pg_advisory_xact_lock(hashtextextended({user_id}, 0))"


def status_count_query(status: str, user_id: str, exclude_id: UUID | None = None) -> Template:
    """Count tasks in a column, optionally ignoring one task.

    Callers exclude the task being moved so its own row doesn't inflate the
    count when computing a clamped target position.
    """
    return t"""
        SELECT count(*)
        FROM tasks
        WHERE status = {status}
          AND user_id = {user_id}
          AND ({exclude_id}::uuid IS NULL OR id != {exclude_id})
    """


def insert_task_query(
    task_id: UUID,
    user_id: str,
    title: str,
    description: str,
    status: str,
    position: int,
) -> Template:
    return t"""
        INSERT INTO tasks (id, user_id, title, description, status, position)
        VALUES ({task_id}, {user_id}, {title}, {description}, {status}, {position})
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def update_task_query(task_id: UUID, user_id: str, updates: Mapping[str, object]) -> Template:
    """Update only the columns present in ``updates``.

    ``{column:i}`` renders each key as a SQL identifier and ``{value}`` as a
    bound parameter; ``{joined_assignments:q}`` splices the pre-composed SET
    clause back into the template as literal SQL.
    """
    assignments = [t"{column:i} = {value}" for column, value in updates.items()]
    assignments.append(t"updated_at = now()")
    joined_assignments = sql.SQL(", ").join(assignments)

    return t"""
        UPDATE tasks
        SET {joined_assignments:q}
        WHERE id = {task_id} AND user_id = {user_id}
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def close_status_gap_query(status: str, user_id: str, position: int) -> Template:
    return t"""
        UPDATE tasks
        SET position = position - 1, updated_at = now()
        WHERE user_id = {user_id} AND status = {status} AND position > {position}
    """


def open_status_gap_query(status: str, user_id: str, position: int, exclude_id: UUID) -> Template:
    return t"""
        UPDATE tasks
        SET position = position + 1, updated_at = now()
        WHERE user_id = {user_id}
          AND status = {status}
          AND position >= {position}
          AND id != {exclude_id}
    """


def move_task_query(task_id: UUID, user_id: str, status: str, position: int) -> Template:
    return t"""
        UPDATE tasks
        SET status = {status}, position = {position}, updated_at = now()
        WHERE id = {task_id} AND user_id = {user_id}
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def delete_task_query(task_id: UUID, user_id: str) -> Template:
    return t"""
        DELETE FROM tasks
        WHERE id = {task_id} AND user_id = {user_id}
        RETURNING status, position
    """


@dataclass(frozen=True)
class QueryCheck:
    """A query builder paired with a way to invoke it with sample arguments.

    ``builder`` is the bare function (used by tests to verify every builder is
    registered here); ``build`` produces a concrete query the test suite can
    EXPLAIN against the real schema to catch SQL that drifts from the tables.
    """

    name: str
    builder: Callable[..., Template]
    build: Callable[[], Template]


_EXAMPLE_ID = UUID(int=0)
_EXAMPLE_USER = "user_example"

# Every ``*_query`` builder must appear here so the schema-check test exercises it.
QUERY_CHECKS = (
    QueryCheck("tasks.list", list_tasks_query, lambda: list_tasks_query(_EXAMPLE_USER)),
    QueryCheck(
        "tasks.by_id",
        task_by_id_query,
        lambda: task_by_id_query(_EXAMPLE_ID, _EXAMPLE_USER),
    ),
    QueryCheck("tasks.count", count_tasks_query, lambda: count_tasks_query(_EXAMPLE_USER)),
    QueryCheck(
        "tasks.lock_user_board",
        lock_user_board_query,
        lambda: lock_user_board_query(_EXAMPLE_USER),
    ),
    QueryCheck(
        "tasks.status_count",
        status_count_query,
        lambda: status_count_query("backlog", _EXAMPLE_USER, _EXAMPLE_ID),
    ),
    QueryCheck(
        "tasks.insert",
        insert_task_query,
        lambda: insert_task_query(_EXAMPLE_ID, _EXAMPLE_USER, "Example", "", "backlog", 0),
    ),
    QueryCheck(
        "tasks.update",
        update_task_query,
        lambda: update_task_query(_EXAMPLE_ID, _EXAMPLE_USER, {"title": "Example"}),
    ),
    QueryCheck(
        "tasks.close_status_gap",
        close_status_gap_query,
        lambda: close_status_gap_query("backlog", _EXAMPLE_USER, 0),
    ),
    QueryCheck(
        "tasks.open_status_gap",
        open_status_gap_query,
        lambda: open_status_gap_query("backlog", _EXAMPLE_USER, 0, _EXAMPLE_ID),
    ),
    QueryCheck(
        "tasks.move",
        move_task_query,
        lambda: move_task_query(_EXAMPLE_ID, _EXAMPLE_USER, "done", 0),
    ),
    QueryCheck(
        "tasks.delete",
        delete_task_query,
        lambda: delete_task_query(_EXAMPLE_ID, _EXAMPLE_USER),
    ),
)
