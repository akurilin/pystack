from collections.abc import Callable, Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from pystack_api.api.auth import get_current_user_id
from pystack_api.core.config import get_settings
from pystack_api.main import create_app

settings = get_settings()
test_conninfo = conninfo_to_dict(settings.test_database_url)
assert test_conninfo["dbname"] == "pystack_test", "Tests must only connect to pystack_test"

# Auth is stubbed in tests: a dummy Clerk key lets the app boot, and the auth
# dependency is overridden per client to act as a fixed signed-in user instead of
# verifying a real Clerk token.
TEST_USER_ID = "user_test"


@pytest.fixture(autouse=True)
def clean_tasks() -> Generator[None]:
    with psycopg.connect(settings.test_database_url) as connection:
        connection.execute("DELETE FROM tasks")
    yield


def _build_client(user_id: str) -> TestClient:
    test_settings = settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "openrouter_api_key": "test-openrouter-key",
            "clerk_secret_key": "sk_test_dummy",
        }
    )
    app = create_app(test_settings)
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    return TestClient(app)


@pytest.fixture
def client() -> Generator[TestClient]:
    with _build_client(TEST_USER_ID) as test_client:
        yield test_client


@pytest.fixture
def client_as() -> Generator[Callable[[str], TestClient]]:
    """Build a signed-in client for an arbitrary user id (for cross-user tests)."""
    open_clients: list[TestClient] = []

    def factory(user_id: str) -> TestClient:
        test_client = _build_client(user_id)
        test_client.__enter__()
        open_clients.append(test_client)
        return test_client

    yield factory
    for test_client in open_clients:
        test_client.__exit__(None, None, None)
