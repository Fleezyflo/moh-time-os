"""
Observability module: structured logging, request IDs, health checks.

Usage:
    from lib.observability import get_logger, RequestContext, HealthChecker

    logger = get_logger(__name__)
    logger.info("Processing request", extra={"user_id": "123"})

    with RequestContext() as ctx:
        logger.info("Request started", extra={"request_id": ctx.request_id})

    health = HealthChecker()
    health.add_check("db", check_db_connection)
    result = health.run_all()
"""

from .logging import get_logger, configure_logging, JSONFormatter
from .context import RequestContext, get_request_id, set_request_id
from .health import HealthChecker, HealthStatus

__all__ = [
    "get_logger",
    "configure_logging",
    "JSONFormatter",
    "RequestContext",
    "get_request_id",
    "set_request_id",
    "HealthChecker",
    "HealthStatus",
]
