"""
v2.9 Org Settings Migration

Creates the org_settings table for timezone and currency configuration.

Spec: §0.1 Global Conventions (org.timezone, org.base_currency, finance_calc_version)
"""

import logging

logger = logging.getLogger(__name__)


MIGRATION_SQL = """
-- Org Settings Table (Spec §0.1)
CREATE TABLE IF NOT EXISTS org_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'Asia/Dubai',
    base_currency TEXT NOT NULL DEFAULT 'AED',
    finance_calc_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Insert default settings if not exists
INSERT OR IGNORE INTO org_settings (id, timezone, base_currency, finance_calc_version, created_at, updated_at)
VALUES (1, 'Asia/Dubai', 'AED', 'v1', datetime('now'), datetime('now'));
"""


def run_migration(conn):
    """Execute the org settings migration."""
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    logger.info("✓ Org settings table created")


if __name__ == "__main__":
    import sqlite3

    from lib import paths

    db_path = paths.db_path()
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        run_migration(conn)
        conn.close()
    else:
        logger.info(f"Database not found: {db_path}")
