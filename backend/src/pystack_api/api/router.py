from http import HTTPStatus
from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from pystack_api.api.dependencies import ConnectionDependency
from pystack_api.core.config import Settings
from pystack_api.schemas import (
    AssistantChatRequest,
    TaskCreate,
    TaskMove,
    TaskRead,
    TaskUpdate,
)
from pystack_api.services import assistant as assistant_service
from pystack_api.services import tasks as task_service

api_router = APIRouter()


@api_router.get("/health", operation_id="getHealth", tags=["health"])
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/tasks", operation_id="listTasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(connection: ConnectionDependency) -> list[TaskRead]:
    return task_service.list_tasks(connection)


@api_router.post(
    "/tasks",
    operation_id="createTask",
    response_model=TaskRead,
    status_code=HTTPStatus.CREATED,
    tags=["tasks"],
)
def create_task(payload: TaskCreate, connection: ConnectionDependency) -> TaskRead:
    return task_service.create_task(connection, payload)


@api_router.patch(
    "/tasks/{task_id}",
    operation_id="updateTask",
    response_model=TaskRead,
    tags=["tasks"],
)
def update_task(task_id: UUID, payload: TaskUpdate, connection: ConnectionDependency) -> TaskRead:
    task = task_service.update_task(connection, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@api_router.post(
    "/tasks/{task_id}/move",
    operation_id="moveTask",
    response_model=TaskRead,
    tags=["tasks"],
)
def move_task(task_id: UUID, payload: TaskMove, connection: ConnectionDependency) -> TaskRead:
    task = task_service.move_task(connection, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@api_router.delete(
    "/tasks/{task_id}",
    operation_id="deleteTask",
    status_code=HTTPStatus.NO_CONTENT,
    tags=["tasks"],
)
def delete_task(task_id: UUID, connection: ConnectionDependency) -> Response:
    if not task_service.delete_task(connection, task_id):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return Response(status_code=HTTPStatus.NO_CONTENT)


@api_router.post("/assistant/chat", operation_id="chatWithAssistant", tags=["assistant"])
def chat_with_assistant(
    payload: AssistantChatRequest,
    connection: ConnectionDependency,
    request: Request,
) -> StreamingResponse:
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        assistant_service.stream_assistant_events(
            settings=settings,
            connection=connection,
            request_messages=payload.messages,
        ),
        media_type="application/x-ndjson",
    )
