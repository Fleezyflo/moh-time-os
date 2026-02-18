"""
OpenTelemetry Trace Correlation.

Provides:
- W3C traceparent header parsing/generation
- Span creation around request handling
- Trace ID in logs
- Collector execution spans
"""

import contextvars
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Context variables for trace propagation
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)
_parent_span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "parent_span_id", default=None
)

# ============================================================================
# Trace ID Generation
# ============================================================================


def generate_trace_id() -> str:
    """Generate a 32-character hex trace ID (128-bit)."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate a 16-character hex span ID (64-bit)."""
    return secrets.token_hex(8)


# ============================================================================
# W3C Traceparent
# ============================================================================


def parse_traceparent(header: str | None) -> tuple[str | None, str | None]:
    """
    Parse W3C traceparent header.

    Format: version-trace_id-parent_span_id-flags
    Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01

    Returns: (trace_id, parent_span_id) or (None, None) if invalid
    """
    if not header:
        return None, None

    parts = header.split("-")
    if len(parts) != 4:
        return None, None

    version, trace_id, parent_span_id, _flags = parts

    if version != "00":
        return None, None  # Only version 00 supported

    if len(trace_id) != 32 or len(parent_span_id) != 16:
        return None, None

    return trace_id, parent_span_id


def create_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Create a W3C traceparent header value."""
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


# ============================================================================
# Context Management
# ============================================================================


def get_trace_id() -> str | None:
    """Get current trace ID from context."""
    return _trace_id_var.get()


def get_span_id() -> str | None:
    """Get current span ID from context."""
    return _span_id_var.get()


def set_trace_context(trace_id: str, span_id: str, parent_span_id: str | None = None) -> None:
    """Set trace context for current execution."""
    _trace_id_var.set(trace_id)
    _span_id_var.set(span_id)
    if parent_span_id:
        _parent_span_id_var.set(parent_span_id)


def clear_trace_context() -> None:
    """Clear trace context."""
    _trace_id_var.set(None)
    _span_id_var.set(None)
    _parent_span_id_var.set(None)


# ============================================================================
# Span Recording
# ============================================================================


@dataclass
class Span:
    """Represents a single span in a trace."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time_ns: int
    end_time_ns: int | None = None
    attributes: dict[str, Any] | None = None
    status: str = "OK"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert span to dict for export."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "name": self.name,
            "startTimeUnixNano": self.start_time_ns,
            "endTimeUnixNano": self.end_time_ns,
            "attributes": self.attributes or {},
            "status": {"code": self.status},
            "error": self.error,
        }


# Span buffer for batch export
_span_buffer: list[Span] = []
MAX_BUFFER_SIZE = 1000


def record_span(span: Span) -> None:
    """Record a span to the buffer."""
    global _span_buffer
    _span_buffer.append(span)
    if len(_span_buffer) > MAX_BUFFER_SIZE:
        _span_buffer = _span_buffer[-MAX_BUFFER_SIZE:]


def get_buffered_spans() -> list[Span]:
    """Get all buffered spans."""
    return list(_span_buffer)


def clear_span_buffer() -> None:
    """Clear the span buffer."""
    global _span_buffer
    _span_buffer = []


# ============================================================================
# Context Manager for Spans
# ============================================================================


class SpanContext:
    """
    Context manager for creating spans.

    Usage:
        with SpanContext("request_handler", attributes={"path": "/api/health"}):
            # ... do work
    """

    def __init__(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ):
        self.name = name
        self.attributes = attributes or {}
        self.trace_id = trace_id or get_trace_id() or generate_trace_id()
        self.span_id = generate_span_id()
        self.parent_span_id = get_span_id()
        self.start_time_ns = time.time_ns()
        self.span: Span | None = None

    def __enter__(self) -> "SpanContext":
        set_trace_context(self.trace_id, self.span_id, self.parent_span_id)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        end_time_ns = time.time_ns()
        status = "ERROR" if exc_type else "OK"
        error = str(exc_val) if exc_val else None

        self.span = Span(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            name=self.name,
            start_time_ns=self.start_time_ns,
            end_time_ns=end_time_ns,
            attributes=self.attributes,
            status=status,
            error=error,
        )
        record_span(self.span)

        # Restore parent span context
        if self.parent_span_id:
            _span_id_var.set(self.parent_span_id)


# ============================================================================
# OTLP Export (Stub for dev)
# ============================================================================


def export_spans_otlp(endpoint: str = "http://localhost:4318/v1/traces") -> int:
    """
    Export buffered spans to OTLP endpoint.

    Returns number of spans exported.
    """
    import json
    import urllib.request

    spans = get_buffered_spans()
    if not spans:
        return 0

    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "moh-time-os"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "moh-time-os"},
                        "spans": [s.to_dict() for s in spans],
                    }
                ],
            }
        ]
    }

    try:
        req = urllib.request.Request(  # noqa: S310
            endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):  # noqa: S310
            clear_span_buffer()
            return len(spans)
    except Exception as e:
        logger.debug(f"Failed to flush traces to {endpoint}: {e}")
        return 0
