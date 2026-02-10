"""
Request context management with thread-local storage.
"""

import contextvars
import uuid
from typing import Optional

# Thread-safe context variable for request ID
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token:
    """Set the request ID in context. Returns token for reset."""
    return _request_id_var.set(request_id)


def generate_request_id() -> str:
    """Generate a new request ID."""
    return f"req-{uuid.uuid4().hex[:16]}"


class RequestContext:
    """
    Context manager for request-scoped operations.

    Usage:
        with RequestContext() as ctx:
            logger.info("Processing", extra={"request_id": ctx.request_id})
            # All logs within this block will include the request ID

        # Or with an existing ID:
        with RequestContext(request_id="req-abc123"):
            ...
    """

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or generate_request_id()
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> "RequestContext":
        self._token = set_request_id(self.request_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            _request_id_var.reset(self._token)
