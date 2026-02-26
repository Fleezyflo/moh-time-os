"""
Score History Migration

Creates the score_history table for tracking entity scores over time.
This enables trend analysis ("did this client improve over the last month?").

Run: python -m lib.migrations.v30_score_history
"""

import logging
import sqlite3
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)


# Schema for score_history table
SCORE_HISTORY_SCHEMA = """
-- Score history for trend analysis
CREATE TABLE IF NOT EXISTS score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,      -- 'client', 'project', 'person', 'portfolio'
    entity_id TEXT NOT NULL,
    composite_score REAL NOT NULL,
    dimensions_json TEXT,           -- Full dimension breakdown as JSON
    data_completeness REAL,         -- How complete was the data (0-1)
    recorded_at TEXT NOT NULL,      -- ISO timestamp when score was computed
    recorded_date TEXT NOT NULL,    -- YYYY-MM-DD for daily grouping

    UNIQUE(entity_type, entity_id, recorded_date)  -- One per entity per day
);

CREATE INDEX IF NOT EXISTS idx_score_history_lookup
ON score_history(entity_type, entity_id, recorded_date);

CREATE INDEX IF NOT EXISTS idx_score_history_date
ON score_history(recorded_date);

CREATE INDEX IF NOT EXISTS idx_score_history_entity
ON score_history(entity_type, entity_id);
"""


def run_migration(db_path: Path | None = None) -> dict:
    """
    Run the score history migration.

    Returns:
        dict with migration results
    """
    if db_path is None:
        db_path = paths.db_path()

    logger.info(f"Running score_history migration on {db_path}")

    results = {
        "tables_created": [],
        "indexes_created": [],
        "errors": [],
    }

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='score_history'
        """)

        if cursor.fetchone():
            logger.info("score_history table already exists")
            results["tables_created"].append("score_history (already exists)")
        else:
            # Execute schema
            cursor.executescript(SCORE_HISTORY_SCHEMA)
            conn.commit()
            logger.info("✓ Created score_history table")
            results["tables_created"].append("score_history")
            results["indexes_created"].extend(
                [
                    "idx_score_history_lookup",
                    "idx_score_history_date",
                    "idx_score_history_entity",
                ]
            )

        conn.close()

    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error(f"Migration failed: {e}")
        results["errors"].append(str(e))

    return results


def verify_migration(db_path: Path | None = None) -> bool:
    """Verify the migration was successful."""
    if db_path is None:
        db_path = paths.db_path()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='score_history'
    """)
    table_exists = cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(score_history)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        "id",
        "entity_type",
        "entity_id",
        "composite_score",
        "dimensions_json",
        "data_completeness",
        "recorded_at",
        "recorded_date",
    }

    conn.close()

    return table_exists and expected_columns.issubset(columns)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_migration()
    print(f"Migration result: {result}")

    if verify_migration():
        print("✓ Migration verified successfully")
    else:
        print("✗ Migration verification failed")
