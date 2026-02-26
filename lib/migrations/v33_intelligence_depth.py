"""
Migration v33: Intelligence Depth tables.

Adds:
- signal_outcomes: Tracks what happens when signals clear (ID-4.1)

Brief 18 (ID), Task ID-4.1
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 33
DESCRIPTION = "Add signal_outcomes table for outcome tracking"


def migrate(db_path: Path) -> None:
    """Apply v33 migration."""
    conn = sqlite3.connect(str(db_path))
    try:
        # Create signal_outcomes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                id TEXT PRIMARY KEY,
                signal_key TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                cleared_at TEXT NOT NULL,
                duration_days REAL NOT NULL,
                health_before REAL,
                health_after REAL,
                health_improved INTEGER,
                actions_taken TEXT,
                resolution_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_entity "
            "ON signal_outcomes(entity_type, entity_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_type "
            "ON signal_outcomes(signal_type, resolution_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_time "
            "ON signal_outcomes(cleared_at DESC)"
        )

        conn.commit()
        logger.info("v33 migration applied: signal_outcomes table created")
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error(f"v33 migration failed: {e}")
        raise
    finally:
        conn.close()
