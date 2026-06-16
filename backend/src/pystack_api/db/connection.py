from collections.abc import Generator
from typing import Any, cast

from fastapi import Request
from psycopg import Connection
from psycopg_pool import ConnectionPool

type DatabaseConnection = Connection[tuple[Any, ...]]
type DatabasePool = ConnectionPool[DatabaseConnection]


def create_pool(database_url: str) -> DatabasePool:
    """Build a closed pool; the app lifespan opens it so import never touches the DB."""
    return ConnectionPool(database_url, min_size=1, open=False)


def get_connection(request: Request) -> Generator[DatabaseConnection]:
    pool = cast(DatabasePool, request.app.state.database_pool)
    with pool.connection() as connection:
        yield connection
