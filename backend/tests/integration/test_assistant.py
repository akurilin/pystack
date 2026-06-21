import json
from collections.abc import AsyncIterator, Callable
from typing import cast

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelMessage, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from pystack_api.core.config import Settings, get_settings
from pystack_api.main import create_app
from pystack_api.services import assistant as assistant_service

settings = get_settings()

USER_ID = "user_assistant_test"
type JsonEvent = dict[str, object]
type ToolResultAssertion = Callable[[assistant_service.JsonObject], None]


def test_assistant_task_tools_mutate_board() -> None:
    with psycopg.connect(settings.test_database_url) as connection:
        created = assistant_service.execute_task_tool(
            connection,
            USER_ID,
            "create_task",
            {"title": "Draft release notes", "description": "Summarize changes"},
        )
        task_id = created.content["task"]["id"]

        moved = assistant_service.execute_task_tool(
            connection,
            USER_ID,
            "move_task",
            {"task_id": task_id, "status": "ready", "position": 0},
        )
        listed = assistant_service.execute_task_tool(connection, USER_ID, "list_tasks", {})

    assert created.mutated
    assert created.content["task"]["status"] == "backlog"
    assert moved.mutated
    assert moved.content["task"]["status"] == "ready"
    assert listed.content["total"] == 1
    assert listed.content["counts"]["ready"] == 1


def test_assistant_chat_can_execute_list_tasks_tool_call(client: TestClient) -> None:
    _create_task(client, "Existing task", "Already on the board")

    def assert_tool_result(result: assistant_service.JsonObject) -> None:
        assert result["total"] == 1
        assert result["counts"]["backlog"] == 1
        assert [task["title"] for task in result["tasks"]] == ["Existing task"]

    events = _chat_with_tool_call(client, "list_tasks", {}, assert_tool_result)

    assert _event_types(events) == ["text_delta", "done"]
    assert _streamed_text(events) == "list_tasks complete"


def test_assistant_chat_can_execute_create_task_tool_call(client: TestClient) -> None:
    def assert_tool_result(result: assistant_service.JsonObject) -> None:
        task = cast(assistant_service.JsonObject, result["task"])
        board = cast(assistant_service.JsonObject, result["board"])
        assert task["title"] == "Write release notes"
        assert task["description"] == "Summarize the shipped changes"
        assert task["status"] == "backlog"
        assert board["total"] == 1

    events = _chat_with_tool_call(
        client,
        "create_task",
        {"title": "Write release notes", "description": "Summarize the shipped changes"},
        assert_tool_result,
    )

    assert _event_types(events) == ["tasks_changed", "text_delta", "done"]
    assert [task["title"] for task in client.get("/api/v1/tasks").json()] == ["Write release notes"]


def test_assistant_chat_can_execute_update_task_tool_call(client: TestClient) -> None:
    task = _create_task(client, "Draft notes", "Rough")

    def assert_tool_result(result: assistant_service.JsonObject) -> None:
        updated_task = cast(assistant_service.JsonObject, result["task"])
        assert updated_task["id"] == task["id"]
        assert updated_task["title"] == "Polished notes"
        assert updated_task["description"] == "Ready for review"

    events = _chat_with_tool_call(
        client,
        "update_task",
        {
            "task_id": task["id"],
            "title": "Polished notes",
            "description": "Ready for review",
        },
        assert_tool_result,
    )

    assert _event_types(events) == ["tasks_changed", "text_delta", "done"]
    assert client.get("/api/v1/tasks").json()[0]["title"] == "Polished notes"


def test_assistant_chat_can_execute_move_task_tool_call(client: TestClient) -> None:
    _create_task(client, "First")
    task = _create_task(client, "Second")

    def assert_tool_result(result: assistant_service.JsonObject) -> None:
        moved_task = cast(assistant_service.JsonObject, result["task"])
        board = cast(assistant_service.JsonObject, result["board"])
        assert moved_task["id"] == task["id"]
        assert moved_task["status"] == "ready"
        assert moved_task["position"] == 0
        assert board["counts"]["backlog"] == 1
        assert board["counts"]["ready"] == 1

    events = _chat_with_tool_call(
        client,
        "move_task",
        {"task_id": task["id"], "status": "ready", "position": 0},
        assert_tool_result,
    )

    tasks = client.get("/api/v1/tasks").json()
    assert _event_types(events) == ["tasks_changed", "text_delta", "done"]
    assert [(task["title"], task["status"], task["position"]) for task in tasks] == [
        ("First", "backlog", 0),
        ("Second", "ready", 0),
    ]


def test_assistant_chat_can_execute_delete_task_tool_call(client: TestClient) -> None:
    task = _create_task(client, "Remove me")

    def assert_tool_result(result: assistant_service.JsonObject) -> None:
        board = cast(assistant_service.JsonObject, result["board"])
        assert result["message"] == "Deleted the task."
        assert board["total"] == 0

    events = _chat_with_tool_call(
        client,
        "delete_task",
        {"task_id": task["id"]},
        assert_tool_result,
    )

    assert _event_types(events) == ["tasks_changed", "text_delta", "done"]
    assert client.get("/api/v1/tasks").json() == []


def test_app_startup_requires_openrouter_key() -> None:
    test_settings = settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "openrouter_api_key": None,
            "clerk_secret_key": "sk_test_dummy",
        }
    )

    with (
        pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"),
        TestClient(create_app(test_settings)),
    ):
        pass


def test_app_startup_requires_clerk_key() -> None:
    test_settings = settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "openrouter_api_key": "test-openrouter-key",
            "clerk_secret_key": None,
        }
    )

    with (
        pytest.raises(RuntimeError, match="CLERK_SECRET_KEY"),
        TestClient(create_app(test_settings)),
    ):
        pass


def _chat_with_tool_call(
    client: TestClient,
    tool_name: str,
    arguments: assistant_service.JsonObject,
    assert_tool_result: ToolResultAssertion,
) -> list[JsonEvent]:
    _override_assistant_model(
        client,
        _model_factory_for_tool_call(tool_name, arguments, assert_tool_result),
    )
    response = client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": f"Please run {tool_name}"}]},
    )

    assert response.status_code == 200
    events = _json_events(response.text)
    assert events[-1] == {"type": "done"}
    assert not any(event["type"] == "error" for event in events)
    return events


def _model_factory_for_tool_call(
    tool_name: str,
    arguments: assistant_service.JsonObject,
    assert_tool_result: ToolResultAssertion,
) -> assistant_service.AssistantModelFactory:
    # The fake model mirrors the provider boundary we care about: first it asks
    # Pydantic AI to call one assistant tool, then it inspects the ToolReturnPart
    # from the next model turn. Everything between those two turns is production
    # code: agent configuration, tool dispatch, task service, SQL, and streaming.
    async def stream_model(
        messages: list[ModelMessage], _info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        tool_result = _tool_return_content(messages, tool_name)
        if tool_result is None:
            yield {
                0: DeltaToolCall(
                    name=tool_name,
                    json_args=json.dumps(arguments, default=str),
                    tool_call_id=f"{tool_name}_call",
                )
            }
            return

        assert_tool_result(tool_result)
        yield f"{tool_name} complete"

    def model_factory(_settings: Settings) -> Model:
        return FunctionModel(stream_function=stream_model)

    return model_factory


def _tool_return_content(
    messages: list[ModelMessage], tool_name: str
) -> assistant_service.JsonObject | None:
    for message in reversed(messages):
        for part in reversed(message.parts):
            if isinstance(part, ToolReturnPart) and part.tool_name == tool_name:
                assert isinstance(part.content, dict)
                return cast(assistant_service.JsonObject, part.content)
    return None


def _override_assistant_model(
    client: TestClient, model_factory: assistant_service.AssistantModelFactory
) -> None:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[assistant_service.get_assistant_model_factory] = lambda: model_factory


def _create_task(
    client: TestClient, title: str, description: str = ""
) -> assistant_service.JsonObject:
    response = client.post("/api/v1/tasks", json={"title": title, "description": description})
    assert response.status_code == 201
    return cast(assistant_service.JsonObject, response.json())


def _json_events(text: str) -> list[JsonEvent]:
    return [cast(JsonEvent, json.loads(line)) for line in text.splitlines()]


def _event_types(events: list[JsonEvent]) -> list[object]:
    return [event["type"] for event in events]


def _streamed_text(events: list[JsonEvent]) -> str:
    return "".join(str(event["text"]) for event in events if event.get("type") == "text_delta")
