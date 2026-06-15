from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from pystack_api.api.dependencies import SessionDependency
from pystack_api.schemas.task import TaskCreate, TaskMove, TaskRead, TaskUpdate
from pystack_api.services import tasks as task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", operation_id="listTasks", response_model=list[TaskRead])
def list_tasks(session: SessionDependency) -> list[TaskRead]:
    return [TaskRead.model_validate(task) for task in task_service.list_tasks(session)]


@router.post(
    "",
    operation_id="createTask",
    response_model=TaskRead,
    status_code=HTTPStatus.CREATED,
)
def create_task(payload: TaskCreate, session: SessionDependency) -> TaskRead:
    return TaskRead.model_validate(task_service.create_task(session, payload))


@router.patch("/{task_id}", operation_id="updateTask", response_model=TaskRead)
def update_task(task_id: UUID, payload: TaskUpdate, session: SessionDependency) -> TaskRead:
    task = task_service.update_task(session, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.post("/{task_id}/move", operation_id="moveTask", response_model=TaskRead)
def move_task(task_id: UUID, payload: TaskMove, session: SessionDependency) -> TaskRead:
    task = task_service.move_task(session, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", operation_id="deleteTask", status_code=HTTPStatus.NO_CONTENT)
def delete_task(task_id: UUID, session: SessionDependency) -> Response:
    if not task_service.delete_task(session, task_id):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return Response(status_code=HTTPStatus.NO_CONTENT)
