from collections.abc import Callable, Mapping
from dataclasses import dataclass
from string.templatelib import Template
from uuid import UUID

from psycopg import sql


def list_tasks_query() -> Template:
    return t"""
        SELECT id, title, description, status, position, created_at, updated_at
        FROM tasks
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


def task_by_id_query(task_id: UUID) -> Template:
    return t"""
        SELECT id, title, description, status, position, created_at, updated_at
        FROM tasks
        WHERE id = {task_id}
    """


def count_tasks_query() -> Template:
    return t"SELECT count(*) FROM tasks"


def status_count_query(status: str, exclude_id: UUID | None = None) -> Template:
    return t"""
        SELECT count(*)
        FROM tasks
        WHERE status = {status}
          AND ({exclude_id}::uuid IS NULL OR id != {exclude_id})
    """


def insert_task_query(
    task_id: UUID,
    title: str,
    description: str,
    status: str,
    position: int,
) -> Template:
    return t"""
        INSERT INTO tasks (id, title, description, status, position)
        VALUES ({task_id}, {title}, {description}, {status}, {position})
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def update_task_query(task_id: UUID, updates: Mapping[str, object]) -> Template:
    assignments = [t"{column:i} = {value}" for column, value in updates.items()]
    assignments.append(t"updated_at = now()")
    joined_assignments = sql.SQL(", ").join(assignments)

    return t"""
        UPDATE tasks
        SET {joined_assignments:q}
        WHERE id = {task_id}
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def close_status_gap_query(status: str, position: int) -> Template:
    return t"""
        UPDATE tasks
        SET position = position - 1, updated_at = now()
        WHERE status = {status} AND position > {position}
    """


def open_status_gap_query(status: str, position: int, exclude_id: UUID) -> Template:
    return t"""
        UPDATE tasks
        SET position = position + 1, updated_at = now()
        WHERE status = {status} AND position >= {position} AND id != {exclude_id}
    """


def move_task_query(task_id: UUID, status: str, position: int) -> Template:
    return t"""
        UPDATE tasks
        SET status = {status}, position = {position}, updated_at = now()
        WHERE id = {task_id}
        RETURNING id, title, description, status, position, created_at, updated_at
    """


def delete_task_query(task_id: UUID) -> Template:
    return t"""
        DELETE FROM tasks
        WHERE id = {task_id}
        RETURNING status, position
    """


@dataclass(frozen=True)
class QueryCheck:
    name: str
    builder: Callable[..., Template]
    build: Callable[[], Template]


_EXAMPLE_ID = UUID(int=0)

QUERY_CHECKS = (
    QueryCheck("tasks.list", list_tasks_query, list_tasks_query),
    QueryCheck("tasks.by_id", task_by_id_query, lambda: task_by_id_query(_EXAMPLE_ID)),
    QueryCheck("tasks.count", count_tasks_query, count_tasks_query),
    QueryCheck(
        "tasks.status_count",
        status_count_query,
        lambda: status_count_query("backlog", _EXAMPLE_ID),
    ),
    QueryCheck(
        "tasks.insert",
        insert_task_query,
        lambda: insert_task_query(_EXAMPLE_ID, "Example", "", "backlog", 0),
    ),
    QueryCheck(
        "tasks.update",
        update_task_query,
        lambda: update_task_query(_EXAMPLE_ID, {"title": "Example", "description": ""}),
    ),
    QueryCheck(
        "tasks.close_status_gap",
        close_status_gap_query,
        lambda: close_status_gap_query("backlog", 0),
    ),
    QueryCheck(
        "tasks.open_status_gap",
        open_status_gap_query,
        lambda: open_status_gap_query("backlog", 0, _EXAMPLE_ID),
    ),
    QueryCheck("tasks.move", move_task_query, lambda: move_task_query(_EXAMPLE_ID, "done", 0)),
    QueryCheck("tasks.delete", delete_task_query, lambda: delete_task_query(_EXAMPLE_ID)),
)
