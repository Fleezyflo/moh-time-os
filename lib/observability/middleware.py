"""
FastAPI middleware for observability metrics and correlation ID tracking.
"""

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class RequestMetricsMiddleware:
    """
    Middleware to track request duration and active request count.

    Tracks:
    - http_request_duration_seconds histogram
    - http_active_requests gauge
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from lib.observability.metrics import active_requests, request_duration_histogram

        # Increment active requests
        active_requests.inc()

        # Track timing
        start_time = time.perf_counter()

        async def send_with_timing(message):
            if message["type"] == "http.response.start":
                # Record timing when response starts
                duration = time.perf_counter() - start_time
                request_duration_histogram.observe(duration)

            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            # Decrement active requests
            active_requests.dec()


class CorrelationIdMiddleware:
    """
    Middleware for adding request ID to logs.

    Usage in server.py:
        from lib.observability.middleware import CorrelationIdMiddleware
        app.add_middleware(CorrelationIdMiddleware)

    All logs within a request will include the request_id in context.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from lib.observability.context import RequestContext, generate_request_id

        request_id = None

        # Check for X-Request-ID header
        headers = dict(scope.get("headers", []))
        for key, value in headers.items():
            if key.lower() == b"x-request-id":
                try:
                    request_id = value.decode("utf-8")
                    break
                except Exception as e:
                    logger.warning(f"Could not decode X-Request-ID header: {e}")
                    break

        # Generate if not provided
        if not request_id:
            request_id = generate_request_id()

        # Add X-Request-ID to response headers
        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-request-id", request_id.encode("utf-8")))
                message["headers"] = headers_list
            await send(message)

        # Set in context for all operations in this request
        with RequestContext(request_id=request_id):
            await self.app(scope, receive, send_with_request_id)
