"""Request-scoped operational context."""

import logging
import re
import time
from typing import cast
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pystack_api.core.event_log import log_event

REQUEST_ID_HEADER = "x-request-id"
_REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.encode("ascii")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestContextMiddleware:
    """Attach a request id and log one completion event for each HTTP request."""

    def __init__(self, app: ASGIApp, *, environment: str) -> None:
        self.app = app
        self.environment = environment

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_from_scope(scope) or _new_request_id()
        state = cast(dict[str, object], scope.setdefault("state", {}))
        state["request_id"] = request_id

        started_at = time.perf_counter()
        status_code: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = cast(int, message["status"])
                headers = cast(list[tuple[bytes, bytes]], message.setdefault("headers", []))
                _set_response_request_id(headers, request_id)

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            log_event(
                logging.ERROR,
                "http.request.error",
                environment=self.environment,
                request_id=request_id,
                http_method=scope.get("method"),
                http_path=scope.get("path"),
                duration_ms=_elapsed_ms(started_at),
                error_type=exc.__class__.__name__,
            )
            raise

        log_event(
            logging.INFO,
            "http.request.completed",
            environment=self.environment,
            request_id=request_id,
            http_method=scope.get("method"),
            http_path=scope.get("path"),
            status_code=status_code,
            duration_ms=_elapsed_ms(started_at),
        )


def _request_id_from_scope(scope: Scope) -> str | None:
    headers = cast(list[tuple[bytes, bytes]], scope.get("headers", []))
    for name, value in headers:
        if name.lower() != _REQUEST_ID_HEADER_BYTES:
            continue
        try:
            request_id = value.decode("ascii")
        except UnicodeDecodeError:
            return None
        if _is_valid_request_id(request_id):
            return request_id
        return None
    return None


def _set_response_request_id(headers: list[tuple[bytes, bytes]], request_id: str) -> None:
    headers[:] = [
        (name, value) for name, value in headers if name.lower() != _REQUEST_ID_HEADER_BYTES
    ]
    headers.append((_REQUEST_ID_HEADER_BYTES, request_id.encode("ascii")))


def _new_request_id() -> str:
    return str(uuid4())


def _is_valid_request_id(request_id: str) -> bool:
    return bool(_REQUEST_ID_PATTERN.fullmatch(request_id))


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)
