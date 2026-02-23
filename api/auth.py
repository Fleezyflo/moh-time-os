"""
API Authentication for MOH TIME OS.

Multi-key authentication system with backward compatibility for legacy INTEL_API_TOKEN.

Supports two modes:
1. Legacy mode: INTEL_API_TOKEN env var (single shared token)
2. Multi-key mode: API keys stored in database (production-grade)

Token extraction order:
1. Authorization: Bearer <token> header
2. X-API-Token header
3. api_token query parameter (for testing)

Usage:
    from api.auth import require_auth

    @router.get("/protected", dependencies=[Depends(require_auth)])
    def protected_endpoint(request: Request):
        # request.state.role will contain the key's role if using multi-key auth
        ...
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from lib.security import KeyManager

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)

# Lazy-initialized key manager (only if not using legacy mode)
_key_manager: KeyManager | None = None


def _get_key_manager() -> KeyManager | None:
    """Get or initialize the key manager (None if using legacy mode)."""
    global _key_manager
    # Only use multi-key auth if not using legacy INTEL_API_TOKEN
    if os.environ.get("INTEL_API_TOKEN"):
        return None
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def _get_token_from_env() -> str | None:
    """Get the expected token from environment."""
    return os.environ.get("INTEL_API_TOKEN")


def _get_token_from_request(request: Request) -> str | None:
    """
    Extract token from request.

    Checks in order:
    1. Authorization: Bearer <token> header
    2. X-API-Token header (alternative)
    3. api_token query parameter (for testing/debugging)
    """
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]  # Strip "Bearer "

    # Check X-API-Token header
    x_token = request.headers.get("X-API-Token")
    if x_token:
        return x_token

    # Check query parameter (useful for quick testing)
    query_token = request.query_params.get("api_token")
    if query_token:
        return query_token

    return None


async def require_auth(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str:
    """
    Dependency that requires valid authentication.

    Supports two authentication modes:
    1. Legacy mode (INTEL_API_TOKEN set): Uses plaintext env var
    2. Multi-key mode: Validates against database API keys

    Returns the validated token/key on success.
    Raises HTTPException 401 on failure.
    Attaches request.state.role if multi-key auth succeeds.

    If neither mode is configured, WARNS but allows (development mode).
    """
    # Try legacy mode first
    expected_token = _get_token_from_env()

    if expected_token:
        # Legacy mode: validate against INTEL_API_TOKEN
        provided_token = _get_token_from_request(request)

        if not provided_token:
            logger.warning(f"Auth failed: no token provided for {request.url.path}")
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide Bearer token in Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Constant-time comparison
        import secrets

        if not secrets.compare_digest(provided_token, expected_token):
            logger.warning(f"Auth failed: invalid token for {request.url.path}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(f"Legacy auth succeeded for {request.url.path}")
        return provided_token

    # Try multi-key mode
    manager = _get_key_manager()
    if manager:
        provided_token = _get_token_from_request(request)

        if not provided_token:
            logger.warning(f"Auth failed: no token provided for {request.url.path}")
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide Bearer token in Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate key
        key_info = manager.validate_key(provided_token)
        if not key_info:
            logger.warning(f"Auth failed: invalid key for {request.url.path}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Attach role to request state
        request.state.role = key_info.role
        logger.debug(
            f"Multi-key auth succeeded for {request.url.path} (key={key_info.name}, role={key_info.role.value})"
        )
        return provided_token

    # No auth configured
    logger.warning(
        "INTEL_API_TOKEN not set and no API keys configured - authentication disabled! "
        "Configure either INTEL_API_TOKEN or create API keys in production."
    )
    return "auth_disabled"


async def optional_auth(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str | None:
    """
    Dependency that checks auth but doesn't require it.

    Supports both legacy and multi-key modes (see require_auth for details).

    Returns the token/key if valid, None if no token provided.
    Raises HTTPException 401 only if token is provided but invalid.
    Attaches request.state.role if multi-key auth succeeds.

    Useful for endpoints that behave differently for authed vs unauthed.
    """
    # Try legacy mode first
    expected_token = _get_token_from_env()

    if expected_token:
        provided_token = _get_token_from_request(request)

        if not provided_token:
            return None  # No token is OK for optional auth

        # Token provided - must be valid
        import secrets

        if not secrets.compare_digest(provided_token, expected_token):
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(f"Legacy optional auth succeeded for {request.url.path}")
        return provided_token

    # Try multi-key mode
    manager = _get_key_manager()
    if manager:
        provided_token = _get_token_from_request(request)

        if not provided_token:
            return None  # No token is OK for optional auth

        # Token provided - must be valid
        key_info = manager.validate_key(provided_token)
        if not key_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.role = key_info.role
        logger.debug(f"Multi-key optional auth succeeded for {request.url.path}")
        return provided_token

    # Auth disabled
    return None


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(_get_token_from_env())


# ── Auth Router (token exchange endpoint) ──────────────────────────


class TokenRequest(BaseModel):
    """Request body for token exchange."""

    api_key: str


class TokenResponse(BaseModel):
    """Response body for token exchange."""

    token: str
    role: str
    user_id: str


auth_router = APIRouter(tags=["auth"])


@auth_router.post("/auth/token", response_model=TokenResponse)
async def exchange_token(body: TokenRequest) -> TokenResponse:
    """
    Exchange an API key for a bearer token.

    In legacy mode (INTEL_API_TOKEN set), validates the key matches.
    In multi-key mode, validates against the database.
    If no auth is configured, accepts any key (dev mode).
    """
    api_key = body.api_key

    # Legacy mode: validate against INTEL_API_TOKEN
    expected = _get_token_from_env()
    if expected:
        import secrets

        if not secrets.compare_digest(api_key, expected):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return TokenResponse(token=api_key, role="owner", user_id="molham")

    # Multi-key mode: validate against database
    manager = _get_key_manager()
    if manager:
        # Check if any keys actually exist in the database
        existing_keys = manager.list_keys(active_only=True)
        if existing_keys:
            key_info = manager.validate_key(api_key)
            if not key_info:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return TokenResponse(token=api_key, role=key_info.role.value, user_id=key_info.name)
        # No keys in DB — fall through to dev mode

    # No auth configured (dev mode): accept any key
    logger.warning("Auth not configured — accepting any API key (dev mode)")
    return TokenResponse(token=api_key, role="owner", user_id="molham")
