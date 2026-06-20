import json
import logging
from collections.abc import AsyncIterator, Generator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from pydantic_ai.models.test import TestModel

from pystack_api.api.auth import get_current_user_id
from pystack_api.api.request_context import RequestContextMiddleware
from pystack_api.api.router import api_router
from pystack_api.core.config import Settings
from pystack_api.db.connection import DatabaseConnection, get_connection
from pystack_api.services import assistant as assistant_service

type JsonEvent = dict[str, object]


def test_assistant_chat_logs_request_scoped_tool_events(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    request_id = "assistant-request-123"
    event_logger = logging.getLogger("pystack_api.events")
    event_logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="pystack_api.events")

    # This is intentionally a one-off seam for this single logging test: we want
    # to hit the real API route and streaming loop without opening a database or
    # calling OpenRouter. If more assistant tests need the same patching, promote
    # these edges into injected Protocols (for example AssistantModelClient and
    # AssistantToolExecutor) and override them with FastAPI dependency_overrides
    # instead of monkeypatching private service functions.
    monkeypatch.setattr(assistant_service, "_build_agent", _fake_build_agent)
    monkeypatch.setattr(assistant_service, "execute_task_tool", _fake_execute_task_tool)

    try:
        response = _client().post(
            "/api/v1/assistant/chat",
            headers={"X-Request-ID": request_id},
            json={"messages": [{"role": "user", "content": "List my tasks"}]},
        )
    finally:
        event_logger.removeHandler(caplog.handler)

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    assert response.text == '{"type":"text_delta","text":"Done"}\n{"type":"done"}\n'

    events = _json_events(caplog.records)
    assert _find_event(events, "assistant.run.started")["request_id"] == request_id
    assert _find_event(events, "assistant.model.completed")["tool_call_count"] == 1

    tool_event = _find_event(events, "assistant.tool.result")
    assert tool_event["request_id"] == request_id
    assert tool_event["assistant_run_id"]
    assert str(tool_event["tool_call_id"]).startswith("pyd_ai_tool_call_id__")
    assert tool_event["tool_name"] == "list_tasks"
    assert tool_event["status"] == "ok"


def test_assistant_runs_tool_when_model_emits_preamble_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that emits text in the SAME response as a tool call must still run
    the tool and stream the follow-up answer.

    Regression: the assistant streamed the final model response only, so when the
    model prepended preamble text to its tool call the run ended at the preamble
    and the tool never executed (no board change, no answer).
    """

    tool_calls: list[str] = []

    def recording_execute_task_tool(
        connection: DatabaseConnection,
        user_id: str,
        tool_name: str,
        arguments: assistant_service.JsonObject,
    ) -> assistant_service.AssistantToolResult:
        tool_calls.append(tool_name)
        return assistant_service.AssistantToolResult({"tasks": [], "total": 0})

    monkeypatch.setattr(assistant_service, "_build_agent", _fake_build_agent_with_preamble)
    monkeypatch.setattr(assistant_service, "execute_task_tool", recording_execute_task_tool)

    response = _client().post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "List my tasks"}]},
    )

    assert response.status_code == 200
    # The tool ran even though its response also carried preamble text.
    assert tool_calls == ["list_tasks"]
    # Both the preamble and the post-tool answer reached the client.
    streamed_text = "".join(
        event["text"]
        for event in (json.loads(line) for line in response.text.splitlines())
        if event["type"] == "text_delta"
    )
    assert streamed_text == "Let me check your tasks. You have 0 tasks."


def _client() -> TestClient:
    settings = Settings(
        openrouter_api_key="test-openrouter-key",
        clerk_secret_key="sk_test_dummy",  # noqa: S106 - inert test credential.
        environment="test",
    )
    app = FastAPI()
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware, environment=settings.environment)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.dependency_overrides[get_current_user_id] = lambda: "user_test"
    app.dependency_overrides[get_connection] = _fake_connection
    return TestClient(app)


def _fake_connection() -> Generator[DatabaseConnection]:
    yield cast(DatabaseConnection, object())


def _fake_build_agent(
    settings: Settings,
) -> Agent[assistant_service.AssistantDeps, str]:
    return Agent[assistant_service.AssistantDeps, str](
        TestModel(call_tools=["list_tasks"], custom_output_text="Done"),
        deps_type=assistant_service.AssistantDeps,
        output_type=str,
        instructions=assistant_service.SYSTEM_PROMPT,
        tools=assistant_service._assistant_tools(),
    )


def _fake_build_agent_with_preamble(
    settings: Settings,
) -> Agent[assistant_service.AssistantDeps, str]:
    async def stream_model(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        # First turn: preamble text and the tool call in one response. Second
        # turn (a prior ModelResponse exists): the answer using the tool result.
        if any(isinstance(message, ModelResponse) for message in messages):
            yield "You have 0 tasks."
        else:
            yield "Let me check your tasks. "
            yield {0: DeltaToolCall(name="list_tasks", json_args="{}")}

    return Agent[assistant_service.AssistantDeps, str](
        FunctionModel(stream_function=stream_model),
        deps_type=assistant_service.AssistantDeps,
        output_type=str,
        instructions=assistant_service.SYSTEM_PROMPT,
        tools=assistant_service._assistant_tools(),
    )


def _fake_execute_task_tool(
    connection: DatabaseConnection,
    user_id: str,
    tool_name: str,
    arguments: assistant_service.JsonObject,
) -> assistant_service.AssistantToolResult:
    return assistant_service.AssistantToolResult(
        {
            "tasks": [],
            "counts": {
                "backlog": 0,
                "ready": 0,
                "in_progress": 0,
                "review": 0,
                "done": 0,
            },
            "total": 0,
        }
    )


def _json_events(records: list[logging.LogRecord]) -> list[JsonEvent]:
    events: list[JsonEvent] = []
    for record in records:
        message = record.getMessage()
        if not message.startswith("{"):
            continue

        parsed = json.loads(message)
        if isinstance(parsed, dict):
            events.append(cast(JsonEvent, parsed))

    return events


def _find_event(events: list[JsonEvent], name: str) -> JsonEvent:
    for event in events:
        if event.get("event") == name:
            return event
    raise AssertionError(f"Missing log event: {name}")
