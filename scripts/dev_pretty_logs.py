"""Render app JSON log lines as compact human-readable development logs.

Production should keep newline-delimited JSON because log collectors handle it
well. This script is only a local terminal presentation layer used by `make dev`.
Non-JSON lines, such as uvicorn startup logs, pass through unchanged.
"""

import json
import os
import re
import sys
from collections.abc import Iterable
from typing import Any

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_BLUE = "\033[34m"
_GRAY = "\033[90m"

_LEVEL_COLORS = {
    "debug": _BLUE,
    "info": _GREEN,
    "warning": _YELLOW,
    "warn": _YELLOW,
    "error": _RED,
    "critical": _RED,
}

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_FIELD_ORDER = (
    ("request_id", "request_id"),
    ("http_method", "method"),
    ("http_path", "path"),
    ("status_code", "status_code"),
    ("status", "status"),
    ("duration_ms", "duration_ms"),
    ("assistant_run_id", "assistant_run_id"),
    ("round_index", "round"),
    ("model", "model"),
    ("tool_name", "tool"),
    ("tool_call_id", "tool_call_id"),
    ("mutated", "mutated"),
    ("tool_call_count", "tool_call_count"),
    ("mutation_count", "mutation_count"),
    ("rounds_used", "rounds_used"),
    ("text_char_count", "text_chars"),
    ("error_type", "error_type"),
    ("error_message", "error"),
    ("tool_args", "tool_args"),
    ("tool_result", "tool_result"),
)


def main() -> int:
    use_color = _use_color()
    for raw_line in sys.stdin:
        print(format_log_line(raw_line.rstrip("\n"), use_color=use_color), flush=True)
    return 0


def format_log_line(line: str, *, use_color: bool = False) -> str:
    if not line.startswith("{"):
        return line

    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return line

    if not isinstance(parsed, dict) or not isinstance(parsed.get("event"), str):
        return line

    return _format_event(parsed, use_color=use_color)


def _format_event(event: dict[str, Any], *, use_color: bool) -> str:
    level_value = str(event.get("level", "info"))
    level = _format_level(level_value, use_color=use_color)
    event_name = _color(str(event["event"]), f"{_BOLD}{_CYAN}", use_color)
    fields = " ".join(_format_fields(event, use_color=use_color))

    line = f"{level} {event_name}"
    if fields:
        line = f"{line} {fields}"
    return line


def _format_fields(event: dict[str, Any], *, use_color: bool) -> Iterable[str]:
    for source_key, output_key in _FIELD_ORDER:
        value = event.get(source_key)
        if value is not None:
            key = _color(output_key, _DIM, use_color)
            yield f"{key}={_format_value(value, use_color=use_color)}"


def _format_value(value: object, *, use_color: bool) -> str:
    if isinstance(value, dict | list):
        rendered = json.dumps(_humanize_value(value), separators=(",", ":"), default=str)
        return _color(rendered, _MAGENTA, use_color)
    if isinstance(value, bool):
        return _color(str(value).lower(), _MAGENTA, use_color)
    if isinstance(value, int | float):
        return _color(str(value), _MAGENTA, use_color)
    if isinstance(value, str):
        return _shorten_uuid(value)
    return str(value)


def _humanize_value(value: object) -> object:
    if isinstance(value, str):
        return _shorten_uuid(value)
    if isinstance(value, list):
        return [_humanize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _humanize_value(item) for key, item in value.items()}
    return value


def _shorten_uuid(value: str) -> str:
    if not _UUID_PATTERN.fullmatch(value):
        return value
    return f"...{value.rsplit('-', maxsplit=1)[-1]}"


def _format_level(level: str, *, use_color: bool) -> str:
    padded = f"{level.upper()}:".ljust(9)
    return _color(padded, _LEVEL_COLORS.get(level.lower(), _GREEN), use_color)


def _color(text: str, code: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{code}{text}{_RESET}"


def _use_color() -> bool:
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


if __name__ == "__main__":
    raise SystemExit(main())
