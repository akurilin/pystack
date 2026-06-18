import json
import logging
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pystack_api.api.request_context import RequestContextMiddleware

type JsonEvent = dict[str, object]


def test_request_id_is_generated_when_missing() -> None:
    response = _client().get("/health")

    assert response.status_code == 200
    UUID(response.headers["x-request-id"])


def test_valid_request_id_is_preserved() -> None:
    request_id = "client-request-123"

    response = _client().get("/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    response = _client().get("/health", headers={"X-Request-ID": "bad request id"})

    assert response.status_code == 200
    generated_request_id = response.headers["x-request-id"]
    assert generated_request_id != "bad request id"
    UUID(generated_request_id)


def test_request_completion_log_includes_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request_id = "client-request-456"
    caplog.set_level(logging.INFO, logger="pystack_api.events")
    event_logger = logging.getLogger("pystack_api.events")
    event_logger.addHandler(caplog.handler)

    try:
        response = _client().get("/health", headers={"X-Request-ID": request_id})
    finally:
        event_logger.removeHandler(caplog.handler)

    assert response.status_code == 200
    events = _json_events(caplog.records)
    completed_events = [event for event in events if event.get("event") == "http.request.completed"]
    assert completed_events

    event = completed_events[-1]
    assert event["request_id"] == request_id
    assert event["service"] == "pystack-api"
    assert event["environment"] == "test"
    assert event["http_method"] == "GET"
    assert event["http_path"] == "/health"
    assert event["status_code"] == 200
    assert isinstance(event["duration_ms"], int | float)


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware, environment="test")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


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
