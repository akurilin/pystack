from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pystack_api.api.router import api_router
from pystack_api.core.config import Settings, get_settings
from pystack_api.db.connection import DatabasePool, create_pool


def create_app(
    settings: Settings | None = None,
    database_pool: DatabasePool | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if database_pool is None:
        database_pool = create_pool(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database_pool.open(wait=True)
        try:
            yield
        finally:
            database_pool.close()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.database_pool = database_pool
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
