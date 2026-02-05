"""
Time OS V4 Migration - Milestone 1: Truth & Proof Backbone

Adds:
- artifacts (normalized evidence stream)
- artifact_blobs (immutable raw storage)
- artifact_excerpts (anchored proof)
- entity_links (explicit graph linking)
- identity_profiles (canonical identities)
- identity_claims (identity evidence)
- identity_operations (merge/split audit)
- fix_data_queue (data quality issues)

Run: python -m lib.migrations.v4_milestone1_truth_proof
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')

MIGRATION_VERSION = 4001  # V4, Milestone 1

SCHEMA_SQL = """
-- ============================================================
-- ARTIFACTS: Normalized Evidence Stream
-- ============================================================

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,  -- gmail, gchat, calendar, asana, docs, sheets, drive, minutes_gemini, billing, xero
    source_id TEXT NOT NULL,  -- stable upstream identifier
    type TEXT NOT NULL,  -- message, thread, calendar_event, meeting, minutes, task, task_update, doc_update, invoice, payment
    occurred_at TEXT NOT NULL,
    actor_person_id TEXT,  -- nullable, references identity_profiles
    payload_ref TEXT NOT NULL,  -- pointer to blob_id or inline
    content_hash TEXT NOT NULL,  -- dedupe + integrity
    visibility_tags TEXT DEFAULT '[]',  -- JSON array for ACL/routing
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_source ON artifacts(source);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type);
CREATE INDEX IF NOT EXISTS idx_artifacts_occurred_at ON artifacts(occurred_at);
CREATE INDEX IF NOT EXISTS idx_artifacts_actor ON artifacts(actor_person_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_content_hash ON artifacts(content_hash);

-- ============================================================
-- ARTIFACT BLOBS: Immutable Raw Storage
-- ============================================================

CREATE TABLE IF NOT EXISTS artifact_blobs (
    blob_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,  -- JSON or base64 encoded
    mime_type TEXT DEFAULT 'application/json',
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    retention_class TEXT NOT NULL DEFAULT 'standard'  -- standard, extended, legal_hold
);

CREATE INDEX IF NOT EXISTS idx_blobs_hash ON artifact_blobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_blobs_retention ON artifact_blobs(retention_class);

-- ============================================================
-- ARTIFACT EXCERPTS: Anchored Proof
-- ============================================================

CREATE TABLE IF NOT EXISTS artifact_excerpts (
    excerpt_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    anchor_type TEXT NOT NULL,  -- byte_span, line_span, json_path, message_quote
    anchor_start TEXT NOT NULL,  -- could be int or path depending on type
    anchor_end TEXT NOT NULL,
    excerpt_text TEXT NOT NULL,  -- cached excerpt content
    excerpt_hash TEXT NOT NULL,  -- for integrity
    redaction_status TEXT DEFAULT 'none',  -- none, pending, redacted
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_excerpts_artifact ON artifact_excerpts(artifact_id);
CREATE INDEX IF NOT EXISTS idx_excerpts_hash ON artifact_excerpts(excerpt_hash);

-- ============================================================
-- ENTITY LINKS: Explicit Graph Linking
-- ============================================================

CREATE TABLE IF NOT EXISTS entity_links (
    link_id TEXT PRIMARY KEY,
    from_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    to_entity_type TEXT NOT NULL,  -- client, brand, engagement, project, task, person, invoice, thread, meeting
    to_entity_id TEXT NOT NULL,
    method TEXT NOT NULL,  -- headers, participants, naming, rules, embedding, nlp, user_confirmed
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    confidence_reasons TEXT DEFAULT '[]',  -- JSON array explaining confidence
    status TEXT NOT NULL DEFAULT 'proposed',  -- proposed, confirmed, rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_by TEXT,  -- actor who confirmed/rejected
    confirmed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_links_artifact ON entity_links(from_artifact_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_entity ON entity_links(to_entity_type, to_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_status ON entity_links(status);
CREATE INDEX IF NOT EXISTS idx_entity_links_confidence ON entity_links(confidence);
CREATE INDEX IF NOT EXISTS idx_entity_links_method ON entity_links(method);

-- ============================================================
-- IDENTITY PROFILES: Canonical Identities
-- ============================================================

CREATE TABLE IF NOT EXISTS identity_profiles (
    profile_id TEXT PRIMARY KEY,
    profile_type TEXT NOT NULL,  -- person, org
    canonical_name TEXT NOT NULL,
    canonical_email TEXT,  -- primary email if person
    canonical_domain TEXT,  -- primary domain if org
    status TEXT NOT NULL DEFAULT 'active',  -- active, merged, split, inactive
    metadata TEXT DEFAULT '{}',  -- JSON for additional attrs
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_identity_profiles_type ON identity_profiles(profile_type);
CREATE INDEX IF NOT EXISTS idx_identity_profiles_status ON identity_profiles(status);
CREATE INDEX IF NOT EXISTS idx_identity_profiles_name ON identity_profiles(canonical_name);

-- ============================================================
-- IDENTITY CLAIMS: Identity Evidence
-- ============================================================

CREATE TABLE IF NOT EXISTS identity_claims (
    claim_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES identity_profiles(profile_id),
    claim_type TEXT NOT NULL,  -- email, domain, chat_handle, calendar_id, asana_id, phone, alias_name
    claim_value TEXT NOT NULL,
    claim_value_normalized TEXT NOT NULL,  -- lowercase, trimmed
    source TEXT NOT NULL,  -- which system provided this
    source_artifact_id TEXT,  -- optional reference to artifact
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL DEFAULT 'active',  -- active, superseded, rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(claim_type, claim_value_normalized)
);

CREATE INDEX IF NOT EXISTS idx_identity_claims_profile ON identity_claims(profile_id);
CREATE INDEX IF NOT EXISTS idx_identity_claims_lookup ON identity_claims(claim_type, claim_value_normalized);
CREATE INDEX IF NOT EXISTS idx_identity_claims_status ON identity_claims(status);

-- ============================================================
-- IDENTITY OPERATIONS: Merge/Split Audit
-- ============================================================

CREATE TABLE IF NOT EXISTS identity_operations (
    op_id TEXT PRIMARY KEY,
    op_type TEXT NOT NULL,  -- merge, split, create, deactivate
    from_profile_ids TEXT NOT NULL,  -- JSON array
    to_profile_ids TEXT NOT NULL,  -- JSON array
    reason TEXT NOT NULL,
    evidence_artifact_ids TEXT DEFAULT '[]',  -- JSON array
    actor TEXT NOT NULL,  -- system or user id
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_identity_ops_type ON identity_operations(op_type);
CREATE INDEX IF NOT EXISTS idx_identity_ops_created ON identity_operations(created_at);

-- ============================================================
-- FIX DATA QUEUE: Data Quality Issues
-- ============================================================

CREATE TABLE IF NOT EXISTS fix_data_queue (
    fix_id TEXT PRIMARY KEY,
    fix_type TEXT NOT NULL,  -- ambiguous_link, missing_link, identity_conflict, hierarchy_violation, duplicate_entity
    severity TEXT NOT NULL DEFAULT 'medium',  -- low, medium, high, critical
    entity_type TEXT,
    entity_id TEXT,
    artifact_id TEXT,
    description TEXT NOT NULL,
    context TEXT DEFAULT '{}',  -- JSON with details
    suggested_actions TEXT DEFAULT '[]',  -- JSON array of possible fixes
    status TEXT NOT NULL DEFAULT 'open',  -- open, in_progress, resolved, dismissed
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fix_data_status ON fix_data_queue(status);
CREATE INDEX IF NOT EXISTS idx_fix_data_type ON fix_data_queue(fix_type);
CREATE INDEX IF NOT EXISTS idx_fix_data_severity ON fix_data_queue(severity);
CREATE INDEX IF NOT EXISTS idx_fix_data_entity ON fix_data_queue(entity_type, entity_id);

-- ============================================================
-- LINK EXISTING TABLES: Bridge to new schema
-- ============================================================

-- Add artifact tracking columns to existing tables if not present
-- These allow us to track which artifact created/updated each record

-- Note: SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we use a workaround

"""

def column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def add_column_if_not_exists(cursor, table, column, column_def):
    """Add a column to a table if it doesn't exist."""
    if not column_exists(cursor, table, column):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
            print(f"  Added column {table}.{column}")
            return True
        except sqlite3.OperationalError as e:
            print(f"  Warning: Could not add {table}.{column}: {e}")
            return False
    return False

def run_migration():
    """Execute the migration."""
    print(f"Running V4 Milestone 1 Migration...")
    print(f"Database: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check current schema version
        cursor.execute("SELECT MAX(version) FROM _schema_version")
        current_version = cursor.fetchone()[0] or 0
        print(f"Current schema version: {current_version}")
        
        if current_version >= MIGRATION_VERSION:
            print(f"Migration {MIGRATION_VERSION} already applied. Skipping.")
            return True
        
        # Execute main schema
        print("Creating new tables...")
        cursor.executescript(SCHEMA_SQL)
        
        # Add bridge columns to existing tables
        print("Adding bridge columns to existing tables...")
        
        # clients table
        add_column_if_not_exists(cursor, 'clients', 'identity_profile_id', 'TEXT')
        add_column_if_not_exists(cursor, 'clients', 'source_artifact_id', 'TEXT')
        
        # people table
        add_column_if_not_exists(cursor, 'people', 'identity_profile_id', 'TEXT')
        add_column_if_not_exists(cursor, 'people', 'source_artifact_id', 'TEXT')
        
        # projects table
        add_column_if_not_exists(cursor, 'projects', 'source_artifact_id', 'TEXT')
        add_column_if_not_exists(cursor, 'projects', 'engagement_type', "TEXT DEFAULT 'project'")  # project or retainer
        
        # Record migration version
        cursor.execute(
            "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, datetime.now().isoformat())
        )
        
        conn.commit()
        print(f"Migration {MIGRATION_VERSION} applied successfully!")
        
        # Print summary
        print("\n=== New Tables Created ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        new_tables = ['artifacts', 'artifact_blobs', 'artifact_excerpts', 'entity_links', 
                      'identity_profiles', 'identity_claims', 'identity_operations', 'fix_data_queue']
        for t in new_tables:
            status = "✓" if t in tables else "✗"
            print(f"  {status} {t}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def verify_migration():
    """Verify the migration was successful."""
    print("\n=== Verifying Migration ===")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check all expected tables exist
        expected_tables = [
            'artifacts', 'artifact_blobs', 'artifact_excerpts',
            'entity_links', 'identity_profiles', 'identity_claims',
            'identity_operations', 'fix_data_queue'
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        
        all_present = True
        for table in expected_tables:
            if table in existing:
                # Count rows
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  ✓ {table}: {count} rows")
            else:
                print(f"  ✗ {table}: MISSING")
                all_present = False
        
        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"\n  Indexes created: {len(indexes)}")
        
        return all_present
        
    finally:
        conn.close()


if __name__ == '__main__':
    success = run_migration()
    if success:
        verify_migration()
