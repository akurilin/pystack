"""Assistant chat service backed by Pydantic AI, OpenRouter, and local task tools.

The public entry point is `stream_assistant_events`, which turns a chat request
into newline-delimited JSON events for the frontend. Pydantic AI owns the
OpenRouter model protocol and tool-call loop; this module owns the local task
tool implementations and operational logs.
"""

import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import Field, TypeAdapter
from pydantic_ai import Agent, ModelSettings, RunContext, Tool, UsageLimits
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from pystack_api.core.config import Settings
from pystack_api.core.event_log import log_event
from pystack_api.db.connection import DatabaseConnection
from pystack_api.schemas import (
    AssistantChatMessage,
    TaskCreate,
    TaskMove,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from pystack_api.services import tasks as task_service

type JsonObject = dict[str, Any]
type ToolTraceEvent = Literal["call", "result", "error"]

MAX_MODEL_REQUESTS = 6
SYSTEM_PROMPT = """You are the Pystack todo board assistant.

You help the user inspect and update a small Kanban-style todo board.
The board statuses are backlog, ready, in_progress, review, and done.

Use tools for any request that needs current board data or changes the board.
When a user asks to edit, move, or delete a task by title or description, call
list_tasks first so you can use the exact task UUID. If a request is ambiguous,
ask a concise clarifying question instead of guessing. After a mutation, briefly
confirm what changed. Do not invent tasks that are not returned by the tools.
"""


class AssistantChatError(Exception):
    """Raised when the assistant stream cannot continue."""


class ToolExecutionError(Exception):
    """Raised when a model-requested task operation cannot be completed."""


@dataclass
class AssistantRunState:
    tool_call_count: int = 0
    mutation_count: int = 0
    pending_task_change_events: int = 0


@dataclass(frozen=True)
class AssistantToolResult:
    content: JsonObject
    mutated: bool = False


@dataclass
class AssistantDeps:
    settings: Settings
    connection: DatabaseConnection
    user_id: str
    request_id: str
    assistant_run_id: str
    state: AssistantRunState = field(default_factory=AssistantRunState)


ASSISTANT_TOOL_COUNT = 5
type AssistantModelFactory = Callable[[Settings], Model]


def build_openrouter_model(settings: Settings) -> Model:
    """Build the production model provider used by the assistant."""

    if settings.openrouter_api_key is None:
        raise AssistantChatError(
            "Assistant chat requires PYSTACK_OPENROUTER_API_KEY or OPENROUTER_API_KEY."
        )

    return OpenRouterModel(
        settings.assistant_model,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key, app_title="Pystack"),
    )


def get_assistant_model_factory() -> AssistantModelFactory:
    """FastAPI dependency for the assistant's external model boundary.

    Tests should override this dependency with a factory that returns Pydantic
    AI's FunctionModel/TestModel. That keeps the agent setup, tool definitions,
    streaming loop, and local task tools real while avoiding OpenRouter network
    calls. Keep the seam at the model boundary unless production code needs a
    broader abstraction.
    """

    return build_openrouter_model


async def stream_assistant_events(
    *,
    settings: Settings,
    connection: DatabaseConnection,
    user_id: str,
    request_id: str,
    request_messages: list[AssistantChatMessage],
    model_factory: AssistantModelFactory = build_openrouter_model,
) -> AsyncIterator[str]:
    """Yield frontend assistant events for one user chat request.

    Pydantic AI handles OpenRouter streaming and model-requested tool execution.
    We keep the frontend contract narrow: text deltas, task-change hints after
    mutations, a final done event, or a recoverable error event.
    """

    assistant_run_id = str(uuid4())
    run_started_at = time.perf_counter()
    deps: AssistantDeps | None = None

    log_event(
        logging.INFO,
        "assistant.run.started",
        environment=settings.environment,
        request_id=request_id,
        assistant_run_id=assistant_run_id,
        model=settings.assistant_model,
        request_message_count=len(request_messages),
    )

    try:
        prompt, message_history = _prompt_and_history(request_messages)
        deps = AssistantDeps(
            settings=settings,
            connection=connection,
            user_id=user_id,
            request_id=request_id,
            assistant_run_id=assistant_run_id,
        )
        agent = _build_agent(settings, model_factory)
        model_started_at = time.perf_counter()
        text_char_count = 0

        log_event(
            logging.INFO,
            "assistant.model.started",
            environment=settings.environment,
            request_id=request_id,
            assistant_run_id=assistant_run_id,
            model=settings.assistant_model,
            round_index=0,
            message_count=len(request_messages),
            available_tool_count=ASSISTANT_TOOL_COUNT,
        )

        async with agent.iter(
            prompt,
            message_history=message_history,
            deps=deps,
            usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS),
        ) as run:
            # Drive the agent graph node by node instead of agent.run_stream, which
            # streams only the final model response. When a model emits text in the
            # same turn as a tool call, run_stream stops at that text and the tool
            # never runs. Streaming each model-request node surfaces every turn's
            # text while the graph still executes the tool calls between turns.
            async for node in run:
                if not Agent.is_model_request_node(node):
                    continue
                async with node.stream(run.ctx) as request_stream:
                    async for delta in request_stream.stream_text(delta=True):
                        for _ in range(_pop_task_change_events(deps)):
                            yield _encode_event({"type": "tasks_changed"})
                        if delta:
                            text_char_count += len(delta)
                            yield _encode_event({"type": "text_delta", "text": delta})

            for _ in range(_pop_task_change_events(deps)):
                yield _encode_event({"type": "tasks_changed"})
            usage = run.usage

        log_event(
            logging.INFO,
            "assistant.model.completed",
            environment=settings.environment,
            request_id=request_id,
            assistant_run_id=assistant_run_id,
            model=settings.assistant_model,
            round_index=0,
            duration_ms=_elapsed_ms(model_started_at),
            text_char_count=text_char_count,
            tool_call_count=deps.state.tool_call_count,
        )
        log_event(
            logging.INFO,
            "assistant.run.completed",
            environment=settings.environment,
            request_id=request_id,
            assistant_run_id=assistant_run_id,
            model=settings.assistant_model,
            status="ok",
            duration_ms=_elapsed_ms(run_started_at),
            rounds_used=usage.requests,
            tool_call_count=deps.state.tool_call_count,
            mutation_count=deps.state.mutation_count,
        )
        yield _encode_event({"type": "done"})
    # Failures during a run collapse into two families:
    #   * AssistantChatError — our own request validation (empty history, last
    #     message not from the user). Raised before the model is ever called.
    #   * AgentRunError — Pydantic AI's base for anything that goes wrong during
    #     the run. The subclasses we can expect, mostly from OpenRouter:
    #       - ModelHTTPError: a 4xx/5xx from OpenRouter. Carries the status code
    #         and raw response body (both are folded into str(exc), so they land
    #         in the log). Covers auth (401/403: bad or revoked key), rate limits
    #         / spent quota (429, easy to hit on the free-tier default model),
    #         bad requests (400: unknown or deactivated model, context length
    #         exceeded), and provider outages (5xx, or no upstream provider
    #         available for the model).
    #       - UsageLimitExceeded: our own MAX_MODEL_REQUESTS cap tripped by a
    #         tool loop that won't terminate — not an OpenRouter failure.
    #       - UnexpectedModelBehavior / IncompleteToolCall: malformed or
    #         truncated model output (e.g. a tool call cut off by the token
    #         limit). str(exc) includes the response body when available.
    #       - ContentFilterError: the provider filtered the response, leaving it
    #         empty.
    #     Lower-level causes (e.g. a wrapped httpx network error — timeout,
    #     connection refused, DNS failure) are captured via exc.__cause__ in the
    #     log below.
    except (AssistantChatError, AgentRunError) as exc:
        if deps is not None:
            for _ in range(_pop_task_change_events(deps)):
                yield _encode_event({"type": "tasks_changed"})
        _log_assistant_run_error(settings, request_id, assistant_run_id, run_started_at, exc)
        yield _encode_event({"type": "error", "message": _assistant_error_message(exc)})


def execute_task_tool(
    connection: DatabaseConnection,
    user_id: str,
    tool_name: str,
    arguments: JsonObject,
) -> AssistantToolResult:
    """Execute one model-requested task tool call against the user's board.

    Argument shape and constraints are enforced upstream: the agent tools below
    declare typed, constrained parameters that Pydantic AI validates before
    dispatching here, and the TaskCreate/TaskUpdate/TaskMove schemas validate
    again on construction for any direct caller. All operations are scoped to
    ``user_id`` so the assistant only touches the authenticated user's own board.
    """

    match tool_name:
        case "list_tasks":
            return AssistantToolResult(_board_payload(task_service.list_tasks(connection, user_id)))
        case "create_task":
            created_task = task_service.create_task(
                connection, user_id, TaskCreate.model_validate(arguments)
            )
            return AssistantToolResult(
                {
                    "message": f"Created task '{created_task.title}'.",
                    "task": _task_payload(created_task),
                    "board": _board_payload(task_service.list_tasks(connection, user_id)),
                },
                mutated=True,
            )
        case "update_task":
            updated_task = task_service.update_task(
                connection,
                user_id,
                _task_id(arguments),
                TaskUpdate.model_validate(arguments),
            )
            if updated_task is None:
                raise ToolExecutionError("No task was found with that task_id.")
            return AssistantToolResult(
                {
                    "message": f"Updated task '{updated_task.title}'.",
                    "task": _task_payload(updated_task),
                    "board": _board_payload(task_service.list_tasks(connection, user_id)),
                },
                mutated=True,
            )
        case "move_task":
            moved_task = task_service.move_task(
                connection,
                user_id,
                _task_id(arguments),
                TaskMove.model_validate(arguments),
            )
            if moved_task is None:
                raise ToolExecutionError("No task was found with that task_id.")
            return AssistantToolResult(
                {
                    "message": f"Moved task '{moved_task.title}' to {moved_task.status}.",
                    "task": _task_payload(moved_task),
                    "board": _board_payload(task_service.list_tasks(connection, user_id)),
                },
                mutated=True,
            )
        case "delete_task":
            if not task_service.delete_task(connection, user_id, _task_id(arguments)):
                raise ToolExecutionError("No task was found with that task_id.")
            return AssistantToolResult(
                {
                    "message": "Deleted the task.",
                    "board": _board_payload(task_service.list_tasks(connection, user_id)),
                },
                mutated=True,
            )
        case _:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")


def _build_agent(
    settings: Settings,
    model_factory: AssistantModelFactory = build_openrouter_model,
) -> Agent[AssistantDeps, str]:
    return Agent[AssistantDeps, str](
        model_factory(settings),
        deps_type=AssistantDeps,
        output_type=str,
        instructions=SYSTEM_PROMPT,
        model_settings=ModelSettings(temperature=0.2, parallel_tool_calls=False),
        tools=_assistant_tools(),
    )


def _assistant_tools() -> list[Tool[AssistantDeps]]:
    return [
        Tool(
            list_tasks,
            takes_ctx=True,
            name="list_tasks",
            description=(
                "List every task on the todo board, including IDs, titles, descriptions, "
                "statuses, and positions. Call this before editing, moving, or deleting "
                "when the user identifies a task by title or natural language."
            ),
        ),
        Tool(
            create_task,
            takes_ctx=True,
            name="create_task",
            description="Create a new task in the backlog column.",
        ),
        Tool(
            update_task,
            takes_ctx=True,
            name="update_task",
            description="Update an existing task title and/or description by task ID.",
        ),
        Tool(
            move_task,
            takes_ctx=True,
            name="move_task",
            description="Move or reorder an existing task by task ID.",
        ),
        Tool(
            delete_task,
            takes_ctx=True,
            name="delete_task",
            description="Delete an existing task by task ID.",
        ),
    ]


def list_tasks(ctx: RunContext[AssistantDeps]) -> JsonObject:
    """List every task on the user's board."""

    return _execute_agent_tool(ctx, "list_tasks", {})


# The parameter constraints below mirror the TaskCreate/TaskUpdate/TaskMove
# schemas. They live on the signatures so Pydantic AI both advertises them to the
# model in each tool's JSON schema and rejects invalid arguments before dispatch,
# which is why execute_task_tool no longer re-validates.
_TaskId = Annotated[UUID, Field(description="The task UUID from list_tasks.")]


def create_task(
    ctx: RunContext[AssistantDeps],
    title: Annotated[
        str, Field(min_length=1, max_length=200, description="Short task title, 1-200 characters.")
    ],
    description: Annotated[
        str, Field(max_length=5000, description="Optional task details or context.")
    ] = "",
) -> JsonObject:
    """Create a backlog task."""

    return _execute_agent_tool(ctx, "create_task", {"title": title, "description": description})


def update_task(
    ctx: RunContext[AssistantDeps],
    task_id: _TaskId,
    title: Annotated[
        str | None, Field(min_length=1, max_length=200, description="New task title.")
    ] = None,
    description: Annotated[
        str | None,
        Field(max_length=5000, description="New description. Use an empty string to clear it."),
    ] = None,
) -> JsonObject:
    """Update a task's title or description by UUID."""

    arguments: JsonObject = {"task_id": task_id}
    if title is not None:
        arguments["title"] = title
    if description is not None:
        arguments["description"] = description
    return _execute_agent_tool(ctx, "update_task", arguments)


def move_task(
    ctx: RunContext[AssistantDeps],
    task_id: _TaskId,
    status: Annotated[TaskStatus, Field(description="Target board column.")],
    position: Annotated[
        int, Field(ge=0, description="Zero-based target position within the target column.")
    ],
) -> JsonObject:
    """Move a task by UUID to a status and zero-based position."""

    return _execute_agent_tool(
        ctx,
        "move_task",
        {"task_id": task_id, "status": status, "position": position},
    )


def delete_task(ctx: RunContext[AssistantDeps], task_id: _TaskId) -> JsonObject:
    """Delete a task by UUID."""

    return _execute_agent_tool(ctx, "delete_task", {"task_id": task_id})


def _execute_agent_tool(
    ctx: RunContext[AssistantDeps],
    tool_name: str,
    arguments: JsonObject,
) -> JsonObject:
    deps = ctx.deps
    deps.state.tool_call_count += 1
    tool_call_id = ctx.tool_call_id or f"{tool_name}-{deps.state.tool_call_count}"
    started_at = time.perf_counter()

    _log_tool_trace(
        event="call",
        environment=deps.settings.environment,
        request_id=deps.request_id,
        assistant_run_id=deps.assistant_run_id,
        model=deps.settings.assistant_model,
        round_index=0,
        payload={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "args": arguments,
        },
    )

    try:
        result = execute_task_tool(deps.connection, deps.user_id, tool_name, arguments)
    except ToolExecutionError as exc:
        _log_tool_trace(
            event="error",
            environment=deps.settings.environment,
            request_id=deps.request_id,
            assistant_run_id=deps.assistant_run_id,
            model=deps.settings.assistant_model,
            round_index=0,
            payload={
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "duration_ms": _elapsed_ms(started_at),
                "error": str(exc),
            },
            is_error=True,
        )
        return {"error": str(exc)}

    if result.mutated:
        deps.state.mutation_count += 1
        deps.state.pending_task_change_events += 1
    _log_tool_trace(
        event="result",
        environment=deps.settings.environment,
        request_id=deps.request_id,
        assistant_run_id=deps.assistant_run_id,
        model=deps.settings.assistant_model,
        round_index=0,
        payload={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "duration_ms": _elapsed_ms(started_at),
            "mutated": result.mutated,
            "result": result.content,
        },
    )
    return result.content


def _pop_task_change_events(deps: AssistantDeps) -> int:
    pending = deps.state.pending_task_change_events
    deps.state.pending_task_change_events = 0
    return pending


_TASK_ID_ADAPTER = TypeAdapter(UUID)


def _task_id(arguments: JsonObject) -> UUID:
    """Coerce the dict task_id to a UUID.

    The agent tools already pass a UUID; direct callers (and the model) may pass
    a string. TaskUpdate/TaskMove carry the other fields but not the id, so it is
    pulled out and coerced here.
    """

    return _TASK_ID_ADAPTER.validate_python(arguments["task_id"])


def _board_payload(tasks: list[TaskRead]) -> JsonObject:
    counts = {status.value: 0 for status in TaskStatus}
    for task in tasks:
        counts[task.status.value] += 1

    return {
        "tasks": [_task_payload(task) for task in tasks],
        "counts": counts,
        "total": len(tasks),
    }


def _task_payload(task: TaskRead) -> JsonObject:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "position": task.position,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _prompt_and_history(
    request_messages: list[AssistantChatMessage],
) -> tuple[str, list[ModelMessage]]:
    if not request_messages:
        raise AssistantChatError("Assistant request requires at least one message.")

    current_message = request_messages[-1]
    if current_message.role != "user":
        raise AssistantChatError("Assistant request must end with a user message.")

    return current_message.content, _message_history(request_messages[:-1])


def _message_history(request_messages: list[AssistantChatMessage]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for message in request_messages:
        match message.role:
            case "user":
                messages.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
            case "assistant":
                messages.append(ModelResponse(parts=[TextPart(content=message.content)]))
    return messages


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _log_assistant_run_error(
    settings: Settings,
    request_id: str,
    assistant_run_id: str,
    started_at: float,
    exc: Exception,
) -> None:
    log_event(
        logging.WARNING,
        "assistant.run.error",
        environment=settings.environment,
        request_id=request_id,
        assistant_run_id=assistant_run_id,
        model=settings.assistant_model,
        status="error",
        duration_ms=_elapsed_ms(started_at),
        error_type=exc.__class__.__name__,
        # str(exc) already embeds the OpenRouter status code and response body
        # for ModelHTTPError / UnexpectedModelBehavior. __cause__ catches the
        # case where the real reason is a lower-level error Pydantic AI wrapped
        # (e.g. a raw httpx network failure); it drops to None otherwise.
        error_message=str(exc),
        error_cause=repr(exc.__cause__) if exc.__cause__ is not None else None,
    )


def _assistant_error_message(exc: AssistantChatError | AgentRunError) -> str:
    # Every model failure currently collapses to one generic client message. The
    # detailed reason (status code, body, cause) is in the logs only. Mapping the
    # known error families to clearer user-facing messages is tracked in
    # https://github.com/akurilin/pystack/issues/26.
    if isinstance(exc, AgentRunError):
        return f"Assistant model request failed: {exc}"
    return str(exc)


def _log_tool_trace(
    *,
    event: ToolTraceEvent,
    environment: str,
    request_id: str,
    assistant_run_id: str,
    model: str,
    round_index: int,
    payload: JsonObject,
    is_error: bool = False,
) -> None:
    """Log assistant tool execution without dumping raw board data."""

    status = "error" if is_error else "ok" if event == "result" else "started"
    log_event(
        logging.WARNING if is_error else logging.INFO,
        f"assistant.tool.{event}",
        environment=environment,
        request_id=request_id,
        assistant_run_id=assistant_run_id,
        model=model,
        round_index=round_index,
        status=status,
        **_tool_trace_summary(payload),
    )


def _tool_trace_summary(payload: JsonObject) -> JsonObject:
    summary: JsonObject = {}
    for key in ("tool_call_id", "tool_name", "duration_ms", "mutated", "error"):
        if key in payload:
            summary[key] = payload[key]

    args = _as_json_object(payload.get("args"))
    if args is not None:
        summary["tool_args"] = _summarize_tool_args(args)

    result = _as_json_object(payload.get("result"))
    if result is not None:
        summary["tool_result"] = _summarize_tool_result(result)

    return summary


def _as_json_object(value: object) -> JsonObject | None:
    if isinstance(value, dict):
        return cast(JsonObject, value)
    return None


def _summarize_tool_args(args: JsonObject) -> JsonObject:
    summary: JsonObject = {}
    for key in ("task_id", "status", "position"):
        if key in args:
            summary[key] = args[key]
    if "title" in args:
        summary["has_title"] = True
    if "description" in args:
        summary["has_description"] = bool(args["description"])
    if not summary and args:
        summary["keys"] = sorted(args)
    return summary


def _summarize_tool_result(result: JsonObject) -> JsonObject:
    summary: JsonObject = {}

    task = _as_json_object(result.get("task"))
    if task is not None:
        for source_key, summary_key in (
            ("id", "task_id"),
            ("status", "task_status"),
            ("position", "task_position"),
        ):
            if source_key in task:
                summary[summary_key] = task[source_key]

    result_board = _as_json_object(result.get("board"))
    board = result_board if result_board is not None else result
    if "total" in board:
        summary["board_total"] = board["total"]
    counts = _as_json_object(board.get("counts"))
    if counts is not None:
        summary["board_counts"] = counts

    if not summary and result:
        summary["keys"] = sorted(result)
    return summary


def _encode_event(event: JsonObject) -> str:
    return json.dumps(event, separators=(",", ":"), default=str) + "\n"
