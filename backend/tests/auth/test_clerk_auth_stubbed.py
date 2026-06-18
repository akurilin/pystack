"""Stubbed-Clerk tests for auth failure branches a real token can't reach.

The companion ``test_clerk_auth.py`` proves the happy path and token rejections
with real Clerk-minted tokens. The branches here either can't be produced from a
valid token (expired, wrong ``azp``, a signed-in token missing ``sub``) or can't
be produced from real Clerk at all (a JWKS-load failure — Clerk always serves its
keys). So we stub the Clerk client to return the exact ``RequestState`` each
branch needs and assert how ``get_current_user_id`` maps it to an HTTP status.

This module is fully offline: no network, no Clerk credentials, no database.
"""

import pytest
from clerk_backend_api.security.types import (
    AuthErrorReason,
    AuthStatus,
    RequestState,
    TokenVerificationErrorReason,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pystack_api.api.auth import UserIdDependency
from pystack_api.core.config import get_settings


class _StubClerk:
    """Stands in for the real Clerk client. ``authenticate_request`` ignores the
    request and returns a preset ``RequestState`` (or raises a preset error), so a
    test can drive any verification outcome deterministically."""

    def __init__(self, result: RequestState | Exception) -> None:
        self._result = result

    def authenticate_request(self, request: object, options: object) -> RequestState:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _client(result: RequestState | Exception) -> TestClient:
    settings = get_settings().model_copy(update={"clerk_authorized_parties": ["*"]})
    app = FastAPI()
    app.state.settings = settings
    app.state.clerk = _StubClerk(result)

    @app.get("/whoami")
    def whoami(current_user: UserIdDependency) -> dict[str, str]:
        return {"user_id": current_user}

    # raise_server_exceptions=False so an escaping error surfaces as a 500
    # response we can assert on, rather than propagating into the test.
    return TestClient(app, raise_server_exceptions=False)


# Reasons that signal a Clerk-side/infra failure -> 503.
_SERVICE_UNAVAILABLE_REASONS = [
    TokenVerificationErrorReason.JWK_FAILED_TO_LOAD,
    TokenVerificationErrorReason.JWK_REMOTE_INVALID,
    TokenVerificationErrorReason.JWK_FAILED_TO_RESOLVE,
    TokenVerificationErrorReason.SERVER_ERROR,
]

# Reasons that signal a bad/missing token -> 401. Includes the originally
# un-testable expired and wrong-azp cases, plus a couple of neighbours.
_UNAUTHORIZED_REASONS: list[AuthErrorReason | TokenVerificationErrorReason] = [
    TokenVerificationErrorReason.TOKEN_EXPIRED,
    TokenVerificationErrorReason.TOKEN_INVALID_AUTHORIZED_PARTIES,
    TokenVerificationErrorReason.TOKEN_INVALID_SIGNATURE,
    AuthErrorReason.SESSION_TOKEN_MISSING,
]


@pytest.mark.parametrize("reason", _SERVICE_UNAVAILABLE_REASONS)
def test_clerk_infra_failure_returns_503(reason: TokenVerificationErrorReason) -> None:
    state = RequestState(status=AuthStatus.SIGNED_OUT, reason=reason)
    assert _client(state).get("/whoami").status_code == 503


@pytest.mark.parametrize("reason", _UNAUTHORIZED_REASONS)
def test_bad_token_returns_401(reason: AuthErrorReason | TokenVerificationErrorReason) -> None:
    state = RequestState(status=AuthStatus.SIGNED_OUT, reason=reason)
    assert _client(state).get("/whoami").status_code == 401


def test_signed_in_without_sub_returns_401() -> None:
    # Verified token, but the payload carries no `sub` — our explicit guard.
    state = RequestState(status=AuthStatus.SIGNED_IN, payload={"not_sub": "x"})
    assert _client(state).get("/whoami").status_code == 401


def test_unexpected_clerk_error_returns_500() -> None:
    # A non-TokenVerificationError escaping the SDK isn't an auth failure: it
    # propagates and FastAPI returns 500 (captured by Sentry in production).
    assert _client(RuntimeError("boom")).get("/whoami").status_code == 500
