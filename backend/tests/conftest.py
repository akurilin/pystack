from collections.abc import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from pystack_api.core.config import get_settings
from pystack_api.db.connection import DatabaseConnection, get_connection
from pystack_api.main import app

settings = get_settings()
test_conninfo = conninfo_to_dict(settings.test_database_url)
assert test_conninfo["dbname"] == "pystack_test", "Tests must only connect to pystack_test"


def override_get_connection() -> Generator[DatabaseConnection]:
    with psycopg.connect(settings.test_database_url) as connection:
        yield connection


app.dependency_overrides[get_connection] = override_get_connection


@pytest.fixture(autouse=True)
def clean_tasks() -> Generator[None]:
    with psycopg.connect(settings.test_database_url) as connection:
        connection.execute("DELETE FROM tasks")
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
