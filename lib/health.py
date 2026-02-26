"""Health checks and self-healing for MOH Time OS."""

import logging
import os
import sqlite3
from datetime import datetime
from enum import Enum
from typing import Any

from .store import (
    DB_PATH,
    checkpoint_wal,
    db_exists,
    get_connection,
    init_db,
    integrity_check,
)

log = logging.getLogger("moh_time_os")

BACKUP_DIR = DB_PATH.parent / "backups"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


def health_check() -> tuple[HealthStatus, dict[str, Any]]:
    """
    Run all health checks.
    Returns (status, details) where details contains check results.
    """
    checks = {}

    # 1. Database exists
    checks["db_exists"] = db_exists()

    if not checks["db_exists"]:
        return HealthStatus.FAILED, {
            "checks": checks,
            "message": "Database does not exist",
            "action": "Run init_db() or restore from backup",
        }

    # 2. Database readable
    try:
        from .store import table_counts

        counts = table_counts()
        checks["db_readable"] = True
        checks["table_counts"] = counts
    except (sqlite3.Error, ValueError, OSError) as e:
        checks["db_readable"] = False
        checks["db_read_error"] = str(e)
        return HealthStatus.FAILED, {
            "checks": checks,
            "message": f"Database not readable: {e}",
            "action": "Check file permissions or restore from backup",
        }

    # 3. Database writable
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        checks["db_writable"] = True
    except (sqlite3.Error, ValueError, OSError) as e:
        checks["db_writable"] = False
        checks["db_write_error"] = str(e)
        return HealthStatus.DEGRADED, {
            "checks": checks,
            "message": f"Database not writable: {e}",
            "action": "Check disk space and permissions",
        }

    # 4. Integrity check
    ok, result = integrity_check()
    checks["integrity_ok"] = ok
    checks["integrity_result"] = result

    if not ok:
        return HealthStatus.DEGRADED, {
            "checks": checks,
            "message": f"Integrity check failed: {result}",
            "action": "Consider restoring from backup",
        }

    # 5. Backup recency
    checks["backup_recent"] = False
    checks["last_backup"] = None

    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if backups:
            last_backup_time = datetime.fromtimestamp(backups[0].stat().st_mtime)
            checks["last_backup"] = last_backup_time.isoformat()
            checks["backup_age_hours"] = (datetime.now() - last_backup_time).total_seconds() / 3600
            checks["backup_recent"] = checks["backup_age_hours"] < 48

    if not checks["backup_recent"]:
        return HealthStatus.DEGRADED, {
            "checks": checks,
            "message": "No recent backup (>48h)",
            "action": "Run backup",
        }

    # 6. Disk space
    try:
        stat = os.statvfs(DB_PATH.parent)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        checks["disk_free_mb"] = round(free_mb, 1)
        checks["disk_ok"] = free_mb > 100

        if not checks["disk_ok"]:
            return HealthStatus.DEGRADED, {
                "checks": checks,
                "message": f"Low disk space: {free_mb:.0f}MB",
                "action": "Free up disk space",
            }
    except (sqlite3.Error, ValueError, OSError) as e:
        checks["disk_check_error"] = str(e)

    # All good
    return HealthStatus.HEALTHY, {"checks": checks, "message": "All checks passed"}


def self_heal() -> list[str]:
    """
    Run self-healing procedures on startup.
    Returns list of actions taken.
    """
    actions = []

    # Ensure directories exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize DB if missing
    if not db_exists():
        init_db()
        actions.append("Initialized new database")
        return actions

    # Ensure WAL mode
    try:
        with get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if mode.lower() != "wal":
                conn.execute("PRAGMA journal_mode=WAL")
                actions.append("Enabled WAL mode")
    except (sqlite3.Error, ValueError, OSError) as e:
        log.error(f"Failed to check/set WAL mode: {e}")

    # Checkpoint WAL to prevent bloat
    try:
        checkpoint_wal()
        actions.append("Checkpointed WAL")
    except (sqlite3.Error, ValueError, OSError) as e:
        log.error(f"Failed to checkpoint WAL: {e}")

    # Ensure foreign keys enabled
    try:
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
    except (sqlite3.Error, ValueError, OSError) as e:
        log.error(f"Failed to enable foreign keys: {e}")

    # Prune old backups (keep 7)
    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_backup in backups[7:]:
            try:
                old_backup.unlink()
                actions.append(f"Pruned old backup: {old_backup.name}")
            except (sqlite3.Error, ValueError, OSError) as e:
                log.error(f"Failed to prune backup {old_backup}: {e}")

    return actions


def startup_check() -> tuple[HealthStatus, str]:
    """
    Run on session start. Returns (status, message).
    Runs self-healing first, then health check.
    """
    # Self-heal first
    heal_actions = self_heal()

    # Then check health
    status, details = health_check()

    if status == HealthStatus.HEALTHY:
        counts = details["checks"].get("table_counts", {})
        msg = f"MOH Time OS: Healthy ({counts.get('items', 0)} items, {counts.get('clients', 0)} clients)"
        if heal_actions:
            msg += f" [healed: {len(heal_actions)} actions]"
        return status, msg

    if status == HealthStatus.DEGRADED:
        return status, f"⚠️ MOH Time OS: Degraded — {details['message']}"

    # FAILED
    return (
        status,
        f"🔴 MOH Time OS: Failed — {details['message']}. {details.get('action', '')}",
    )


def status_report() -> str:
    """Generate a full status report."""
    status, details = health_check()

    lines = [f"## MOH Time OS Status: {status.value.upper()}\n"]

    checks = details.get("checks", {})

    # Database
    lines.append("### Database")
    lines.append(f"- Exists: {'✅' if checks.get('db_exists') else '❌'}")
    lines.append(f"- Readable: {'✅' if checks.get('db_readable') else '❌'}")
    lines.append(f"- Writable: {'✅' if checks.get('db_writable') else '❌'}")
    lines.append(f"- Integrity: {'✅' if checks.get('integrity_ok') else '❌'}")
    lines.append("")

    # Counts
    counts = checks.get("table_counts", {})
    if counts:
        lines.append("### Data")
        lines.append(f"- Clients: {counts.get('clients', 0)}")
        lines.append(f"- People: {counts.get('people', 0)}")
        lines.append(f"- Projects: {counts.get('projects', 0)}")
        lines.append(f"- Items: {counts.get('items', 0)}")
        lines.append("")

    # Backup
    lines.append("### Backup")
    lines.append(f"- Recent (<48h): {'✅' if checks.get('backup_recent') else '❌'}")
    if checks.get("last_backup"):
        lines.append(f"- Last backup: {checks['last_backup']}")
        lines.append(f"- Age: {checks.get('backup_age_hours', 0):.1f} hours")
    lines.append("")

    # Disk
    if "disk_free_mb" in checks:
        lines.append("### Disk")
        lines.append(f"- Free space: {checks['disk_free_mb']} MB")
        lines.append(f"- Status: {'✅' if checks.get('disk_ok') else '⚠️ Low'}")
        lines.append("")

    # Message
    if details.get("message"):
        lines.append(f"**Status:** {details['message']}")
    if details.get("action"):
        lines.append(f"**Action:** {details['action']}")

    return "\n".join(lines)
