-- Migration 001: inbox_items_v29 table (primary table)
-- Spec Section 6.13 - using v29 naming for API compatibility

-- Create inbox_items_v29 as the primary table
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
  state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'snoozed', 'dismissed', 'linked_to_issue')),
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

  -- Timestamps
  proposed_at TEXT NOT NULL,
  last_refreshed_at TEXT,
  read_at TEXT,
  resurfaced_at TEXT,
  resolved_at TEXT,

  -- Snooze (populated when state = 'snoozed')
  snooze_until TEXT,
  snoozed_by TEXT,
  snoozed_at TEXT,
  snooze_reason TEXT,

  -- Dismissal (populated when state = 'dismissed')
  dismissed_by TEXT,
  dismissed_at TEXT,
  dismiss_reason TEXT,
  suppression_key TEXT,

  -- Underlying entity (exactly one of these is set)
  underlying_issue_id TEXT,
  underlying_signal_id TEXT,

  -- Resolution (populated when state = 'linked_to_issue')
  resolved_issue_id TEXT,

  -- Scoping (nullable per type)
  client_id TEXT,
  brand_id TEXT,
  engagement_id TEXT,

  -- Metadata
  title TEXT NOT NULL,
  evidence TEXT,
  evidence_version TEXT DEFAULT 'v1',
  resolution_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_client ON inbox_items_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_proposed ON inbox_items_v29(proposed_at);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_suppression ON inbox_items_v29(suppression_key);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_severity ON inbox_items_v29(severity);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_resolved ON inbox_items_v29(resolved_at);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_underlying_issue ON inbox_items_v29(underlying_issue_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_underlying_signal ON inbox_items_v29(underlying_signal_id);

-- Create inbox_items as view for backward compatibility with test helpers
CREATE VIEW IF NOT EXISTS inbox_items AS SELECT * FROM inbox_items_v29;

-- INSTEAD OF trigger to allow inserts into the view
CREATE TRIGGER IF NOT EXISTS inbox_items_insert
INSTEAD OF INSERT ON inbox_items
BEGIN
  INSERT INTO inbox_items_v29 (
    id, type, state, severity, proposed_at, last_refreshed_at, read_at, resurfaced_at,
    resolved_at, snooze_until, snoozed_by, snoozed_at, snooze_reason,
    dismissed_by, dismissed_at, dismiss_reason, suppression_key,
    underlying_issue_id, underlying_signal_id, resolved_issue_id,
    client_id, brand_id, engagement_id, title, evidence, evidence_version,
    resolution_reason, created_at, updated_at
  ) VALUES (
    NEW.id, NEW.type, NEW.state, NEW.severity, NEW.proposed_at, 
    COALESCE(NEW.last_refreshed_at, NEW.proposed_at), NEW.read_at, NEW.resurfaced_at,
    NEW.resolved_at, NEW.snooze_until, NEW.snoozed_by, NEW.snoozed_at, NEW.snooze_reason,
    NEW.dismissed_by, NEW.dismissed_at, NEW.dismiss_reason, NEW.suppression_key,
    NEW.underlying_issue_id, NEW.underlying_signal_id, NEW.resolved_issue_id,
    NEW.client_id, NEW.brand_id, NEW.engagement_id, NEW.title, NEW.evidence, NEW.evidence_version,
    NEW.resolution_reason, NEW.created_at, NEW.updated_at
  );
END;

-- INSTEAD OF trigger for updates
CREATE TRIGGER IF NOT EXISTS inbox_items_update
INSTEAD OF UPDATE ON inbox_items
BEGIN
  UPDATE inbox_items_v29 SET
    type = NEW.type,
    state = NEW.state,
    severity = NEW.severity,
    proposed_at = NEW.proposed_at,
    last_refreshed_at = NEW.last_refreshed_at,
    read_at = NEW.read_at,
    resurfaced_at = NEW.resurfaced_at,
    resolved_at = NEW.resolved_at,
    snooze_until = NEW.snooze_until,
    snoozed_by = NEW.snoozed_by,
    snoozed_at = NEW.snoozed_at,
    snooze_reason = NEW.snooze_reason,
    dismissed_by = NEW.dismissed_by,
    dismissed_at = NEW.dismissed_at,
    dismiss_reason = NEW.dismiss_reason,
    suppression_key = NEW.suppression_key,
    underlying_issue_id = NEW.underlying_issue_id,
    underlying_signal_id = NEW.underlying_signal_id,
    resolved_issue_id = NEW.resolved_issue_id,
    client_id = NEW.client_id,
    brand_id = NEW.brand_id,
    engagement_id = NEW.engagement_id,
    title = NEW.title,
    evidence = NEW.evidence,
    evidence_version = NEW.evidence_version,
    resolution_reason = NEW.resolution_reason,
    updated_at = NEW.updated_at
  WHERE id = OLD.id;
END;

-- INSTEAD OF trigger for deletes
CREATE TRIGGER IF NOT EXISTS inbox_items_delete
INSTEAD OF DELETE ON inbox_items
BEGIN
  DELETE FROM inbox_items_v29 WHERE id = OLD.id;
END;
