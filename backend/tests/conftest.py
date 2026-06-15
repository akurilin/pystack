from collections.abc import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from pystack_api.core.config import get_settings
from pystack_api.main import create_app

settings = get_settings()
test_conninfo = conninfo_to_dict(settings.test_database_url)
assert test_conninfo["dbname"] == "pystack_test", "Tests must only connect to pystack_test"


@pytest.fixture(autouse=True)
def clean_tasks() -> Generator[None]:
    with psycopg.connect(settings.test_database_url) as connection:
        connection.execute("DELETE FROM tasks")
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    test_settings = settings.model_copy(update={"database_url": settings.test_database_url})
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
