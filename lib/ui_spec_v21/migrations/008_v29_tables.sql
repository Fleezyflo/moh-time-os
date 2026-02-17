-- Migration 008: v29 tables (replaces views for write compatibility)
-- Creates actual tables with _v29 suffix for API compatibility
-- The API code expects to INSERT/UPDATE these tables directly

-- inbox_items_v29: same structure as inbox_items with additional columns
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'snoozed', 'dismissed', 'linked_to_issue')),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT,
    read_at TEXT,
    resurfaced_at TEXT,
    resolved_at TEXT,
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    dismissed_by TEXT,
    dismissed_at TEXT,
    dismiss_reason TEXT,
    suppression_key TEXT,
    underlying_issue_id TEXT,
    underlying_signal_id TEXT,
    resolved_issue_id TEXT,
    title TEXT NOT NULL,
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    resolution_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_client ON inbox_items_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_proposed ON inbox_items_v29(proposed_at);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_suppression ON inbox_items_v29(suppression_key);

-- issues_v29: same structure as issues
CREATE TABLE IF NOT EXISTS issues_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('financial', 'schedule_delivery', 'communication', 'risk')),
    state TEXT NOT NULL DEFAULT 'surfaced' CHECK (state IN ('surfaced', 'acknowledged', 'addressing', 'awaiting_resolution', 'closed')),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    title TEXT NOT NULL,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    suppressed INTEGER DEFAULT 0,
    suppression_key TEXT,
    suppressed_by TEXT,
    suppressed_at TEXT,
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    assigned_to TEXT,
    assigned_by TEXT,
    assigned_at TEXT,
    tagged_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_severity ON issues_v29(severity);

-- signals_v29: same structure as signals
CREATE TABLE IF NOT EXISTS signals_v29 (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT,
    engagement_id TEXT,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    title TEXT NOT NULL,
    payload TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    cleared_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_v29_source ON signals_v29(source);
CREATE INDEX IF NOT EXISTS idx_signals_v29_client ON signals_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_severity ON signals_v29(severity);

-- inbox_suppression_rules_v29: same structure as inbox_suppression_rules
CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
    key TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK (scope IN ('client', 'engagement', 'global')),
    entity_id TEXT,
    expires_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_suppression_rules_v29_scope ON inbox_suppression_rules_v29(scope);
CREATE INDEX IF NOT EXISTS idx_suppression_rules_v29_expires ON inbox_suppression_rules_v29(expires_at);
