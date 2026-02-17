-- Migration 008: v29 alias views
-- Creates views with _v29 suffix for compatibility with API code
-- These are simple aliases to the base tables

-- inbox_items_v29: alias to inbox_items
CREATE VIEW IF NOT EXISTS inbox_items_v29 AS
SELECT
    id,
    type,
    state,
    severity,
    proposed_at,
    COALESCE(last_refreshed_at, proposed_at) AS last_refreshed_at,
    read_at,
    resurfaced_at,
    resolved_at,
    snooze_until,
    snoozed_by,
    snoozed_at,
    snooze_reason,
    dismissed_by,
    dismissed_at,
    dismiss_reason,
    suppression_key,
    underlying_issue_id,
    underlying_signal_id,
    resolved_issue_id,
    title,
    client_id,
    brand_id,
    engagement_id,
    evidence,
    evidence_version,
    resolution_reason,
    created_at,
    updated_at
FROM inbox_items;

-- issues_v29: alias to issues
CREATE VIEW IF NOT EXISTS issues_v29 AS
SELECT
    id,
    type,
    state,
    severity,
    client_id,
    brand_id,
    engagement_id,
    title,
    evidence,
    evidence_version,
    suppressed,
    suppression_key,
    suppressed_by,
    suppressed_at,
    snooze_until,
    snoozed_by,
    snoozed_at,
    snooze_reason,
    assigned_to,
    assigned_by,
    assigned_at,
    tagged_by,
    created_at,
    updated_at
FROM issues;

-- signals_v29: alias to signals
CREATE VIEW IF NOT EXISTS signals_v29 AS
SELECT
    id,
    source,
    source_id,
    client_id,
    engagement_id,
    severity,
    title,
    payload,
    first_seen_at,
    last_seen_at,
    cleared_at,
    created_at,
    updated_at
FROM signals;

-- inbox_suppression_rules_v29: alias to inbox_suppression_rules
CREATE VIEW IF NOT EXISTS inbox_suppression_rules_v29 AS
SELECT
    key,
    scope,
    entity_id,
    expires_at,
    created_by,
    created_at
FROM inbox_suppression_rules;
