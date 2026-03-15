"""
API Authentication for MOH TIME OS.

Single-user personal system with shared-secret API key protection.
Enforces Bearer token auth on all mutation endpoints. The API key is
read from MOH_TIME_OS_API_KEY env var; if unset, a random key is
generated on startup and logged once so the operator can use it.

This is NOT production-grade OAuth or session management. It is the
minimum viable boundary that prevents unauthenticated access to
destructive/governance/export/action surfaces — including when the
server is accidentally bound to a non-localhost interface.
"""

import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Security scheme — auto_error=False so we can give custom 401 messages
security = HTTPBearer(auto_error=False)

# Fixed identity — single user system
_USER_ID = "molham"
_ROLE = "owner"

# API key: from environment or generated at startup
_API_KEY: str = os.environ.get("MOH_TIME_OS_API_KEY", "")
if not _API_KEY:
    _API_KEY = secrets.token_urlsafe(32)
    logger.warning(
        "MOH_TIME_OS_API_KEY not set. Generated ephemeral key (set env var for persistence): %s",
        _API_KEY,
    )


def _get_api_key() -> str:
    """Return the active API key (testable seam)."""
    return _API_KEY


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """
    Enforce Bearer token auth.

    Rejects requests without a valid Bearer token matching the API key.
    Attaches user identity to request state on success.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(credentials.credentials, _get_api_key()):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.role = _ROLE
    request.state.user_id = _USER_ID
    return credentials.credentials


async def optional_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """
    Optional auth — attaches identity if Bearer token is valid,
    returns None if no token provided. Rejects invalid tokens.
    """
    if credentials is None:
        request.state.role = "anonymous"
        return None

    if not secrets.compare_digest(credentials.credentials, _get_api_key()):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.role = _ROLE
    request.state.user_id = _USER_ID
    return credentials.credentials


def is_auth_enabled() -> bool:
    """Auth is always enabled."""
    return True


# ── Auth Router ──────────────────────────────────────────────────────


class AuthModeResponse(BaseModel):
    """Auth mode response."""

    mode: str
    auth_required: bool


class TokenResponse(BaseModel):
    """Response body for token exchange (kept for UI compatibility)."""

    token: str
    role: str
    user_id: str


auth_router = APIRouter(tags=["auth"])


@auth_router.get("/auth/mode", response_model=AuthModeResponse)
async def get_auth_mode() -> dict:
    """Report auth mode — always requires Bearer token."""
    return {"mode": "api_key", "auth_required": True}


@auth_router.post("/auth/token", response_model=TokenResponse)
async def exchange_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenResponse:
    """
    Exchange Bearer token for user identity.

    Validates the API key and returns user info on success.
    """
    if credentials is None or not secrets.compare_digest(credentials.credentials, _get_api_key()):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(token=credentials.credentials, role=_ROLE, user_id=_USER_ID)
