from dataclasses import dataclass
from string.templatelib import Template
from typing import cast
from uuid import UUID, uuid4

from psycopg.rows import class_row, scalar_row

from pystack_api.db.connection import DatabaseConnection
from pystack_api.queries import tasks as queries
from pystack_api.schemas import TaskCreate, TaskMove, TaskRead, TaskStatus, TaskUpdate

# Every operation is scoped to ``user_id`` (the authenticated Clerk user) so a
# user only ever sees and mutates their own board.


@dataclass
class DeletedTask:
    """The slot a deleted task vacated, so we can close the gap it leaves behind."""

    status: str
    position: int


def list_tasks(connection: DatabaseConnection, user_id: str) -> list[TaskRead]:
    with connection.cursor(row_factory=class_row(TaskRead)) as cursor:
        cursor.execute(queries.list_tasks_query(user_id))
        return cursor.fetchall()


def create_task(connection: DatabaseConnection, user_id: str, payload: TaskCreate) -> TaskRead:
    """Create a task at the bottom of the backlog column."""
    _lock_user_board(connection, user_id)
    position = _status_count(connection, user_id, TaskStatus.BACKLOG.value)
    return create_task_at_position(
        connection,
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        status=TaskStatus.BACKLOG.value,
        position=position,
    )


def create_task_at_position(
    connection: DatabaseConnection,
    user_id: str,
    title: str,
    description: str,
    status: str,
    position: int,
) -> TaskRead:
    task = _fetch_task(
        connection,
        queries.insert_task_query(uuid4(), user_id, title, description, status, position),
    )
    # INSERT ... RETURNING always yields the new row; guard for the type checker
    # (and so the failure is explicit rather than an AssertionError stripped by -O).
    if task is None:
        raise RuntimeError("INSERT did not return the created task")
    return task


def update_task(
    connection: DatabaseConnection, user_id: str, task_id: UUID, payload: TaskUpdate
) -> TaskRead | None:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return _get_task(connection, user_id, task_id)

    return _fetch_task(connection, queries.update_task_query(task_id, user_id, updates))


def move_task(
    connection: DatabaseConnection, user_id: str, task_id: UUID, payload: TaskMove
) -> TaskRead | None:
    _lock_user_board(connection, user_id)
    task = _get_task(connection, user_id, task_id)
    if task is None:
        return None

    old_status = task.status
    old_position = task.position
    target_status = payload.status.value

    # Positions stay contiguous within each column. Pull the source column up to
    # fill the hole the task leaves, then push the target column down to free a
    # slot — clamped so a task can't be dropped past the end of its column.
    connection.execute(queries.close_status_gap_query(old_status, user_id, old_position))

    target_position = min(
        payload.position,
        _status_count(connection, user_id, target_status, exclude_id=task.id),
    )
    connection.execute(
        queries.open_status_gap_query(target_status, user_id, target_position, task.id)
    )

    return _fetch_task(
        connection,
        queries.move_task_query(task.id, user_id, target_status, target_position),
    )


def delete_task(connection: DatabaseConnection, user_id: str, task_id: UUID) -> bool:
    _lock_user_board(connection, user_id)
    with connection.cursor(row_factory=class_row(DeletedTask)) as cursor:
        cursor.execute(queries.delete_task_query(task_id, user_id))
        deleted_task = cursor.fetchone()

    if deleted_task is None:
        return False

    connection.execute(
        queries.close_status_gap_query(deleted_task.status, user_id, deleted_task.position)
    )
    return True


def count_tasks(connection: DatabaseConnection, user_id: str) -> int:
    with connection.cursor(row_factory=scalar_row) as cursor:
        cursor.execute(queries.count_tasks_query(user_id))
        return cast(int, next(cursor))


def _get_task(connection: DatabaseConnection, user_id: str, task_id: UUID) -> TaskRead | None:
    return _fetch_task(connection, queries.task_by_id_query(task_id, user_id))


def _fetch_task(connection: DatabaseConnection, query: Template) -> TaskRead | None:
    with connection.cursor(row_factory=class_row(TaskRead)) as cursor:
        cursor.execute(query)
        return cursor.fetchone()


def _lock_user_board(connection: DatabaseConnection, user_id: str) -> None:
    # Complements the deferred unique constraint: normal position mutations
    # serialize per user instead of racing into a commit-time uniqueness failure.
    connection.execute(queries.lock_user_board_query(user_id))


def _status_count(
    connection: DatabaseConnection,
    user_id: str,
    status: str,
    exclude_id: UUID | None = None,
) -> int:
    with connection.cursor(row_factory=scalar_row) as cursor:
        cursor.execute(queries.status_count_query(status, user_id, exclude_id))
        return cast(int, next(cursor))
