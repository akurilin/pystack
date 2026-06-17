from http import HTTPStatus
from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from pystack_api.api.auth import UserIdDependency
from pystack_api.api.dependencies import ConnectionDependency
from pystack_api.core.config import Settings
from pystack_api.db.connection import DatabasePool
from pystack_api.schemas import (
    AssistantChatRequest,
    HealthStatus,
    TaskCreate,
    TaskMove,
    TaskRead,
    TaskUpdate,
)
from pystack_api.services import assistant as assistant_service
from pystack_api.services import tasks as task_service

api_router = APIRouter()


@api_router.get("/health", operation_id="getHealth", response_model=HealthStatus, tags=["health"])
def get_health(request: Request, response: Response) -> HealthStatus:
    """Readiness check: confirm the database is reachable with a trivial query.

    Reports 503 when the database is unreachable so load balancers and
    orchestrators route traffic away. We go through the pool directly rather than
    the connection dependency so a connection failure becomes a clean 503 here
    instead of a 500 raised during dependency resolution.
    """
    pool = cast(DatabasePool, request.app.state.database_pool)
    try:
        with pool.connection() as connection:
            connection.execute("SELECT 1")
    except Exception:  # noqa: BLE001 — any failure means the DB is not ready.
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return HealthStatus(status="error", database="down")
    return HealthStatus(status="ok", database="up")


@api_router.get("/tasks", operation_id="listTasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(connection: ConnectionDependency, user_id: UserIdDependency) -> list[TaskRead]:
    return task_service.list_tasks(connection, user_id)


@api_router.post(
    "/tasks",
    operation_id="createTask",
    response_model=TaskRead,
    status_code=HTTPStatus.CREATED,
    tags=["tasks"],
)
def create_task(
    payload: TaskCreate, connection: ConnectionDependency, user_id: UserIdDependency
) -> TaskRead:
    return task_service.create_task(connection, user_id, payload)


@api_router.patch(
    "/tasks/{task_id}",
    operation_id="updateTask",
    response_model=TaskRead,
    tags=["tasks"],
)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    connection: ConnectionDependency,
    user_id: UserIdDependency,
) -> TaskRead:
    task = task_service.update_task(connection, user_id, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@api_router.post(
    "/tasks/{task_id}/move",
    operation_id="moveTask",
    response_model=TaskRead,
    tags=["tasks"],
)
def move_task(
    task_id: UUID,
    payload: TaskMove,
    connection: ConnectionDependency,
    user_id: UserIdDependency,
) -> TaskRead:
    task = task_service.move_task(connection, user_id, task_id, payload)
    if task is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return task


@api_router.delete(
    "/tasks/{task_id}",
    operation_id="deleteTask",
    status_code=HTTPStatus.NO_CONTENT,
    tags=["tasks"],
)
def delete_task(
    task_id: UUID, connection: ConnectionDependency, user_id: UserIdDependency
) -> Response:
    if not task_service.delete_task(connection, user_id, task_id):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Task not found")
    return Response(status_code=HTTPStatus.NO_CONTENT)


@api_router.post("/assistant/chat", operation_id="chatWithAssistant", tags=["assistant"])
def chat_with_assistant(
    payload: AssistantChatRequest,
    connection: ConnectionDependency,
    user_id: UserIdDependency,
    request: Request,
) -> StreamingResponse:
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        assistant_service.stream_assistant_events(
            settings=settings,
            connection=connection,
            user_id=user_id,
            request_messages=payload.messages,
        ),
        media_type="application/x-ndjson",
    )
