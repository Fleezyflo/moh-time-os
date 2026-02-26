"""
v2.9 Full Schema Migration

Creates all spec-aligned tables for CLIENT-UI-SPEC-v2.9.md.
This migration creates new tables alongside legacy tables.

Tables created:
- issues_v29: Spec-aligned issues table (§6.14)
- inbox_items_v29: Spec-aligned inbox items (§6.13)
- signals_v29: Spec-aligned signals (§6.15)

Run with: python3 lib/migrations/v29_full_schema.py
"""

import logging
import sqlite3
from datetime import datetime

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


def get_utc_now_iso() -> str:
    """Returns current UTC time in canonical 24-char format."""
    now = datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


SCHEMA_SQL = """
-- Issues table per §6.14
CREATE TABLE IF NOT EXISTS issues_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('financial', 'schedule_delivery', 'communication', 'risk')),
    state TEXT NOT NULL DEFAULT 'detected' CHECK (state IN (
        'detected', 'surfaced', 'snoozed', 'acknowledged', 'addressing',
        'awaiting_resolution', 'regression_watch', 'closed', 'regressed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

    -- Scope
    client_id TEXT NOT NULL,
    brand_id TEXT,
    engagement_id TEXT,

    -- Content
    title TEXT NOT NULL,
    evidence TEXT,  -- JSON
    evidence_version TEXT DEFAULT 'v1',
    aggregation_key TEXT NOT NULL,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Snooze fields
    snoozed_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,

    -- Assignment fields
    tagged_by_user_id TEXT,
    tagged_at TEXT,
    assigned_to TEXT,
    assigned_at TEXT,
    assigned_by TEXT,

    -- Suppression fields
    suppressed INTEGER NOT NULL DEFAULT 0,
    suppressed_at TEXT,
    suppressed_by TEXT,

    -- Escalation fields
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TEXT,
    escalated_by TEXT,

    -- Regression watch
    regression_watch_until TEXT,
    closed_at TEXT,

    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_severity ON issues_v29(severity);
CREATE INDEX IF NOT EXISTS idx_issues_v29_type ON issues_v29(type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_issues_v29_aggregation
ON issues_v29(type, aggregation_key) WHERE suppressed = 0;

-- Issue transitions audit table
CREATE TABLE IF NOT EXISTS issue_transitions_v29 (
    id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT,
    actor TEXT,
    reason TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues_v29(id)
);

CREATE INDEX IF NOT EXISTS idx_issue_transitions_v29_issue
ON issue_transitions_v29(issue_id);

-- Inbox items table per §6.13
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN (
        'proposed', 'snoozed', 'linked_to_issue', 'dismissed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

    -- Timestamps
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    read_at TEXT,
    resurfaced_at TEXT,
    resolved_at TEXT,

    -- Snooze fields
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,

    -- Dismissal fields
    dismissed_by TEXT,
    dismissed_at TEXT,
    dismiss_reason TEXT,
    suppression_key TEXT,

    -- Underlying entity (exactly one)
    underlying_issue_id TEXT,
    underlying_signal_id TEXT,
    resolved_issue_id TEXT,

    -- Content
    title TEXT NOT NULL,
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    evidence TEXT,  -- JSON
    evidence_version TEXT DEFAULT 'v1',

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (underlying_issue_id) REFERENCES issues_v29(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_client ON inbox_items_v29(client_id);

-- Signals table per §6.15
CREATE TABLE IF NOT EXISTS signals_v29 (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT,
    engagement_id TEXT,
    sentiment TEXT CHECK (sentiment IN ('good', 'neutral', 'bad')),
    signal_type TEXT,
    summary TEXT,
    observed_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    evidence TEXT,  -- JSON

    -- Dismissal
    dismissed_at TEXT,
    dismissed_by TEXT,

    -- For minutes signals
    analysis_provider TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_signals_v29_client ON signals_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_source ON signals_v29(source, source_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_observed ON signals_v29(observed_at);

-- Suppression rules table
CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
    id TEXT PRIMARY KEY,
    suppression_key TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    scope_client_id TEXT,
    scope_engagement_id TEXT,
    scope_source TEXT,
    scope_rule TEXT,
    reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_suppression_v29_key ON inbox_suppression_rules_v29(suppression_key);
CREATE INDEX IF NOT EXISTS idx_suppression_v29_expires ON inbox_suppression_rules_v29(expires_at);
"""


def run_migration():
    """Execute the full schema migration."""
    logger.info(f"Database: {DB_PATH}")
    if not DB_PATH.exists():
        logger.info(f"ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # Verify tables exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE '%v29'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        logger.info(f"✓ Created tables: {', '.join(tables)}")
        return True
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.info(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    success = run_migration()
    sys.exit(0 if success else 1)
