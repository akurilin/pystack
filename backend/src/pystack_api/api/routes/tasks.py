from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from pystack_api.api.dependencies import ConnectionDependency
from pystack_api.schemas.task import TaskCreate, TaskMove, TaskRead, TaskUpdate
from pystack_api.services import tasks as task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", operation_id="listTasks", response_model=list[TaskRead])
def list_tasks(connection: ConnectionDependency) -> list[TaskRead]:
    return task_service.list_tasks(connection)


@router.post(
    "",
    operation_id="createTask",
    response_model=TaskRead,
    status_code=HTTPStatus.CREATED,
)
def create_task(payload: TaskCreate, connection: ConnectionDependency) -> TaskRead:
    return task_service.create_task(connection, payload)


@router.patch("/{task_id}", operation_id="updateTask", response_model=TaskRead)
def update_task(task_id: UUID, payload: TaskUpdate, connection: ConnectionDependency) -> TaskRead:
    task = task_service.update_task(connection, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@router.post("/{task_id}/move", operation_id="moveTask", response_model=TaskRead)
def move_task(task_id: UUID, payload: TaskMove, connection: ConnectionDependency) -> TaskRead:
    task = task_service.move_task(connection, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", operation_id="deleteTask", status_code=HTTPStatus.NO_CONTENT)
def delete_task(task_id: UUID, connection: ConnectionDependency) -> Response:
    if not task_service.delete_task(connection, task_id):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return Response(status_code=HTTPStatus.NO_CONTENT)
