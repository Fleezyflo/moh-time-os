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
    # S3.6: manual transaction control (isolation_level=None) so the ALTER TABLE
    # ADD COLUMN adds and the backfill commit ATOMICALLY inside one explicit
    # BEGIN/COMMIT. Under sqlite3's default deferred mode, DDL (ALTER) auto-
    # commits before it runs, so a later backfill failure would leave columns
    # added-but-unbackfilled with no way to roll them back. With an explicit
    # BEGIN, the ALTERs participate in the transaction and a backfill failure
    # rolls them back (verified).
    conn = sqlite3.connect(str(db), isolation_level=None)
    results = {"added_columns": [], "backfilled": 0, "skipped_columns": []}

    try:
        # Check signal_state exists. The optional table create is setup, not part
        # of the atomic ALTER+backfill unit, so it commits on its own (autocommit
        # is in effect until the explicit BEGIN below).
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

        # Begin the atomic ALTER + backfill transaction.
        conn.execute("BEGIN")

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

        # Commit the atomic ALTER + backfill transaction.
        conn.execute("COMMIT")
        logger.info("v32 migration complete: %s", results)
        return results

    except (sqlite3.Error, ValueError, OSError) as exc:
        logger.error("v32 migration failed: %s", exc)
        # Roll back the ALTER + backfill transaction so columns are not left
        # added-but-unbackfilled. Guard the ROLLBACK: if the failure occurred
        # before BEGIN (no active transaction), ROLLBACK would itself raise and
        # mask the real error.
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            logger.debug("v32 rollback: no active transaction to roll back")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = migrate()
    print(f"Migration v32 complete: {result}")
