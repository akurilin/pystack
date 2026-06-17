"""Clerk-backed request authentication.

Every data endpoint requires a signed-in Clerk user; there is no anonymous
access. `get_current_user_id` verifies the session token on the incoming request
and returns the Clerk user ID (the JWT `sub` claim, e.g. `user_2ab...`), which
the services use to scope all database access to that user's own board.
"""

from http import HTTPStatus
from typing import Annotated, cast

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Depends, HTTPException, Request

from pystack_api.core.config import Settings


def get_current_user_id(request: Request) -> str:
    clerk = cast(Clerk, request.app.state.clerk)
    settings = cast(Settings, request.app.state.settings)

    # Clerk's SDK verifies against an httpx.Request, so mirror the incoming
    # request's method, URL, and headers (where the session token lives).
    clerk_request = httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=request.headers.raw,
    )
    request_state = clerk.authenticate_request(
        clerk_request,
        AuthenticateRequestOptions(authorized_parties=settings.clerk_authorized_parties),
    )

    if not request_state.is_signed_in or not request_state.payload:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail=request_state.message or "Not authenticated",
        )

    user_id = request_state.payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Authenticated token is missing a user id",
        )
    return user_id


UserIdDependency = Annotated[str, Depends(get_current_user_id)]
