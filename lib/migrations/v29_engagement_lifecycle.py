"""
v2.9 Engagement Lifecycle Migration

Creates the engagements table with 7-state lifecycle and transition audit table.

Spec: §6.7 Engagement Lifecycle, §7.4 Engagements API
"""

import logging

logger = logging.getLogger(__name__)


MIGRATION_SQL = """
-- Engagements table with lifecycle state (Spec §6.7)
CREATE TABLE IF NOT EXISTS engagements (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('project', 'retainer')),
    state TEXT NOT NULL DEFAULT 'planned' CHECK (state IN (
        'planned', 'active', 'blocked', 'paused',
        'delivering', 'delivered', 'completed'
    )),
    -- Asana integration
    asana_project_gid TEXT,
    asana_url TEXT,
    -- Dates
    started_at TEXT,
    completed_at TEXT,
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- Foreign keys
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id)
);

CREATE INDEX IF NOT EXISTS idx_engagements_client_id ON engagements(client_id);
CREATE INDEX IF NOT EXISTS idx_engagements_state ON engagements(state);
CREATE INDEX IF NOT EXISTS idx_engagements_asana_gid ON engagements(asana_project_gid);

-- Engagement transitions audit table (Spec §6.7)
CREATE TABLE IF NOT EXISTS engagement_transitions (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT,
    actor TEXT,
    note TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE INDEX IF NOT EXISTS idx_engagement_transitions_engagement_id
ON engagement_transitions(engagement_id);
"""


def run_migration(conn):
    """Execute the engagement lifecycle migration."""
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    logger.info("✓ Engagement lifecycle tables created")


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
