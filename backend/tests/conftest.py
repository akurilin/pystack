from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from pystack_api.core.config import get_settings
from pystack_api.db.base import Base
from pystack_api.db.session import get_session
from pystack_api.main import app
from pystack_api.models import Task

settings = get_settings()
test_url = make_url(settings.test_database_url)
assert test_url.database == "pystack_test", "Tests must only connect to pystack_test"

test_engine = create_engine(settings.test_database_url)
test_session_factory = sessionmaker(bind=test_engine, expire_on_commit=False)


def override_get_session() -> Generator[Session]:
    with test_session_factory() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


@pytest.fixture(scope="session", autouse=True)
def create_test_schema() -> Generator[None]:
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture(autouse=True)
def clean_tasks() -> Generator[None]:
    with test_session_factory.begin() as session:
        session.execute(delete(Task))
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
