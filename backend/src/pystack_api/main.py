from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from clerk_backend_api import Clerk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pystack_api.api.router import api_router
from pystack_api.core.config import Settings, get_settings
from pystack_api.db.connection import DatabasePool, create_pool


def create_app(
    settings: Settings | None = None,
    database_pool: DatabasePool | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    Settings and the pool are injectable so tests can point the app at the test
    database and share a single pool across requests.
    """
    settings = settings or get_settings()
    # Initialize error monitoring before the app is built so the FastAPI/ASGI
    # integration hooks in. Gated on the DSN so dev and tests stay no-ops; the
    # value is supplied per-deployment (Render), never hardcoded.
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            # Conservative default for a clonable scaffold: do not attach client
            # IP or request headers to events. Flip on if richer context is worth
            # the PII tradeoff for your deployment.
            send_default_pii=False,
        )
    if database_pool is None:
        database_pool = create_pool(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        settings.validate_assistant_config()
        settings.validate_clerk_config()
        database_pool.open(wait=True)
        try:
            yield
        finally:
            database_pool.close()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database_pool = database_pool
    # One Clerk client per app verifies session tokens; it caches Clerk's JWKS
    # internally so per-request verification stays networkless after warm-up.
    app.state.clerk = Clerk(bearer_auth=settings.clerk_secret_key)
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
