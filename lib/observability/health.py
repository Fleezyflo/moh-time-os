"""
Health check system with component-level checks.
"""

import logging
import shutil
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Python 3.10 compatibility
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from enum import Enum
from pathlib import Path
from typing import Optional

from lib import paths

logger = logging.getLogger(__name__)


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

    def to_prometheus(self) -> str:
        """Export health status in Prometheus format."""
        lines = [
            "# HELP health_check_status Overall health status (1=healthy, 0.5=degraded, 0=unhealthy)",
            "# TYPE health_check_status gauge",
        ]

        status_value = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0.0,
        }.get(self.status, 0.0)

        lines.append(f"health_check_status {status_value}")

        # Add per-check metrics
        lines.append("# HELP health_check_component_status Component health status")
        lines.append("# TYPE health_check_component_status gauge")

        for check in self.checks:
            status_val = {
                HealthStatus.HEALTHY: 1.0,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0.0,
            }.get(check.status, 0.0)
            lines.append(f'health_check_component_status{{component="{check.name}"}} {status_val}')
            lines.append(f'health_check_latency_ms{{component="{check.name}"}} {check.latency_ms}')

        return "\n".join(lines) + "\n"


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
        self.add_check("disk_space", self._check_disk_space)
        self.add_check("collector_health", self._check_collector_health)
        self.add_check("daemon_health", self._check_daemon_health)
        self.add_check("bundle_health", self._check_bundle_health)

    def add_check(self, name: str, check_fn: Callable[[], HealthCheckResult]) -> None:
        """Register a health check function."""
        self._checks[name] = check_fn

    def run_all(self) -> HealthReport:
        """Run all health checks and return aggregated report."""
        results = []
        overall_status = HealthStatus.HEALTHY

        for name, check_fn in self._checks.items():
            start = time.monotonic()
            try:
                result = check_fn()
            except Exception as e:
                logger.error(f"Health check '{name}' failed with exception", exc_info=e)
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
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
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
            logger.error("Database health check failed", exc_info=e)
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
                logger.warning(
                    f"Schema version mismatch: {version} != {expected}",
                )
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
            logger.error("Schema version check failed", exc_info=e)
            return HealthCheckResult(
                name="schema_version",
                status=HealthStatus.UNHEALTHY,
                message=f"Schema check error: {e}",
                latency_ms=0,
            )

    def _check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage of data directory."""
        try:
            data_dir = paths.app_home()

            # Get disk usage
            total, used, free = shutil.disk_usage(str(data_dir))
            percent_used = (used / total) * 100 if total > 0 else 0

            details = {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "percent_used": round(percent_used, 2),
            }

            if percent_used > 95:
                logger.error(f"Disk space critical: {percent_used:.1f}% used")
                return HealthCheckResult(
                    name="disk_space",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Disk space critical: {percent_used:.1f}% used",
                    latency_ms=0,
                    details=details,
                )
            elif percent_used > 90:
                logger.warning(f"Disk space degraded: {percent_used:.1f}% used")
                return HealthCheckResult(
                    name="disk_space",
                    status=HealthStatus.DEGRADED,
                    message=f"Disk space degraded: {percent_used:.1f}% used",
                    latency_ms=0,
                    details=details,
                )

            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.HEALTHY,
                message=f"Disk space OK: {percent_used:.1f}% used",
                latency_ms=0,
                details=details,
            )
        except Exception as e:
            logger.error("Disk space check failed", exc_info=e)
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.DEGRADED,
                message=f"Disk space check error: {e}",
                latency_ms=0,
            )

    def _check_collector_health(self) -> HealthCheckResult:
        """Check if collectors ran recently (last sync < 2x interval)."""
        try:
            db_path = paths.db_path()
            conn = sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.cursor()

            # Check if there's a recent collector state
            # Look for collector_sync_log or similar recent activity
            cursor.execute(
                """
                SELECT MAX(created_at) FROM events
                WHERE event_type LIKE 'collector_%'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            result = cursor.fetchone()
            conn.close()

            if not result or not result[0]:
                logger.warning("No recent collector activity found")
                return HealthCheckResult(
                    name="collector_health",
                    status=HealthStatus.DEGRADED,
                    message="No recent collector activity",
                    latency_ms=0,
                    details={"last_run": None},
                )

            try:
                last_run = datetime.fromisoformat(
                    result[0].replace("Z", "+00:00")
                    if isinstance(result[0], str)
                    else str(result[0])
                )
                now = datetime.now(UTC)
                age_seconds = (now - last_run).total_seconds()

                # Default expected sync interval is around 5 minutes (300s)
                # Allow 2x that = 600 seconds
                max_age = 600

                if age_seconds > max_age:
                    logger.warning(
                        f"Collector health degraded: last run {age_seconds}s ago (max {max_age}s)"
                    )
                    return HealthCheckResult(
                        name="collector_health",
                        status=HealthStatus.DEGRADED,
                        message=f"Last collector run {int(age_seconds)}s ago (threshold {max_age}s)",
                        latency_ms=0,
                        details={"last_run": result[0], "age_seconds": int(age_seconds)},
                    )

                return HealthCheckResult(
                    name="collector_health",
                    status=HealthStatus.HEALTHY,
                    message=f"Collectors running normally (last run {int(age_seconds)}s ago)",
                    latency_ms=0,
                    details={"last_run": result[0], "age_seconds": int(age_seconds)},
                )
            except Exception as e:
                logger.error(f"Error parsing collector timestamp: {e}")
                return HealthCheckResult(
                    name="collector_health",
                    status=HealthStatus.DEGRADED,
                    message=f"Error parsing collector timestamp: {e}",
                    latency_ms=0,
                )
        except Exception as e:
            logger.error("Collector health check failed", exc_info=e)
            return HealthCheckResult(
                name="collector_health",
                status=HealthStatus.DEGRADED,
                message=f"Collector check error: {e}",
                latency_ms=0,
            )

    def _check_daemon_health(self) -> HealthCheckResult:
        """Check if daemon is responsive (state file fresh)."""
        try:
            # Try to get daemon state from store
            from lib.state_store import get_store

            try:
                store = get_store()
                state = store.get("daemon_heartbeat")

                if state:
                    try:
                        heartbeat_time = datetime.fromisoformat(
                            state.replace("Z", "+00:00") if isinstance(state, str) else str(state)
                        )
                        now = datetime.now(UTC)
                        age_seconds = (now - heartbeat_time).total_seconds()

                        # Allow up to 30 seconds for heartbeat
                        max_age = 30

                        if age_seconds > max_age:
                            logger.warning(f"Daemon health degraded: heartbeat {age_seconds}s old")
                            return HealthCheckResult(
                                name="daemon_health",
                                status=HealthStatus.DEGRADED,
                                message=f"Daemon heartbeat {int(age_seconds)}s old (threshold {max_age}s)",
                                latency_ms=0,
                                details={"last_heartbeat": state, "age_seconds": int(age_seconds)},
                            )

                        return HealthCheckResult(
                            name="daemon_health",
                            status=HealthStatus.HEALTHY,
                            message=f"Daemon responsive (heartbeat {int(age_seconds)}s old)",
                            latency_ms=0,
                            details={"last_heartbeat": state, "age_seconds": int(age_seconds)},
                        )
                    except Exception as e:
                        logger.error(f"Error parsing daemon heartbeat: {e}")
                        return HealthCheckResult(
                            name="daemon_health",
                            status=HealthStatus.DEGRADED,
                            message=f"Error parsing daemon heartbeat: {e}",
                            latency_ms=0,
                        )

                # No heartbeat found - assume daemon is ok but no heartbeat yet
                return HealthCheckResult(
                    name="daemon_health",
                    status=HealthStatus.HEALTHY,
                    message="Daemon state available",
                    latency_ms=0,
                    details={"last_heartbeat": None},
                )
            except Exception as e:
                logger.warning(f"Could not access daemon state: {e}")
                # Degraded but not unhealthy - state store may not be initialized
                return HealthCheckResult(
                    name="daemon_health",
                    status=HealthStatus.DEGRADED,
                    message=f"Could not check daemon state: {e}",
                    latency_ms=0,
                )
        except Exception as e:
            logger.error("Daemon health check failed", exc_info=e)
            return HealthCheckResult(
                name="daemon_health",
                status=HealthStatus.DEGRADED,
                message=f"Daemon check error: {e}",
                latency_ms=0,
            )

    def _check_bundle_health(self) -> HealthCheckResult:
        """Check if any bundles are stuck in PENDING > 1 hour."""
        try:
            from lib.change_bundles import BundleStatus, list_bundles

            try:
                pending_bundles = list_bundles(status=BundleStatus.PENDING.value)
                now = datetime.now(UTC)
                stuck_bundles = []

                for bundle in pending_bundles:
                    created_str = bundle.get("created_at")
                    if created_str:
                        try:
                            created = datetime.fromisoformat(
                                created_str.replace("Z", "+00:00")
                                if isinstance(created_str, str)
                                else str(created_str)
                            )
                            age = now - created
                            if age > timedelta(hours=1):
                                stuck_bundles.append(
                                    {
                                        "id": bundle.get("id"),
                                        "age_hours": round(age.total_seconds() / 3600, 2),
                                    }
                                )
                        except Exception:
                            pass

                details = {
                    "pending_count": len(pending_bundles),
                    "stuck_count": len(stuck_bundles),
                }

                if stuck_bundles:
                    logger.warning(f"{len(stuck_bundles)} bundles stuck in PENDING > 1 hour")
                    details["stuck_bundles"] = stuck_bundles
                    return HealthCheckResult(
                        name="bundle_health",
                        status=HealthStatus.DEGRADED,
                        message=f"{len(stuck_bundles)} bundle(s) stuck in PENDING > 1 hour",
                        latency_ms=0,
                        details=details,
                    )

                return HealthCheckResult(
                    name="bundle_health",
                    status=HealthStatus.HEALTHY,
                    message=f"No stuck bundles ({len(pending_bundles)} pending)",
                    latency_ms=0,
                    details=details,
                )
            except Exception as e:
                logger.error(f"Error checking bundle health: {e}")
                return HealthCheckResult(
                    name="bundle_health",
                    status=HealthStatus.DEGRADED,
                    message=f"Bundle health check error: {e}",
                    latency_ms=0,
                )
        except Exception as e:
            logger.error("Bundle health check failed", exc_info=e)
            return HealthCheckResult(
                name="bundle_health",
                status=HealthStatus.DEGRADED,
                message=f"Bundle check error: {e}",
                latency_ms=0,
            )
