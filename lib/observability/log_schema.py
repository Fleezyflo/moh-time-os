"""
Log schema enforcement.

Defines required fields for structured logs and validates log entries.
Ensures consistent, parseable log output across the application.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Log schema version - increment when adding required fields
LOG_SCHEMA_VERSION = "1.0"


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """
    Structured log entry with required fields.

    Required fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level
    - message: Human-readable message
    - logger: Logger name/module
    - request_id: Request correlation ID (if in request context)

    Optional fields:
    - trace_id: Distributed trace ID
    - span_id: Current span ID
    - user_id: Authenticated user
    - client_id: Client context
    - duration_ms: Operation duration
    - error: Error details
    - extra: Additional context
    """

    timestamp: str
    level: LogLevel
    message: str
    logger: str
    request_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    user_id: str | None = None
    client_id: str | None = None
    duration_ms: float | None = None
    error: dict | None = None
    extra: dict | None = None

    @classmethod
    def create(
        cls,
        level: LogLevel,
        message: str,
        logger: str,
        **kwargs,
    ) -> "LogEntry":
        """Create a log entry with current timestamp."""
        return cls(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level,
            message=message,
            logger=logger,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level.value,
            "message": self.message,
            "logger": self.logger,
            "schema_version": LOG_SCHEMA_VERSION,
        }

        # Add optional fields only if present
        if self.request_id:
            result["request_id"] = self.request_id
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.span_id:
            result["span_id"] = self.span_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.client_id:
            result["client_id"] = self.client_id
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.error:
            result["error"] = self.error
        if self.extra:
            result["extra"] = self.extra

        return result


def validate_log_entry(entry: dict) -> list[str]:
    """
    Validate a log entry against the schema.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Required fields
    required = ["timestamp", "level", "message", "logger"]
    for field in required:
        if field not in entry:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "level" in entry and entry["level"] not in [l.value for l in LogLevel]:
        errors.append(f"Invalid log level: {entry['level']}")

    if "timestamp" in entry:
        try:
            # Validate ISO 8601 format
            datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"Invalid timestamp format: {entry['timestamp']}")

    return errors
