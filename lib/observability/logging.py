"""
Structured JSON logging with request ID propagation.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# UTC compatibility for Python 3.10/3.11
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc  # noqa: UP017

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
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "message",
                "taskName",
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


class CorrelationIdMiddleware:
    """
    FastAPI middleware for adding request ID to logs.

    Usage in server.py:
        from lib.observability.logging import CorrelationIdMiddleware
        app.add_middleware(CorrelationIdMiddleware)

    All logs within a request will include the request_id in context.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get or generate request ID
        from .context import RequestContext, generate_request_id

        request_id = None

        # Check for X-Request-ID header
        headers = dict(scope.get("headers", []))
        for key, value in headers.items():
            if key.lower() == b"x-request-id":
                try:
                    request_id = value.decode("utf-8")
                except Exception:  # noqa: S110
                    pass
                break

        # Generate if not provided
        if not request_id:
            request_id = generate_request_id()

        # Set in context for all operations in this request
        with RequestContext(request_id=request_id):
            await self.app(scope, receive, send)


def configure_request_logging(app) -> None:
    """
    Configure request logging with correlation ID middleware.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(CorrelationIdMiddleware)


def configure_log_rotation(
    log_file: str = None,
    max_bytes: int = 50 * 1024 * 1024,  # 50 MB
    backup_count: int = 5,
) -> None:
    """
    Configure rotating file handler for logs.

    Args:
        log_file: Path to log file. If None, logs go to stderr only.
        max_bytes: Max size of log file before rotation (default 50MB)
        backup_count: Number of backup files to keep (default 5)
    """
    from logging.handlers import RotatingFileHandler

    if not log_file:
        return

    # Create log directory if needed
    log_dir = os.path.dirname(os.path.abspath(log_file))
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Could not create log directory {log_dir}: {e}")
            return

    root_logger = logging.getLogger()

    # Add rotating file handler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        formatter = JSONFormatter()
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Could not configure log rotation: {e}")
