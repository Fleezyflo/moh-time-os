"""
Observability module: structured logging, request IDs, health checks, metrics.

Usage:
    from lib.observability import get_logger, RequestContext, HealthChecker

    logger = get_logger(__name__)
    logger.info("Processing request", extra={"user_id": "123"})

    with RequestContext() as ctx:
        logger.info("Request started", extra={"request_id": ctx.request_id})

    health = HealthChecker()
    health.add_check("db", check_db_connection)
    result = health.run_all()

Metrics:
    from lib.observability import REGISTRY, collector_runs, timed

    collector_runs.inc()

    @timed(collector_duration)
    def my_collector():
        ...
"""

from .context import RequestContext, get_request_id, set_request_id
from .health import HealthChecker, HealthStatus
from .log_schema import LOG_SCHEMA_VERSION, LogEntry, LogLevel, validate_log_entry
from .logging import JSONFormatter, configure_logging, get_logger
from .metrics import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    api_errors,
    api_latency,
    api_requests,
    collector_duration,
    collector_errors,
    collector_runs,
    db_latency,
    db_queries,
    timed,
)

__all__ = [
    # Logging
    "get_logger",
    "configure_logging",
    "JSONFormatter",
    # Context
    "RequestContext",
    "get_request_id",
    "set_request_id",
    # Health
    "HealthChecker",
    "HealthStatus",
    # Log schema
    "LOG_SCHEMA_VERSION",
    "LogEntry",
    "LogLevel",
    "validate_log_entry",
    # Metrics
    "REGISTRY",
    "Counter",
    "Gauge",
    "Histogram",
    "timed",
    "collector_runs",
    "collector_errors",
    "collector_duration",
    "api_requests",
    "api_errors",
    "api_latency",
    "db_queries",
    "db_latency",
]
