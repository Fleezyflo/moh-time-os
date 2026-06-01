"""Global ASGI auth + rate-limit middleware for the MOH TIME OS API (WS2).

AuthMiddleware enforces a shared-secret Bearer token on every request except a
small public allowlist (liveness, auth handshake, CORS preflight, static UI).
It is the single enforcement layer that protects the ~285 bare @app routes that
are not mounted via a router. Router-level Depends(require_auth) (api/server.py
include_router calls) is defense-in-depth on top of this.

RateLimitMiddleware throttles write/destructive HTTP methods per client key.
"""

import json
import logging
from datetime import datetime, timezone

from starlette.types import ASGIApp, Receive, Scope, Send

from api import auth
from lib.security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Methods that mutate state or trigger destructive/governance actions.
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _bearer_token(scope: Scope) -> str | None:
    """Extract the Bearer token from the ASGI scope headers, if present."""
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            raw = value.decode("latin-1")
            prefix = "Bearer "
            if raw.startswith(prefix):
                return raw[len(prefix) :].strip()
            return None
    return None


async def _send_json(send: Send, status: int, body: dict, extra_headers=None) -> None:
    """Emit a JSON error response through the raw ASGI send callable."""
    payload = json.dumps(body).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode("ascii")),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


class AuthMiddleware:
    """Enforce Bearer auth on every non-allowlisted HTTP request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")

        # CORS preflight and the public allowlist bypass auth.
        if method == "OPTIONS" or auth.is_public_path(path):
            await self.app(scope, receive, send)
            return

        token = _bearer_token(scope)
        if not auth.verify_token(token):
            detail = (
                "Authentication required. Provide Bearer token."
                if token is None
                else "Invalid API key."
            )
            await _send_json(
                send,
                401,
                {"detail": detail},
                extra_headers=[(b"www-authenticate", b"Bearer")],
            )
            return

        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Throttle write/destructive methods per client key (IP or token tail)."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None):
        self.app = app
        self.limiter = limiter or RateLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if method not in _WRITE_METHODS or auth.is_public_path(path):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "unknown"
        result = self.limiter.check_rate_limit(key=key, role="authenticated")
        if not result.allowed:
            retry_after = max(
                1, int((result.reset_at - datetime.now(timezone.utc)).total_seconds())
            )
            await _send_json(
                send,
                429,
                {"detail": "Rate limit exceeded. Slow down."},
                extra_headers=[
                    (b"retry-after", str(retry_after).encode("ascii")),
                    (b"x-ratelimit-limit", str(result.limit).encode("ascii")),
                ],
            )
            return

        await self.app(scope, receive, send)
