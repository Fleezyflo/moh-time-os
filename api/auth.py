"""
API Authentication for MOH TIME OS.

Simple token-based authentication for intelligence endpoints.
Token is configured via INTEL_API_TOKEN environment variable.

Usage:
    from api.auth import require_auth

    @router.get("/protected", dependencies=[Depends(require_auth)])
    def protected_endpoint():
        ...
"""

import logging
import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)


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

    Returns the validated token on success.
    Raises HTTPException 401 on failure.

    If INTEL_API_TOKEN is not set, authentication is DISABLED and a
    warning is logged. This allows development without auth but should
    never happen in production.
    """
    expected_token = _get_token_from_env()

    # If no token configured, WARN but allow (development mode)
    if not expected_token:
        logger.warning(
            "INTEL_API_TOKEN not set - authentication disabled! "
            "Set this environment variable in production."
        )
        return "auth_disabled"

    # Get token from request
    provided_token = _get_token_from_request(request)

    if not provided_token:
        logger.warning(f"Auth failed: no token provided for {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to prevent timing attacks
    import secrets

    if not secrets.compare_digest(provided_token, expected_token):
        logger.warning(f"Auth failed: invalid token for {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token


async def optional_auth(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str | None:
    """
    Dependency that checks auth but doesn't require it.

    Returns the token if valid, None if no token provided.
    Raises HTTPException 401 only if token is provided but invalid.

    Useful for endpoints that behave differently for authed vs unauthed.
    """
    expected_token = _get_token_from_env()

    if not expected_token:
        return None  # Auth disabled

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

    return provided_token


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(_get_token_from_env())
