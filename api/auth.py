"""
API Authentication for MOH TIME OS.

Single-user personal system — auth is a passthrough on localhost.
The require_auth / optional_auth dependencies exist so routers don't
need to change if real auth is added later.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Security scheme kept for OpenAPI docs
security = HTTPBearer(auto_error=False)

# Fixed identity — single user system
_USER_ID = "molham"
_ROLE = "owner"
_TOKEN = "local"  # noqa: S105 — not a real credential, localhost passthrough


async def require_auth(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str:
    """Always passes. Attaches owner role to request state."""
    request.state.role = _ROLE
    return _TOKEN


async def optional_auth(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str | None:
    """Always returns the local token."""
    request.state.role = _ROLE
    return _TOKEN


def is_auth_enabled() -> bool:
    """Auth is effectively disabled for localhost single-user."""
    return False


# ── Auth Router ──────────────────────────────────────────────────────


class AuthModeResponse(BaseModel):
    """Auth mode response."""

    mode: str


class TokenResponse(BaseModel):
    """Response body for token exchange (kept for UI compatibility)."""

    token: str
    role: str
    user_id: str


auth_router = APIRouter(tags=["auth"])


@auth_router.get("/auth/mode", response_model=AuthModeResponse)
async def get_auth_mode() -> dict:
    """Always dev mode — single-user system."""
    return {"mode": "dev"}


@auth_router.post("/auth/token", response_model=TokenResponse)
async def exchange_token() -> TokenResponse:
    """Accept any request — return fixed owner identity."""
    return TokenResponse(token=_TOKEN, role=_ROLE, user_id=_USER_ID)
