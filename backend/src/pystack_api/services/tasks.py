from dataclasses import dataclass
from string.templatelib import Template
from typing import cast
from uuid import UUID, uuid4

from psycopg.rows import class_row, scalar_row

from pystack_api.db.connection import DatabaseConnection
from pystack_api.queries import tasks as queries
from pystack_api.schemas import TaskCreate, TaskMove, TaskRead, TaskStatus, TaskUpdate


@dataclass
class DeletedTask:
    """The slot a deleted task vacated, so we can close the gap it leaves behind."""

    status: str
    position: int


def list_tasks(connection: DatabaseConnection) -> list[TaskRead]:
    with connection.cursor(row_factory=class_row(TaskRead)) as cursor:
        cursor.execute(queries.list_tasks_query())
        return cursor.fetchall()


def create_task(connection: DatabaseConnection, payload: TaskCreate) -> TaskRead:
    """Create a task at the bottom of the backlog column."""
    position = _status_count(connection, TaskStatus.BACKLOG.value)
    return create_task_at_position(
        connection,
        title=payload.title,
        description=payload.description,
        status=TaskStatus.BACKLOG.value,
        position=position,
    )


def create_task_at_position(
    connection: DatabaseConnection,
    title: str,
    description: str,
    status: str,
    position: int,
) -> TaskRead:
    task = _fetch_task(
        connection,
        queries.insert_task_query(uuid4(), title, description, status, position),
    )
    assert task is not None
    return task


def update_task(
    connection: DatabaseConnection, task_id: UUID, payload: TaskUpdate
) -> TaskRead | None:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return _get_task(connection, task_id)

    return _fetch_task(connection, queries.update_task_query(task_id, updates))


def move_task(connection: DatabaseConnection, task_id: UUID, payload: TaskMove) -> TaskRead | None:
    task = _get_task(connection, task_id)
    if task is None:
        return None

    old_status = task.status
    old_position = task.position
    target_status = payload.status.value

    # Positions stay contiguous within each column. Pull the source column up to
    # fill the hole the task leaves, then push the target column down to free a
    # slot — clamped so a task can't be dropped past the end of its column.
    connection.execute(queries.close_status_gap_query(old_status, old_position))

    target_position = min(
        payload.position,
        _status_count(connection, target_status, exclude_id=task.id),
    )
    connection.execute(queries.open_status_gap_query(target_status, target_position, task.id))

    return _fetch_task(
        connection,
        queries.move_task_query(task.id, target_status, target_position),
    )


def delete_task(connection: DatabaseConnection, task_id: UUID) -> bool:
    with connection.cursor(row_factory=class_row(DeletedTask)) as cursor:
        cursor.execute(queries.delete_task_query(task_id))
        deleted_task = cursor.fetchone()

    if deleted_task is None:
        return False

    connection.execute(queries.close_status_gap_query(deleted_task.status, deleted_task.position))
    return True


def count_tasks(connection: DatabaseConnection) -> int:
    with connection.cursor(row_factory=scalar_row) as cursor:
        cursor.execute(queries.count_tasks_query())
        return cast(int, next(cursor))


def _get_task(connection: DatabaseConnection, task_id: UUID) -> TaskRead | None:
    return _fetch_task(connection, queries.task_by_id_query(task_id))


def _fetch_task(connection: DatabaseConnection, query: Template) -> TaskRead | None:
    with connection.cursor(row_factory=class_row(TaskRead)) as cursor:
        cursor.execute(query)
        return cursor.fetchone()


def _status_count(
    connection: DatabaseConnection,
    status: str,
    exclude_id: UUID | None = None,
) -> int:
    with connection.cursor(row_factory=scalar_row) as cursor:
        cursor.execute(queries.status_count_query(status, exclude_id))
        return cast(int, next(cursor))
