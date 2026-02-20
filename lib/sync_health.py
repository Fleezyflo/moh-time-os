"""
Sync schedule health checker.

Reads config/sync_schedule.yaml to determine per-collector intervals,
then checks collector run history to flag stale collectors.

Usage:
    from lib.sync_health import load_schedule, check_collector_health

    schedule = load_schedule()
    report = check_collector_health(db_path)
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

SCHEDULE_PATH = Path(__file__).parent.parent / "config" / "sync_schedule.yaml"


def load_schedule(path: Optional[str] = None) -> dict:
    """
    Load sync schedule from YAML config.

    Returns:
        {
            "schedules": {
                "asana": {"interval_minutes": 30, "enabled": True, "health_multiplier": 2},
                ...
            }
        }

    Raises:
        FileNotFoundError if config file doesn't exist.
        yaml.YAMLError if config is invalid YAML.
    """
    config_path = Path(path) if path else SCHEDULE_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Sync schedule not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data or "schedules" not in data:
        raise ValueError("sync_schedule.yaml must have a 'schedules' key")

    # Validate and apply defaults
    schedules = {}
    for name, config in data["schedules"].items():
        if not isinstance(config, dict):
            logger.warning(f"Skipping invalid schedule entry: {name}")
            continue

        interval = config.get("interval_minutes")
        if not isinstance(interval, (int, float)) or interval <= 0:
            logger.warning(f"Invalid interval for {name}: {interval}")
            continue

        schedules[name] = {
            "interval_minutes": int(interval),
            "enabled": config.get("enabled", True),
            "health_multiplier": config.get("health_multiplier", 2),
        }

    return {"schedules": schedules}


def get_enabled_collectors(path: Optional[str] = None) -> list[str]:
    """Return list of enabled collector names from schedule config."""
    schedule = load_schedule(path)
    return [
        name
        for name, cfg in schedule["schedules"].items()
        if cfg["enabled"]
    ]


def check_collector_health(
    db_path: Optional[str] = None,
    schedule_path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    """
    Check health of all enabled collectors.

    Compares last run time from cycle_logs against expected interval.
    A collector is "stale" if it hasn't run within health_multiplier * interval.

    Args:
        db_path: Path to SQLite database. Uses default if None.
        schedule_path: Path to sync_schedule.yaml. Uses default if None.
        now: Current time (for testing). Uses UTC now if None.

    Returns:
        {
            "healthy": [...],
            "stale": [{"name": ..., "last_run": ..., "expected_interval_minutes": ..., "stale_minutes": ...}],
            "never_run": [...],
            "disabled": [...],
            "checked_at": ISO timestamp,
        }
    """
    schedule = load_schedule(schedule_path)
    now = now or datetime.now(timezone.utc)

    # Get last run times from cycle_logs or state_tracker
    last_runs = _get_last_run_times(db_path)

    healthy = []
    stale = []
    never_run = []
    disabled = []

    for name, cfg in schedule["schedules"].items():
        if not cfg["enabled"]:
            disabled.append(name)
            continue

        last_run = last_runs.get(name)
        if last_run is None:
            never_run.append(name)
            continue

        max_age = timedelta(minutes=cfg["interval_minutes"] * cfg["health_multiplier"])
        age = now - last_run

        if age > max_age:
            stale.append({
                "name": name,
                "last_run": last_run.isoformat(),
                "expected_interval_minutes": cfg["interval_minutes"],
                "stale_minutes": int(age.total_seconds() / 60),
            })
        else:
            healthy.append(name)

    return {
        "healthy": healthy,
        "stale": stale,
        "never_run": never_run,
        "disabled": disabled,
        "checked_at": now.isoformat(),
    }


def _get_last_run_times(db_path: Optional[str] = None) -> dict[str, datetime]:
    """
    Get last successful run time for each collector from the database.

    Checks cycle_logs table first, falls back to state_tracker.
    """
    if db_path is None:
        db_path = str(Path(__file__).parent.parent / "data" / "moh_time_os.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    last_runs: dict[str, datetime] = {}

    # Try cycle_logs table (has collector run history)
    try:
        rows = conn.execute("""
            SELECT source, MAX(completed_at) as last_run
            FROM cycle_logs
            WHERE status = 'success'
            GROUP BY source
        """).fetchall()
        for row in rows:
            try:
                ts = datetime.fromisoformat(row["last_run"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                last_runs[row["source"]] = ts
            except (ValueError, TypeError):
                pass
    except sqlite3.OperationalError:
        # Table might not exist
        pass

    # Fallback: state_tracker table
    if not last_runs:
        try:
            rows = conn.execute("""
                SELECT source, MAX(collected_at) as last_run
                FROM state_tracker
                GROUP BY source
            """).fetchall()
            for row in rows:
                try:
                    ts = datetime.fromisoformat(row["last_run"])
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    last_runs[row["source"]] = ts
                except (ValueError, TypeError):
                    pass
        except sqlite3.OperationalError:
            pass

    conn.close()
    return last_runs


def format_health_report(report: dict) -> str:
    """Format health check report for logging/display."""
    lines = ["=== Sync Health Report ==="]
    lines.append(f"Checked at: {report['checked_at']}")
    lines.append("")

    if report["healthy"]:
        lines.append(f"✅ Healthy ({len(report['healthy'])}): {', '.join(report['healthy'])}")

    if report["stale"]:
        lines.append(f"⚠️  Stale ({len(report['stale'])}):")
        for s in report["stale"]:
            lines.append(
                f"   {s['name']}: last run {s['stale_minutes']}m ago "
                f"(expected every {s['expected_interval_minutes']}m)"
            )

    if report["never_run"]:
        lines.append(f"❌ Never run ({len(report['never_run'])}): {', '.join(report['never_run'])}")

    if report["disabled"]:
        lines.append(f"⏸️  Disabled ({len(report['disabled'])}): {', '.join(report['disabled'])}")

    return "\n".join(lines)


if __name__ == "__main__":
    schedule = load_schedule()
    print("Loaded schedule:")
    for name, cfg in schedule["schedules"].items():
        status = "enabled" if cfg["enabled"] else "disabled"
        print(f"  {name}: every {cfg['interval_minutes']}m ({status})")

    print()
    report = check_collector_health()
    print(format_health_report(report))
