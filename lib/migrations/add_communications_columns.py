"""Add missing columns to communications table.

Adds: from_domain, client_id, link_status
These are required by lib/normalizer.py for client identity matching.

Idempotent: checks column existence before ALTER TABLE.
"""

import logging
import sqlite3
from pathlib import Path

from lib import paths as _paths

logger = logging.getLogger(__name__)

# Default DB path from central paths module
DEFAULT_DB = _paths.db_path()

COLUMNS_TO_ADD = [
    ("from_domain", "TEXT", None),
    ("client_id", "TEXT", None),
    ("link_status", "TEXT", "'unlinked'"),
]


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run(db_path: str | Path | None = None) -> int:
    """Add missing columns to communications table.

    Returns number of columns added (0 if all already exist).
    """
    db_path = str(db_path or DEFAULT_DB)
    conn = sqlite3.connect(db_path)
    added = 0

    for col_name, col_type, default in COLUMNS_TO_ADD:
        if _column_exists(conn, "communications", col_name):
            logger.info("Column %s already exists — skipping", col_name)
            continue

        ddl = f"ALTER TABLE communications ADD COLUMN {col_name} {col_type}"
        if default is not None:
            ddl += f" DEFAULT {default}"

        conn.execute(ddl)
        logger.info("Added column: communications.%s (%s)", col_name, col_type)
        added += 1

    conn.commit()
    conn.close()

    logger.info("Migration complete: %d columns added", added)
    return added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"Added {count} columns to communications table")
