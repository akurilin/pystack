"""Small JSON event logger for operational logs.

The app deliberately does not pull in a full observability stack yet. Emitting
stable JSON objects keeps logs queryable today and easy to map into OpenTelemetry
or a log backend later.
"""

import json
import logging
from datetime import UTC, datetime

SERVICE_NAME = "pystack-api"
_LOGGER_NAME = "pystack_api.events"


def log_event(level: int, event: str, *, environment: str, **fields: object) -> None:
    """Emit one structured application event as a compact JSON line."""

    payload: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        "service": SERVICE_NAME,
        "environment": environment,
    }
    payload.update({key: value for key, value in fields.items() if value is not None})

    _event_logger().log(level, json.dumps(payload, default=str, separators=(",", ":")))


def _event_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger
