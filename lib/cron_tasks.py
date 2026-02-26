"""
Cron task handlers for MOH Time OS.

These are called by Clawdbot cron jobs:
- daily_sync: Sync from Xero/Asana (06:00)
- daily_backup: Create backup (03:00)
- health_check: Run health check (every 6h)
"""

import logging
import sqlite3

from .backup import create_backup, prune_backups
from .classify import run_auto_classification
from .health import health_check, self_heal
from .maintenance import fix_item_priorities
from .store import get_connection
from .sync_asana import sync_asana_projects
from .sync_xero import sync_xero_clients

logger = logging.getLogger(__name__)


log = logging.getLogger("moh_time_os.cron")


def cron_daily_sync() -> dict:
    """
    Run daily data sync.

    Called at 06:00 Dubai time.
    Syncs Xero clients and Asana projects.
    """
    log.info("Starting daily sync")
    results = {}

    # Xero sync
    try:
        created, updated, skipped, errors = sync_xero_clients()
        results["xero"] = {
            "created": created,
            "updated": updated,
            "errors": len(errors),
        }
        log.info(f"Xero sync: {created} created, {updated} updated")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["xero"] = {"error": str(e)}
        log.error(f"Xero sync failed: {e}")

    # Asana sync
    try:
        created, updated, matched, skipped, errors = sync_asana_projects()
        results["asana"] = {
            "created": created,
            "updated": updated,
            "matched": matched,
            "errors": len(errors),
        }
        log.info(f"Asana sync: {created} created, {updated} updated")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["asana"] = {"error": str(e)}
        log.error(f"Asana sync failed: {e}")

    # Recalculate priorities
    try:
        count = fix_item_priorities()
        results["priorities_updated"] = count
    except (sqlite3.Error, ValueError, OSError) as e:
        results["priorities_error"] = str(e)

    # Run auto-classification
    try:
        class_results = run_auto_classification()
        results["classification"] = class_results["tiers"]
    except (sqlite3.Error, ValueError, OSError) as e:
        results["classification_error"] = str(e)

    log.info("Daily sync complete")
    return results


def cron_daily_backup() -> dict:
    """
    Run daily backup.

    Called at 03:00 Dubai time.
    """
    log.info("Starting daily backup")
    results = {}

    # Self-heal first
    heal_actions = self_heal()
    results["self_heal"] = heal_actions

    # Create backup
    success, path = create_backup(tag="daily")
    results["backup"] = {
        "success": success,
        "path": path if success else None,
        "error": None if success else path,
    }

    if success:
        log.info(f"Backup created: {path}")
    else:
        log.error(f"Backup failed: {path}")

    # Prune old backups
    deleted = prune_backups(keep=7)
    results["pruned"] = deleted

    log.info("Daily backup complete")
    return results


def cron_health_check() -> dict:
    """
    Run periodic health check.

    Called every 6 hours.
    Returns health status.
    """
    log.info("Running health check")

    report = health_check()

    result = {
        "status": report.overall,
        "checks": {c.name: c.status for c in report.checks},
        "timestamp": report.timestamp,
    }

    # Self-heal if issues detected
    if report.overall != "HEALTHY":
        heal_actions = self_heal()
        result["heal_actions"] = heal_actions

        # Re-check
        report2 = health_check()
        result["status_after_heal"] = report2.overall

    log.info(f"Health check: {result['status']}")
    return result


def cron_retention_enforcement() -> dict:
    """
    Run daily retention enforcement.

    Called at 04:00 Dubai time.
    Deletes rows older than configured retention policies.
    """
    log.info("Starting retention enforcement")

    try:
        from .data_lifecycle import DataLifecycleManager

        manager = DataLifecycleManager()
        results = manager.enforce_retention(dry_run=False)

        # Format results
        summary = {
            "tables_processed": len(results),
            "total_rows_deleted": sum(r["rows_deleted"] for r in results),
            "total_rows_archived": sum(r["rows_archived"] for r in results),
            "space_freed_kb": sum(r["estimated_space_freed_kb"] for r in results),
            "timestamp": results[0]["timestamp"] if results else None,
        }

        for result in results:
            if result["rows_deleted"] > 0:
                log.info(f"Deleted {result['rows_deleted']} rows from {result['table']}")
            if result["rows_archived"] > 0:
                log.info(f"Archived {result['rows_archived']} rows from {result['table']}")

        log.info("Retention enforcement complete")
        return summary

    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise  # re-raise after logging


def cron_weekly_archive() -> dict:
    """
    Run weekly data archival.

    Called weekly at 02:00 Dubai time.
    Archives old data from archival tables to cold storage.
    """
    log.info("Starting weekly archive")

    try:
        from datetime import date, timedelta

        from .data_lifecycle import DataLifecycleManager

        manager = DataLifecycleManager()

        # Archive communications, messages, etc. older than retention period
        archival_results = []
        archive_targets = {
            "communications": 180,
            "gmail_messages": 180,
            "chat_messages": 180,
        }

        for table, retention_days in archive_targets.items():
            # Check if table exists
            with get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name = ?
                """,
                    (table,),
                )
                if not cursor.fetchone():
                    log.debug(f"Table {table} does not exist, skipping")
                    continue

            try:
                cutoff = date.today() - timedelta(days=retention_days)
                result = manager.archive_to_cold(table, cutoff, dry_run=False)
                archival_results.append(result)
            except ValueError as e:
                # Table might not have timestamp column or be protected
                log.debug(f"Cannot archive {table}: {e}")
            except (sqlite3.Error, OSError) as e:
                log.error(f"Failed to archive {table}: {e}", exc_info=True)

        summary = {
            "tables_archived": len(archival_results),
            "total_archived": sum(r["rows_archived"] for r in archival_results),
            "space_freed_kb": sum(r["estimated_space_freed_kb"] for r in archival_results),
        }

        log.info("Weekly archive complete")
        return summary

    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise  # re-raise after logging


def get_cron_config() -> dict:
    """
    Get cron job configuration for Clawdbot.

    These can be added via the cron tool.
    """
    return {
        "daily_sync": {
            "schedule": "0 6 * * *",  # 06:00 daily
            "timezone": "Asia/Dubai",
            "task": "Sync Xero and Asana data",
            "handler": "cron_daily_sync",
        },
        "daily_backup": {
            "schedule": "0 3 * * *",  # 03:00 daily
            "timezone": "Asia/Dubai",
            "task": "Backup database and prune old backups",
            "handler": "cron_daily_backup",
        },
        "health_check": {
            "schedule": "0 */6 * * *",  # Every 6 hours
            "timezone": "Asia/Dubai",
            "task": "Run health check and self-heal",
            "handler": "cron_health_check",
        },
        "retention_enforcement": {
            "schedule": "0 4 * * *",  # 04:00 daily
            "timezone": "Asia/Dubai",
            "task": "Enforce data retention policies",
            "handler": "cron_retention_enforcement",
        },
        "weekly_archive": {
            "schedule": "0 2 * * 0",  # 02:00 on Sunday
            "timezone": "Asia/Dubai",
            "task": "Archive old data to cold storage",
            "handler": "cron_weekly_archive",
        },
    }


def format_sync_report(results: dict) -> str:
    """Format sync results for notification."""
    lines = ["**Daily Sync Complete**", ""]

    if "xero" in results:
        x = results["xero"]
        if "error" in x:
            lines.append(f"❌ Xero: {x['error']}")
        else:
            lines.append(f"✅ Xero: {x['created']} new, {x['updated']} updated")

    if "asana" in results:
        a = results["asana"]
        if "error" in a:
            lines.append(f"❌ Asana: {a['error']}")
        else:
            lines.append(
                f"✅ Asana: {a['created']} new, {a['updated']} updated, {a['matched']} linked"
            )

    if "classification" in results:
        c = results["classification"]
        if c.get("applied", 0) > 0:
            lines.append(f"🏷️ Classified {c['applied']} clients")

    return "\n".join(lines)


if __name__ == "__main__":
    logger.info("=== Cron Configuration ===\n")
    config = get_cron_config()
    for name, cfg in config.items():
        logger.info(f"{name}:")
        logger.info(f"  Schedule: {cfg['schedule']}")
        logger.info(f"  Task: {cfg['task']}")
        # (newline for readability)
