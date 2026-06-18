"""Real-token integration tests for Clerk authentication.

Unlike the rest of the suite (which stubs auth via ``dependency_overrides``),
these tests run the *real* ``get_current_user_id`` against real Clerk-minted
session tokens, with no browser involved. Tokens are minted entirely through
Clerk's Backend API:

    create session (POST /sessions) -> create token (POST /sessions/{id}/tokens)

``POST /sessions`` is a development-instance-only endpoint, which is exactly the
kind of instance these tests target. Because no frontend sign-in flow is used,
there is no bot detection and the ``__clerk_testing_token`` parameter is not
needed here.

These tests require a Clerk dev instance and a test user, and they fail loudly
(rather than skipping) when the env vars are absent, so a misconfigured
environment is obvious instead of silently uncovered.

Several failure branches cannot be reached with a real backend-minted token; they
are documented as skipped tests at the bottom of this file rather than faked, so
the coverage gap stays explicit.
"""

import pytest
from clerk_backend_api import Clerk
from clerk_backend_api.models import CreateSessionRequestBody, GetUserListRequest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pystack_api.api.auth import UserIdDependency
from pystack_api.core.config import get_settings


class _AuthTestConfig(BaseSettings):
    """Clerk credentials these tests need, read from the same repo-root .env the
    app uses. Kept separate from the app ``Settings`` because the e2e test-user
    variable is unprefixed and has no place in production config."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    clerk_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PYSTACK_CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
    )
    # The identifier (username or email) of the dedicated Clerk test user, reused
    # from the Playwright e2e suite. We resolve it to a Clerk user id below.
    clerk_test_user_username: str | None = None


@pytest.fixture(scope="module")
def auth_config() -> _AuthTestConfig:
    config = _AuthTestConfig()
    missing = [
        name
        for name, value in (
            ("PYSTACK_CLERK_SECRET_KEY", config.clerk_secret_key),
            ("CLERK_TEST_USER_USERNAME", config.clerk_test_user_username),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Clerk auth tests require these env vars (set them in the repo-root "
            f".env): {', '.join(missing)}. Create a Clerk dev instance and a test "
            "user, then add their keys."
        )
    return config


@pytest.fixture(scope="module")
def clerk(auth_config: _AuthTestConfig) -> Clerk:
    return Clerk(bearer_auth=auth_config.clerk_secret_key)


@pytest.fixture(scope="module")
def user_id(clerk: Clerk, auth_config: _AuthTestConfig) -> str:
    """Resolve the test user's Clerk id from the configured identifier."""
    users = clerk.users.list(request=GetUserListRequest(query=auth_config.clerk_test_user_username))
    if len(users) != 1:
        raise RuntimeError(
            f"Expected exactly one Clerk user matching "
            f"{auth_config.clerk_test_user_username!r}, found {len(users)}."
        )
    return users[0].id


@pytest.fixture
def client() -> TestClient:
    """A minimal app with one authenticated route wired to the real Clerk
    dependency. We deliberately avoid ``create_app()`` so these tests need
    neither the database nor the assistant config — only auth is under test.

    ``authorized_parties`` is set to the ["*"] opt-out because backend-minted
    tokens carry no ``azp`` claim, which any real allowlist would (correctly)
    reject. ``raise_server_exceptions=False`` lets us assert on 5xx responses
    instead of the exception propagating.
    """
    settings = get_settings().model_copy(update={"clerk_authorized_parties": ["*"]})
    app = FastAPI()
    app.state.settings = settings
    app.state.clerk = Clerk(bearer_auth=settings.clerk_secret_key)

    @app.get("/whoami")
    def whoami(current_user: UserIdDependency) -> dict[str, str]:
        return {"user_id": current_user}

    return TestClient(app, raise_server_exceptions=False)


def _mint_token(clerk: Clerk, user_id: str) -> str:
    """Mint a fresh, real session-token JWT for the user. Clerk session tokens
    live ~60s, so mint immediately before use."""
    session = clerk.sessions.create(request=CreateSessionRequestBody(user_id=user_id))
    token = clerk.sessions.create_token(session_id=session.id)
    assert token.jwt is not None, "Clerk returned no JWT for the session token"
    return token.jwt


def test_valid_token_authenticates(client: TestClient, clerk: Clerk, user_id: str) -> None:
    token = _mint_token(clerk, user_id)
    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user_id"] == user_id


def test_tampered_token_is_rejected(client: TestClient, clerk: Clerk, user_id: str) -> None:
    """A real token with a corrupted signature is well-formed but must fail
    signature verification."""
    header, payload, signature = _mint_token(clerk, user_id).split(".")
    flipped = ("B" if signature[0] == "A" else "A") + signature[1:]
    tampered = ".".join([header, payload, flipped])
    response = client.get("/whoami", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_missing_authorization_header_is_rejected(client: TestClient) -> None:
    response = client.get("/whoami")
    assert response.status_code == 401


def test_malformed_token_is_rejected(client: TestClient) -> None:
    response = client.get("/whoami", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


# Failure branches a real backend-minted token can't reach — expired, wrong
# azp, Clerk JWKS-load failure (-> 503), and a signed-in token missing `sub` —
# are covered with a stubbed Clerk client in test_clerk_auth_stubbed.py.
