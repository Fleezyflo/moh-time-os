"""
Time OS V4 Migration - Milestone 4: Intersections, Reports & Policy

Adds:
- couplings table
- report_templates + report_snapshots
- protocol_violations
- access_roles + entity_acl + retention_rules + redaction_markers
"""

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")
MIGRATION_VERSION = 4004

SCHEMA_SQL = """
-- Couplings
CREATE TABLE IF NOT EXISTS couplings (
    coupling_id TEXT PRIMARY KEY,
    anchor_ref_type TEXT NOT NULL,
    anchor_ref_id TEXT NOT NULL,
    entity_refs TEXT NOT NULL,
    coupling_type TEXT NOT NULL,
    strength REAL NOT NULL CHECK (strength >= 0 AND strength <= 1),
    why TEXT NOT NULL,
    investigation_path TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_couplings_anchor ON couplings(anchor_ref_type, anchor_ref_id);

-- Reports
CREATE TABLE IF NOT EXISTS report_templates (
    template_id TEXT PRIMARY KEY,
    template_type TEXT NOT NULL,
    sections TEXT NOT NULL,
    default_scopes TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS report_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES report_templates(template_id),
    scope_ref_type TEXT NOT NULL,
    scope_ref_id TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    content TEXT NOT NULL,
    evidence_excerpt_ids TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    immutable_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_report_snapshots_scope ON report_snapshots(scope_ref_type, scope_ref_id);
CREATE INDEX IF NOT EXISTS idx_report_snapshots_period ON report_snapshots(period_start, period_end);

-- Protocol violations
CREATE TABLE IF NOT EXISTS protocol_violations (
    violation_id TEXT PRIMARY KEY,
    violation_type TEXT NOT NULL,
    scope_refs TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence_excerpt_ids TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_protocol_violations_status ON protocol_violations(status);
CREATE INDEX IF NOT EXISTS idx_protocol_violations_severity ON protocol_violations(severity);

-- Policy: ACL, retention, redaction
CREATE TABLE IF NOT EXISTS access_roles (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    permissions TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS entity_acl (
    acl_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES access_roles(role_id),
    permission TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_type, entity_id, role_id)
);
CREATE TABLE IF NOT EXISTS retention_rules (
    rule_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    type TEXT,
    retention_days INTEGER NOT NULL,
    legal_hold_supported INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS redaction_markers (
    marker_id TEXT PRIMARY KEY,
    excerpt_id TEXT NOT NULL,
    redaction_type TEXT NOT NULL,
    redacted_by TEXT NOT NULL,
    redacted_at TEXT NOT NULL DEFAULT (datetime('now')),
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_entity_acl ON entity_acl(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_redaction_markers_excerpt ON redaction_markers(excerpt_id);
"""


def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check version
    try:
        cursor.execute("SELECT MAX(version) FROM _schema_version")
        current = cursor.fetchone()[0] or 0
        if current >= MIGRATION_VERSION:
            logger.info(f"Migration {MIGRATION_VERSION} already applied.")
            return
    except sqlite3.OperationalError:
        logger.info("_schema_version table missing. Run v4_milestone1 migration first.")
        return

    cursor.executescript(SCHEMA_SQL)
    cursor.execute(
        "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
        (MIGRATION_VERSION, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    logger.info(f"Migration {MIGRATION_VERSION} applied.")


if __name__ == "__main__":
    run_migration()
