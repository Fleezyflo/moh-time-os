"""
Health check system with component-level checks.
"""

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from lib import paths


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str
    latency_ms: float
    details: dict = field(default_factory=dict)


@dataclass
class HealthReport:
    status: HealthStatus
    checks: list[HealthCheckResult]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    **c.details,
                }
                for c in self.checks
            ],
        }


class HealthChecker:
    """
    Health check orchestrator.

    Usage:
        checker = HealthChecker()
        checker.add_check("db", check_db)
        checker.add_check("collectors", check_collectors)
        report = checker.run_all()
    """

    def __init__(self):
        self._checks: dict[str, Callable[[], HealthCheckResult]] = {}
        # Add default checks
        self.add_check("db", self._check_db)
        self.add_check("schema_version", self._check_schema_version)

    def add_check(self, name: str, check_fn: Callable[[], HealthCheckResult]) -> None:
        """Register a health check function."""
        self._checks[name] = check_fn

    def run_all(self) -> HealthReport:
        """Run all health checks and return aggregated report."""
        from datetime import UTC, datetime

        results = []
        overall_status = HealthStatus.HEALTHY

        for name, check_fn in self._checks.items():
            start = time.monotonic()
            try:
                result = check_fn()
            except Exception as e:
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}",
                    latency_ms=(time.monotonic() - start) * 1000,
                )

            result.latency_ms = (time.monotonic() - start) * 1000
            results.append(result)

            # Aggregate status (worst wins)
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                result.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        return HealthReport(
            status=overall_status,
            checks=results,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        )

    def _check_db(self) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            db_path = paths.db_path()
            conn = sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return HealthCheckResult(
                name="db",
                status=HealthStatus.HEALTHY,
                message="Database connection OK",
                latency_ms=0,
                details={"path": str(db_path)},
            )
        except Exception as e:
            return HealthCheckResult(
                name="db",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {e}",
                latency_ms=0,
            )

    def _check_schema_version(self) -> HealthCheckResult:
        """Check database schema version."""
        try:
            from lib import db as db_module

            db_path = paths.db_path()
            conn = sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version")
            version = cursor.fetchone()[0]
            conn.close()

            expected = getattr(db_module, "SCHEMA_VERSION", None)
            if expected and version != expected:
                return HealthCheckResult(
                    name="schema_version",
                    status=HealthStatus.DEGRADED,
                    message=f"Schema version mismatch: {version} != {expected}",
                    latency_ms=0,
                    details={"current": version, "expected": expected},
                )

            return HealthCheckResult(
                name="schema_version",
                status=HealthStatus.HEALTHY,
                message=f"Schema version: {version}",
                latency_ms=0,
                details={"version": version},
            )
        except Exception as e:
            return HealthCheckResult(
                name="schema_version",
                status=HealthStatus.UNHEALTHY,
                message=f"Schema check error: {e}",
                latency_ms=0,
            )
