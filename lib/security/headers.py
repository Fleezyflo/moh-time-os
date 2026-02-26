"""
Security headers middleware for FastAPI.

Provides:
- CORS (Cross-Origin Resource Sharing) configuration
- CSP (Content Security Policy) headers
- Additional security headers (HSTS, X-Frame-Options, etc.)

Usage in server.py:
    from lib.security.headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
"""

import logging
import os

logger = logging.getLogger(__name__)

# Default CORS origins (can be overridden via CORS_ORIGINS env var)
DEFAULT_CORS_ORIGINS = "http://localhost:*"

# CORS configuration
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Authorization", "Content-Type", "X-API-Token"]
CORS_MAX_AGE = 3600

# CSP policy
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'"
)

# Additional security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def parse_cors_origins(origins_str: str) -> list[str]:
    """
    Parse CORS origins from environment variable format.

    Args:
        origins_str: Comma-separated list of origins, or "*" for all origins

    Returns:
        List of allowed origins
    """
    if origins_str == "*":
        return ["*"]

    origins = []
    for origin in origins_str.split(","):
        origin = origin.strip()
        if origin:
            origins.append(origin)

    return origins if origins else ["http://localhost:*"]


def is_cors_allowed(origin: str, allowed_origins: list[str]) -> bool:
    """
    Check if an origin is allowed by CORS policy.

    Supports wildcard patterns like "http://localhost:*" and exact matches.

    Args:
        origin: Origin header from request
        allowed_origins: List of allowed origins

    Returns:
        True if origin is allowed
    """
    if "*" in allowed_origins:
        return True

    for allowed in allowed_origins:
        if allowed == "*":
            return True
        if allowed.endswith("*"):
            # Handle wildcard patterns like "http://localhost:*"
            prefix = allowed[:-1]  # Remove the "*"
            if origin.startswith(prefix):
                return True
        elif allowed == origin:
            return True

    return False


class SecurityHeadersMiddleware:
    """
    Starlette-compatible ASGI middleware for security headers.

    Adds:
    - CORS headers (based on CORS_ORIGINS env var)
    - Content Security Policy header
    - Additional security headers (HSTS, X-Frame-Options, etc.)
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: ASGI application
        """
        self.app = app

        # Parse CORS origins from environment
        cors_origins_env = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
        self.allowed_origins = parse_cors_origins(cors_origins_env)

        logger.debug(f"SecurityHeadersMiddleware initialized with origins: {self.allowed_origins}")

    async def __call__(self, scope, receive, send):
        """
        Process HTTP requests and add security headers.

        Args:
            scope: ASGI scope dict
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request headers
        request_headers = dict(scope.get("headers", []))
        origin = None
        for key, value in request_headers.items():
            if key.lower() == b"origin":
                origin = value.decode("utf-8", errors="ignore")
                break

        async def send_with_headers(message):
            """Wrap send to inject security headers."""
            if message["type"] == "http.response.start":
                # Extract headers from response
                headers = list(message.get("headers", []))

                # Add CORS headers if origin is provided
                if origin and is_cors_allowed(origin, self.allowed_origins):
                    headers.append((b"access-control-allow-origin", origin.encode()))
                    headers.append(
                        (b"access-control-allow-methods", ",".join(CORS_ALLOWED_METHODS).encode())
                    )
                    headers.append(
                        (b"access-control-allow-headers", ",".join(CORS_ALLOWED_HEADERS).encode())
                    )
                    headers.append((b"access-control-max-age", str(CORS_MAX_AGE).encode()))
                    headers.append((b"access-control-allow-credentials", b"true"))

                # Add CSP header
                headers.append((b"content-security-policy", CSP_POLICY.encode()))

                # Add other security headers
                for header_name, header_value in SECURITY_HEADERS.items():
                    headers.append((header_name.lower().encode(), header_value.encode()))

                # Update message with new headers
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
