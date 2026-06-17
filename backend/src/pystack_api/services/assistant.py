"""Assistant chat service backed by OpenRouter and local task tools.

The public entry point is `stream_assistant_events`, which turns a chat request
into newline-delimited JSON events for the frontend. Internally it runs one or
more OpenRouter chat-completion rounds, executes any requested task tools
against the local database, and sends the tool results back to the model.
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from pystack_api.core.config import Settings
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
type OpenRouterMessage = dict[str, Any]

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOOL_ROUNDS = 6
# Use uvicorn's visible server logger for assistant traces so they show up under
# `make dev` beside request logs. The trace helper below keeps normal logs compact
# and reserves full tool payloads for DEBUG.
logger = logging.getLogger("uvicorn.error")

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
class PendingToolCall:
    index: int
    id: str = ""
    name: str = ""
    arguments_text: str = ""


@dataclass(frozen=True)
class AssistantToolResult:
    content: JsonObject
    mutated: bool = False


class ListTasksArgs(BaseModel):
    """Schema used to reject stray arguments for the zero-argument list_tasks tool."""


class CreateTaskArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class UpdateTaskArgs(BaseModel):
    task_id: UUID
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class MoveTaskArgs(BaseModel):
    task_id: UUID
    status: TaskStatus
    position: int = Field(ge=0)


class DeleteTaskArgs(BaseModel):
    task_id: UUID


TASK_TOOL_DEFINITIONS: list[JsonObject] = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": (
                "List every task on the todo board, including IDs, titles, descriptions, "
                "statuses, and positions. Call this before editing, moving, or deleting "
                "when the user identifies a task by title or natural language."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task in the backlog column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short task title, 1-200 characters.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional task details or context.",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task title and/or description by task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "The task UUID from list_tasks.",
                    },
                    "title": {"type": "string", "description": "New task title."},
                    "description": {
                        "type": "string",
                        "description": "New task description. Use an empty string to clear it.",
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_task",
            "description": "Move or reorder an existing task by task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "The task UUID from list_tasks.",
                    },
                    "status": {
                        "type": "string",
                        "enum": [status.value for status in TaskStatus],
                        "description": "Target board column.",
                    },
                    "position": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Zero-based target position within the target column.",
                    },
                },
                "required": ["task_id", "status", "position"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete an existing task by task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "The task UUID from list_tasks.",
                    }
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
]


async def stream_assistant_events(
    *,
    settings: Settings,
    connection: DatabaseConnection,
    user_id: str,
    request_messages: list[AssistantChatMessage],
) -> AsyncIterator[str]:
    """Yield frontend assistant events for one user chat request.

    Each OpenRouter round can either finish with text or request local task
    tools. Tool arguments are parsed after all streamed fragments arrive, then
    validated with the Pydantic schemas below before touching the database.
    The round limit prevents a bad model response from looping forever.
    """

    messages = _build_messages(request_messages)

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            text_buffer = ""
            tool_calls: list[PendingToolCall] = []

            async for chunk in _stream_openrouter_chat(settings, messages):
                chunk_type = chunk["type"]
                if chunk_type == "text_delta":
                    text = cast(str, chunk["text"])
                    text_buffer += text
                    yield _encode_event({"type": "text_delta", "text": text})
                elif chunk_type == "tool_calls":
                    tool_calls = cast(list[PendingToolCall], chunk["tool_calls"])

            if not tool_calls:
                yield _encode_event({"type": "done"})
                return

            assistant_message: OpenRouterMessage = {
                "role": "assistant",
                "content": text_buffer or None,
                "tool_calls": [_openrouter_tool_call(tool_call) for tool_call in tool_calls],
            }
            messages.append(assistant_message)

            for tool_call in tool_calls:
                arguments = _parse_tool_arguments(tool_call)
                _log_tool_trace(
                    "call",
                    {
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "args": arguments,
                    },
                )

                started_at = time.perf_counter()
                try:
                    result = execute_task_tool(connection, user_id, tool_call.name, arguments)
                    tool_content: JsonObject = result.content
                    mutated = result.mutated
                    _log_tool_trace(
                        "result",
                        {
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_call.name,
                            "duration_ms": _elapsed_ms(started_at),
                            "mutated": mutated,
                            "result": tool_content,
                        },
                    )
                except ToolExecutionError as exc:
                    tool_content = {"error": str(exc)}
                    mutated = False
                    _log_tool_trace(
                        "error",
                        {
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_call.name,
                            "duration_ms": _elapsed_ms(started_at),
                            "error": str(exc),
                        },
                        is_error=True,
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_content, default=str),
                    }
                )
                if mutated:
                    yield _encode_event({"type": "tasks_changed"})

        raise AssistantChatError("The assistant reached the maximum tool-call limit.")
    except AssistantChatError as exc:
        yield _encode_event({"type": "error", "message": str(exc)})
    except httpx.HTTPError as exc:
        yield _encode_event({"type": "error", "message": f"OpenRouter request failed: {exc}"})


def execute_task_tool(
    connection: DatabaseConnection,
    user_id: str,
    tool_name: str,
    arguments: JsonObject,
) -> AssistantToolResult:
    """Validate and execute one model-requested task tool call.

    All operations are scoped to ``user_id`` so the assistant can only inspect
    and modify the authenticated user's own board.
    """

    match tool_name:
        case "list_tasks":
            _validate_args(ListTasksArgs, arguments)
            return AssistantToolResult(_board_payload(task_service.list_tasks(connection, user_id)))
        case "create_task":
            create_args = _validate_args(CreateTaskArgs, arguments)
            created_task = task_service.create_task(
                connection,
                user_id,
                TaskCreate(title=create_args.title, description=create_args.description),
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
            update_args = _validate_args(UpdateTaskArgs, arguments)
            updated_task = task_service.update_task(
                connection,
                user_id,
                update_args.task_id,
                TaskUpdate(title=update_args.title, description=update_args.description),
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
            move_args = _validate_args(MoveTaskArgs, arguments)
            moved_task = task_service.move_task(
                connection,
                user_id,
                move_args.task_id,
                TaskMove(status=move_args.status, position=move_args.position),
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
            delete_args = _validate_args(DeleteTaskArgs, arguments)
            if not task_service.delete_task(connection, user_id, delete_args.task_id):
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


async def _stream_openrouter_chat(
    settings: Settings,
    messages: list[OpenRouterMessage],
) -> AsyncIterator[JsonObject]:
    """Yield normalized chunks from OpenRouter's streamed SSE response.

    OpenRouter streams Server-Sent Events where each `data:` line holds a chat
    completion chunk. Text can be yielded immediately, but tool calls arrive as
    fragments: the function name and argument JSON can be split across multiple
    deltas. This function therefore keeps a `PendingToolCall` per provider
    index, appends fragments as they arrive, and emits a normalized `tool_calls`
    event only once OpenRouter reports `finish_reason == "tool_calls"` or the
    stream ends. Final argument parsing and Pydantic validation happen later in
    `execute_task_tool`, after the complete argument string exists.
    """

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": "Pystack",
    }
    payload: JsonObject = {
        "model": settings.assistant_model,
        "messages": messages,
        "tools": TASK_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "stream": True,
        "temperature": 0.2,
    }
    timeout = httpx.Timeout(connect=30.0, read=90.0, write=10.0, pool=10.0)

    async with (
        httpx.AsyncClient(timeout=timeout) as client,
        client.stream(
            "POST",
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
        ) as response,
    ):
        if response.status_code >= 400:
            body = await response.aread()
            raise AssistantChatError(_openrouter_error_message(response.status_code, body))

        tool_calls_by_index: dict[int, PendingToolCall] = {}
        async for line in response.aiter_lines():
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data: "):
                continue

            data = line.removeprefix("data: ").strip()
            if data == "[DONE]":
                break

            chunk = _load_sse_json(data)
            error = chunk.get("error")
            if isinstance(error, dict):
                raise AssistantChatError(str(error.get("message", "OpenRouter stream failed.")))

            choice = _first_choice(chunk)
            if choice is None:
                continue

            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue

            content = delta.get("content")
            if isinstance(content, str) and content:
                yield {"type": "text_delta", "text": content}

            # Tool call fields are streamed piecemeal, so collect them by
            # provider index until the finish reason says the call is complete.
            _accumulate_tool_calls(delta, tool_calls_by_index)

            finish_reason = choice.get("finish_reason") or delta.get("finish_reason")
            if finish_reason == "tool_calls":
                yield {
                    "type": "tool_calls",
                    "tool_calls": _normalize_tool_calls(tool_calls_by_index),
                }

        if tool_calls_by_index:
            yield {
                "type": "tool_calls",
                "tool_calls": _normalize_tool_calls(tool_calls_by_index),
            }


def _validate_args[T: BaseModel](model: type[T], arguments: JsonObject) -> T:
    try:
        return model.model_validate(arguments)
    except ValidationError as exc:
        raise ToolExecutionError(exc.errors(include_url=False)) from exc


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


def _build_messages(request_messages: list[AssistantChatMessage]) -> list[OpenRouterMessage]:
    messages: list[OpenRouterMessage] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in request_messages:
        messages.append({"role": message.role, "content": message.content})
    return messages


def _openrouter_tool_call(tool_call: PendingToolCall) -> JsonObject:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": tool_call.arguments_text or "{}",
        },
    }


def _parse_tool_arguments(tool_call: PendingToolCall) -> JsonObject:
    if not tool_call.name:
        raise AssistantChatError("OpenRouter returned a tool call without a tool name.")

    try:
        parsed = json.loads(tool_call.arguments_text or "{}")
    except json.JSONDecodeError as exc:
        raise AssistantChatError(f"Could not parse tool arguments for {tool_call.name}.") from exc

    if not isinstance(parsed, dict):
        raise AssistantChatError(f"Tool arguments for {tool_call.name} were not an object.")
    return cast(JsonObject, parsed)


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _log_tool_trace(event: str, payload: JsonObject, *, is_error: bool = False) -> None:
    """Log assistant tool execution without dumping raw board data at INFO.

    Tool payloads can include the entire board. Keep INFO useful for normal
    operation with a compact summary, and emit full args/results only at DEBUG
    for deeper troubleshooting.
    """

    summary = json.dumps(_tool_trace_summary(event, payload), default=str)
    detail = json.dumps({"event": event, **payload}, default=str)
    if is_error:
        logger.warning("assistant_tool_trace %s", summary)
        logger.debug("assistant_tool_trace_detail %s", detail)
        return
    logger.info("assistant_tool_trace %s", summary)
    logger.debug("assistant_tool_trace_detail %s", detail)


def _tool_trace_summary(event: str, payload: JsonObject) -> JsonObject:
    summary: JsonObject = {"event": event}
    for key in ("tool_call_id", "tool_name", "duration_ms", "mutated", "error"):
        if key in payload:
            summary[key] = payload[key]

    args = payload.get("args")
    if isinstance(args, dict):
        summary["args"] = _summarize_tool_args(args)

    result = payload.get("result")
    if isinstance(result, dict):
        summary["result"] = _summarize_tool_result(result)

    return summary


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

    task = result.get("task")
    if isinstance(task, dict):
        for source_key, summary_key in (
            ("id", "task_id"),
            ("status", "task_status"),
            ("position", "task_position"),
        ):
            if source_key in task:
                summary[summary_key] = task[source_key]

    board = result.get("board") if isinstance(result.get("board"), dict) else result
    if isinstance(board, dict):
        if "total" in board:
            summary["board_total"] = board["total"]
        counts = board.get("counts")
        if isinstance(counts, dict):
            summary["board_counts"] = counts

    if not summary and result:
        summary["keys"] = sorted(result)
    return summary


def _accumulate_tool_calls(
    delta: JsonObject,
    tool_calls_by_index: dict[int, PendingToolCall],
) -> None:
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return

    for raw_tool_call in tool_calls:
        if not isinstance(raw_tool_call, dict):
            continue
        index = _tool_call_index(raw_tool_call)
        tool_call = tool_calls_by_index.setdefault(index, PendingToolCall(index=index))

        tool_call_id = raw_tool_call.get("id")
        if isinstance(tool_call_id, str) and tool_call_id:
            tool_call.id = tool_call_id

        function = raw_tool_call.get("function")
        if not isinstance(function, dict):
            continue

        name = function.get("name")
        if isinstance(name, str) and name:
            tool_call.name += name

        arguments = function.get("arguments")
        if isinstance(arguments, str) and arguments:
            tool_call.arguments_text += arguments


def _normalize_tool_calls(
    tool_calls_by_index: dict[int, PendingToolCall],
) -> list[PendingToolCall]:
    tool_calls = sorted(tool_calls_by_index.values(), key=lambda tool_call: tool_call.index)
    for tool_call in tool_calls:
        if not tool_call.id:
            tool_call.id = f"tool_call_{tool_call.index}"
    return tool_calls


def _tool_call_index(raw_tool_call: JsonObject) -> int:
    index = raw_tool_call.get("index")
    if isinstance(index, int):
        return index
    return 0


def _load_sse_json(data: str) -> JsonObject:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise AssistantChatError("OpenRouter returned malformed stream data.") from exc
    if not isinstance(parsed, dict):
        raise AssistantChatError("OpenRouter returned unexpected stream data.")
    return cast(JsonObject, parsed)


def _first_choice(chunk: JsonObject) -> JsonObject | None:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    if not isinstance(choice, dict):
        return None
    return cast(JsonObject, choice)


def _openrouter_error_message(status_code: int, body: bytes) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return f"OpenRouter request failed with HTTP {status_code}."

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail

    return f"OpenRouter request failed with HTTP {status_code}."


def _encode_event(event: JsonObject) -> str:
    return json.dumps(event, separators=(",", ":"), default=str) + "\n"
