from collections.abc import Generator
from threading import Lock
from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool

from pystack_api.core.config import get_settings

type DatabaseConnection = Connection[tuple[Any, ...]]

_pool: ConnectionPool[DatabaseConnection] | None = None
_pool_lock = Lock()


def get_pool() -> ConnectionPool[DatabaseConnection]:
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                pool: ConnectionPool[DatabaseConnection] = ConnectionPool(
                    get_settings().database_url,
                    min_size=1,
                    open=False,
                )
                pool.open(wait=True)
                _pool = pool

    assert _pool is not None
    return _pool


def close_pool() -> None:
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


def get_connection() -> Generator[DatabaseConnection]:
    with get_pool().connection() as connection:
        yield connection
