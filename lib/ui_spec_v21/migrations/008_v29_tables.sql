-- Migration 008: v29 tables (matching production schema from lib/db.py)
-- Creates actual tables with _v29 suffix for API compatibility

-- issues_v29: production-compatible schema
CREATE TABLE IF NOT EXISTS issues_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('financial', 'schedule_delivery', 'communication', 'risk')),
    state TEXT NOT NULL DEFAULT 'detected' CHECK (state IN (
        'detected', 'surfaced', 'snoozed', 'acknowledged', 'addressing',
        'awaiting_resolution', 'regression_watch', 'closed', 'regressed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    client_id TEXT NOT NULL,
    brand_id TEXT,
    engagement_id TEXT,
    title TEXT NOT NULL,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    aggregation_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snoozed_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    tagged_by_user_id TEXT,
    tagged_at TEXT,
    assigned_to TEXT,
    assigned_at TEXT,
    assigned_by TEXT,
    suppressed INTEGER NOT NULL DEFAULT 0,
    suppressed_at TEXT,
    suppressed_by TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TEXT,
    escalated_by TEXT,
    regression_watch_until TEXT,
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_severity ON issues_v29(severity);
CREATE INDEX IF NOT EXISTS idx_issues_v29_type ON issues_v29(type);

-- issue_transitions_v29: audit table
CREATE TABLE IF NOT EXISTS issue_transitions_v29 (
    id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT,
    actor TEXT,
    reason TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_transitions_v29_issue ON issue_transitions_v29(issue_id);

-- inbox_items_v29: production-compatible schema
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN (
        'proposed', 'snoozed', 'linked_to_issue', 'dismissed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_client ON inbox_items_v29(client_id);

-- signals_v29: production-compatible schema
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
    evidence TEXT,
    dismissed_at TEXT,
    dismissed_by TEXT,
    analysis_provider TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_v29_client ON signals_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_source ON signals_v29(source, source_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_observed ON signals_v29(observed_at);

-- inbox_suppression_rules_v29: production-compatible schema
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
