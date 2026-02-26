"""
Signal Lifecycle Migration (v32)

Extends signal_state table with lifecycle tracking columns:
- first_detected_at: when the signal was first seen
- detection_count: how many cycles it has fired
- consecutive_cycles: unbroken streak of detections
- initial_severity: severity at first detection
- peak_severity: highest severity reached
- escalation_history_json: JSON array of severity changes
- resolved_at: when the signal cleared
- resolution_type: how it was resolved

Also backfills existing rows: first_detected_at = detected_at,
initial_severity = severity, peak_severity = severity.

Run: python -m lib.migrations.v32_signal_lifecycle
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from lib import paths

logger = logging.getLogger(__name__)

# Columns to add with their defaults
NEW_COLUMNS = [
    ("first_detected_at", "TEXT", None),
    ("detection_count", "INTEGER", "1"),
    ("consecutive_cycles", "INTEGER", "1"),
    ("initial_severity", "TEXT", None),
    ("peak_severity", "TEXT", None),
    ("escalation_history_json", "TEXT", "'[]'"),
    ("resolved_at", "TEXT", None),
    ("resolution_type", "TEXT", None),
]


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate(db_path: Path | None = None) -> dict:
    """
    Run the v32 migration.

    Returns dict with migration results.
    """
    db = db_path or paths.db_path()
    conn = sqlite3.connect(str(db))
    results = {"added_columns": [], "backfilled": 0, "skipped_columns": []}

    try:
        # Check signal_state exists
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        if "signal_state" not in tables:
            logger.warning("signal_state table does not exist, creating it")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_state (
                    signal_key TEXT PRIMARY KEY,
                    signal_type TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    severity TEXT,
                    detected_at TEXT,
                    value REAL,
                    threshold REAL,
                    evidence_json TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    acknowledged_at TEXT
                )
                """
            )
            conn.commit()

        # Add new columns if they don't exist
        for col_name, col_type, default in NEW_COLUMNS:
            if _column_exists(conn, "signal_state", col_name):
                results["skipped_columns"].append(col_name)
                logger.info("Column %s already exists, skipping", col_name)
                continue

            default_clause = f" DEFAULT {default}" if default else ""
            sql = f"ALTER TABLE signal_state ADD COLUMN {col_name} {col_type}{default_clause}"
            conn.execute(sql)
            results["added_columns"].append(col_name)
            logger.info("Added column: %s %s%s", col_name, col_type, default_clause)

        conn.commit()

        # Backfill: set first_detected_at = detected_at where NULL
        cursor = conn.execute(
            """
            UPDATE signal_state
            SET first_detected_at = detected_at
            WHERE first_detected_at IS NULL AND detected_at IS NOT NULL
            """
        )
        results["backfilled"] += cursor.rowcount

        # Backfill: set initial_severity = severity where NULL
        conn.execute(
            """
            UPDATE signal_state
            SET initial_severity = severity
            WHERE initial_severity IS NULL AND severity IS NOT NULL
            """
        )

        # Backfill: set peak_severity = severity where NULL
        conn.execute(
            """
            UPDATE signal_state
            SET peak_severity = severity
            WHERE peak_severity IS NULL AND severity IS NOT NULL
            """
        )

        conn.commit()
        logger.info("v32 migration complete: %s", results)
        return results

    except (sqlite3.Error, ValueError, OSError) as exc:
        logger.error("v32 migration failed: %s", exc)
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = migrate()
    print(f"Migration v32 complete: {result}")
