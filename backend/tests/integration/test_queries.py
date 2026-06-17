import psycopg
import pytest

from pystack_api.core.config import get_settings
from pystack_api.queries import tasks
from pystack_api.queries.tasks import QUERY_CHECKS, QueryCheck

settings = get_settings()


def test_all_query_builders_have_schema_checks() -> None:
    query_builders = {
        value for name, value in vars(tasks).items() if name.endswith("_query") and callable(value)
    }
    checked_builders = {check.builder for check in QUERY_CHECKS}

    assert checked_builders == query_builders


@pytest.mark.parametrize("check", QUERY_CHECKS, ids=[check.name for check in QUERY_CHECKS])
def test_query_matches_database_schema(check: QueryCheck) -> None:
    query = check.build()

    with psycopg.connect(settings.test_database_url) as connection:
        # Plain EXPLAIN makes PostgreSQL parse, type-check, and plan without executing DML.
        connection.execute(t"EXPLAIN {query:q}").fetchall()
