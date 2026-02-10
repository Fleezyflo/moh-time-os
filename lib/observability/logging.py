"""
Structured JSON logging with request ID propagation.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from .context import get_request_id


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "logger": "lib.api",
        "message": "Request processed",
        "request_id": "req-abc123",
        "user_id": "123",
        ...
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_obj["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName",
            ):
                log_obj[key] = value

        return json.dumps(log_obj, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        request_id = get_request_id()
        rid_str = f"[{request_id[:12]}] " if request_id else ""
        return f"{timestamp} [{record.levelname}] {record.name}: {rid_str}{record.getMessage()}"


def configure_logging(
    level: str = "INFO",
    json_format: bool | None = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format. If None, auto-detect based on environment.
    """
    if json_format is None:
        # Use JSON in production (when not a TTY), human format in dev
        json_format = not sys.stderr.isatty()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add new handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter() if json_format else HumanFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing", extra={"count": 42})
    """
    return logging.getLogger(name)
