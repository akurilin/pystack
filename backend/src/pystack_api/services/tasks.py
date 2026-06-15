from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from pystack_api.models.task import Task, TaskStatus
from pystack_api.schemas.task import TaskCreate, TaskMove, TaskUpdate

STATUS_ORDER = {status.value: index for index, status in enumerate(TaskStatus)}


def list_tasks(session: Session) -> list[Task]:
    status_order = case(STATUS_ORDER, value=Task.status)
    return list(
        session.scalars(select(Task).order_by(status_order, Task.position, Task.created_at))
    )


def create_task(session: Session, payload: TaskCreate) -> Task:
    position = _status_count(session, TaskStatus.BACKLOG.value)
    task = Task(
        title=payload.title,
        description=payload.description,
        status=TaskStatus.BACKLOG.value,
        position=position,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def update_task(session: Session, task_id: UUID, payload: TaskUpdate) -> Task | None:
    task = session.get(Task, task_id)
    if task is None:
        return None

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in updates.items():
        setattr(task, field, value)

    session.commit()
    session.refresh(task)
    return task


def move_task(session: Session, task_id: UUID, payload: TaskMove) -> Task | None:
    task = session.get(Task, task_id)
    if task is None:
        return None

    old_status = task.status
    old_position = task.position
    target_status = payload.status.value

    session.execute(
        update(Task)
        .where(Task.status == old_status, Task.position > old_position)
        .values(position=Task.position - 1)
    )
    session.flush()

    target_position = min(
        payload.position, _status_count(session, target_status, exclude_id=task.id)
    )
    session.execute(
        update(Task)
        .where(
            Task.status == target_status,
            Task.position >= target_position,
            Task.id != task.id,
        )
        .values(position=Task.position + 1)
    )

    task.status = target_status
    task.position = target_position
    session.commit()
    session.refresh(task)
    return task


def delete_task(session: Session, task_id: UUID) -> bool:
    task = session.get(Task, task_id)
    if task is None:
        return False

    status = task.status
    position = task.position
    session.delete(task)
    session.flush()
    session.execute(
        update(Task)
        .where(Task.status == status, Task.position > position)
        .values(position=Task.position - 1)
    )
    session.commit()
    return True


def _status_count(session: Session, status: str, exclude_id: UUID | None = None) -> int:
    statement = select(func.count(Task.id)).where(Task.status == status)
    if exclude_id is not None:
        statement = statement.where(Task.id != exclude_id)
    return session.scalar(statement) or 0
