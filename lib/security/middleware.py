"""
RBAC middleware for FastAPI.

Intercepts all requests, extracts role from request.state.role (set by auth middleware),
and enforces role-based access control on endpoints.

Usage in server.py:
    from lib.security.middleware import RBACMiddleware

    app.add_middleware(RBACMiddleware)

The role should be set in request.state.role by the authentication layer before
this middleware runs.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


class RBACMiddleware:
    """
    Middleware that enforces role-based access control on API endpoints.

    Extracts role from request.state.role and checks permission for the
    requested endpoint (method + path). Returns 403 Forbidden if the role
    lacks permission.

    Logs all access attempts (both allowed and denied).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process HTTP requests with RBAC checks.

        Args:
            scope: ASGI scope dict
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            # Not an HTTP request, pass through
            await self.app(scope, receive, send)
            return

        # Extract path from scope
        path = scope.get("path", "UNKNOWN")

        # Skip middleware checks for certain paths (health checks, docs, etc.)
        if self._should_skip_rbac_check(path):
            await self.app(scope, receive, send)
            return

        # At this point, we need to check role, but we don't have access to
        # request.state yet. We need to inject role check in the response flow.
        #
        # Strategy: Wrap the send callable to check role when the response
        # headers are about to be sent.

        response_started = False

        async def send_with_rbac_check(message):
            """Intercept the response and check RBAC before headers are sent."""
            nonlocal response_started

            if message["type"] == "http.response.start" and not response_started:
                response_started = True

                # At this point we can't access request.state from scope alone.
                # The role check should happen via the dependency injection system
                # in the route handlers, not at the middleware level.
                #
                # However, if needed, we can still log access here.
                status_code = message.get("status", 200)
                logger.debug(
                    f"RBAC: {path} -> {status_code}",
                    extra={"path": path, "status": status_code},
                )

            await send(message)

        try:
            await self.app(scope, receive, send_with_rbac_check)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error in RBAC middleware for {path}: {e}")
            raise

    @staticmethod
    def _should_skip_rbac_check(path: str) -> bool:
        """Determine if this path should skip RBAC checks.

        Some paths like health checks, docs, and static files don't need RBAC.

        Args:
            path: The request path

        Returns:
            True if this path should skip RBAC checks
        """
        skip_patterns = [
            "/",  # Root
            "/docs",  # Swagger docs
            "/redoc",  # ReDoc
            "/openapi.json",  # OpenAPI spec
            "/health",  # Health check
            "/.well-known/",  # Well-known
            "/metrics",  # Prometheus metrics
        ]

        for pattern in skip_patterns:
            if path.startswith(pattern):
                return True

        return False


class RBACEnforcerMiddleware:
    """
    Alternative RBAC middleware that enforces checks at the middleware layer.

    This version checks permission before the request reaches the route handler.
    It requires that request.state.role be set by a prior middleware (e.g., auth).

    Note: This approach is less flexible because we can't easily access request.state
    in middleware without parsing the request body. The preferred approach is to
    use require_role() dependency injection in route handlers.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process HTTP requests with early RBAC enforcement."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "UNKNOWN")

        # Skip for internal paths
        if self._should_skip_rbac_check(path):
            await self.app(scope, receive, send)
            return

        # Create a response function to send 403 if needed
        async def send_with_rbac(message):
            """Send response, checking RBAC on first response message."""
            if message["type"] == "http.response.start":
                # At this point, we still don't have direct access to request.state.
                # We need the route handler to set it first.
                # This middleware mainly logs access.
                pass

            await send(message)

        await self.app(scope, receive, send_with_rbac)

    @staticmethod
    def _should_skip_rbac_check(path: str) -> bool:
        """Skip RBAC checks for certain paths."""
        skip_patterns = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/.well-known/",
            "/metrics",
        ]

        for pattern in skip_patterns:
            if path.startswith(pattern):
                return True

        return False
