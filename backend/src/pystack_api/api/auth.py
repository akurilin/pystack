"""Clerk-backed request authentication.

Every data endpoint requires a signed-in Clerk user; there is no anonymous
access. `get_current_user_id` verifies the session token on the incoming request
and returns the Clerk user ID (the JWT `sub` claim, e.g. `user_2ab...`), which
the services use to scope all database access to that user's own board.

A bad or missing token yields 401. A failure to reach or use Clerk's signing
keys yields 503 instead, so a Clerk outage is retryable and distinguishable from
a genuine auth failure (mirroring how /health reports a down database).
"""

from http import HTTPStatus
from typing import Annotated, cast

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import (
    AuthenticateRequestOptions,
    TokenVerificationErrorReason,
)
from fastapi import Depends, HTTPException, Request

from pystack_api.core.config import Settings

# Verification reasons that mean "we couldn't reach or use Clerk's signing keys"
# rather than "the token is bad". These map to 503 (transient/retryable) instead
# of 401, so a Clerk outage isn't misreported as the user being signed out.
_SERVICE_UNAVAILABLE_REASONS = {
    TokenVerificationErrorReason.JWK_FAILED_TO_LOAD,
    TokenVerificationErrorReason.JWK_REMOTE_INVALID,
    TokenVerificationErrorReason.JWK_FAILED_TO_RESOLVE,
    TokenVerificationErrorReason.SERVER_ERROR,
}


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
    # ["*"] is an explicit opt-out: the SDK reads authorized_parties=None as
    # "accept any origin", so we translate the sentinel here. Any other value —
    # including the default or an empty list — is enforced, keeping the gate
    # closed unless someone deliberately opens it.
    authorized_parties = (
        None if settings.clerk_authorized_parties == ["*"] else settings.clerk_authorized_parties
    )
    request_state = clerk.authenticate_request(
        clerk_request,
        AuthenticateRequestOptions(authorized_parties=authorized_parties),
    )

    if not request_state.is_signed_in or not request_state.payload:
        status_code = (
            HTTPStatus.SERVICE_UNAVAILABLE
            if request_state.reason in _SERVICE_UNAVAILABLE_REASONS
            else HTTPStatus.UNAUTHORIZED
        )
        raise HTTPException(
            status_code=status_code,
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
