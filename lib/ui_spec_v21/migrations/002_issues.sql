-- Migration 002: issues_v29 table (primary table)
-- Spec Section 6.14 - using v29 naming for API compatibility

CREATE TABLE IF NOT EXISTS issues_v29 (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('financial', 'schedule_delivery', 'communication', 'risk')),
  state TEXT NOT NULL DEFAULT 'detected' CHECK (state IN (
    'detected', 'surfaced', 'snoozed', 'acknowledged', 'addressing',
    'awaiting_resolution', 'resolved', 'regression_watch', 'closed', 'regressed'
  )),
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

  -- Scoping
  client_id TEXT NOT NULL,
  brand_id TEXT,
  engagement_id TEXT,

  -- Core fields
  title TEXT NOT NULL,
  evidence TEXT,
  evidence_version TEXT DEFAULT 'v1',
  aggregation_key TEXT,

  -- Tagging (set on Tag or Assign)
  tagged_by_user_id TEXT,
  tagged_at TEXT,
  tagged_by TEXT,

  -- Assignment (set on Assign)
  assigned_to TEXT,
  assigned_at TEXT,
  assigned_by TEXT,

  -- Snooze (when state = 'snoozed')
  snoozed_until TEXT,
  snoozed_by TEXT,
  snoozed_at TEXT,
  snooze_reason TEXT,

  -- Suppression (parallel flag, not a state)
  suppressed INTEGER NOT NULL DEFAULT 0,
  suppression_key TEXT,
  suppressed_at TEXT,
  suppressed_by TEXT,

  -- Escalation (parallel flag, not a state)
  escalated INTEGER NOT NULL DEFAULT 0,
  escalated_at TEXT,
  escalated_by TEXT,

  -- Regression watch
  regression_watch_until TEXT,
  closed_at TEXT,

  -- Timestamps
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_type ON issues_v29(type);
CREATE INDEX IF NOT EXISTS idx_issues_v29_severity ON issues_v29(severity);
CREATE INDEX IF NOT EXISTS idx_issues_v29_suppressed ON issues_v29(suppressed);
CREATE INDEX IF NOT EXISTS idx_issues_v29_engagement ON issues_v29(engagement_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_brand ON issues_v29(brand_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_snoozed_until ON issues_v29(snoozed_until);

-- Create issues as view for backward compatibility
CREATE VIEW IF NOT EXISTS issues AS SELECT * FROM issues_v29;

-- INSTEAD OF trigger for inserts
CREATE TRIGGER IF NOT EXISTS issues_insert
INSTEAD OF INSERT ON issues
BEGIN
  INSERT INTO issues_v29 (
    id, type, state, severity, client_id, brand_id, engagement_id,
    title, evidence, evidence_version, aggregation_key,
    tagged_by_user_id, tagged_at, tagged_by, assigned_to, assigned_at, assigned_by,
    snoozed_until, snoozed_by, snoozed_at, snooze_reason,
    suppressed, suppression_key, suppressed_at, suppressed_by,
    escalated, escalated_at, escalated_by,
    regression_watch_until, closed_at, created_at, updated_at
  ) VALUES (
    NEW.id, NEW.type, NEW.state, NEW.severity, NEW.client_id, NEW.brand_id, NEW.engagement_id,
    NEW.title, NEW.evidence, NEW.evidence_version, COALESCE(NEW.aggregation_key, NEW.id),
    NEW.tagged_by_user_id, NEW.tagged_at, NEW.tagged_by, NEW.assigned_to, NEW.assigned_at, NEW.assigned_by,
    NEW.snoozed_until, NEW.snoozed_by, NEW.snoozed_at, NEW.snooze_reason,
    COALESCE(NEW.suppressed, 0), NEW.suppression_key, NEW.suppressed_at, NEW.suppressed_by,
    COALESCE(NEW.escalated, 0), NEW.escalated_at, NEW.escalated_by,
    NEW.regression_watch_until, NEW.closed_at, NEW.created_at, NEW.updated_at
  );
END;

-- INSTEAD OF trigger for updates
CREATE TRIGGER IF NOT EXISTS issues_update
INSTEAD OF UPDATE ON issues
BEGIN
  UPDATE issues_v29 SET
    type = NEW.type, state = NEW.state, severity = NEW.severity,
    client_id = NEW.client_id, brand_id = NEW.brand_id, engagement_id = NEW.engagement_id,
    title = NEW.title, evidence = NEW.evidence, evidence_version = NEW.evidence_version,
    aggregation_key = NEW.aggregation_key,
    tagged_by_user_id = NEW.tagged_by_user_id, tagged_at = NEW.tagged_at, tagged_by = NEW.tagged_by,
    assigned_to = NEW.assigned_to, assigned_at = NEW.assigned_at, assigned_by = NEW.assigned_by,
    snoozed_until = NEW.snoozed_until, snoozed_by = NEW.snoozed_by, snoozed_at = NEW.snoozed_at, snooze_reason = NEW.snooze_reason,
    suppressed = NEW.suppressed, suppression_key = NEW.suppression_key, suppressed_at = NEW.suppressed_at, suppressed_by = NEW.suppressed_by,
    escalated = NEW.escalated, escalated_at = NEW.escalated_at, escalated_by = NEW.escalated_by,
    regression_watch_until = NEW.regression_watch_until, closed_at = NEW.closed_at,
    updated_at = NEW.updated_at
  WHERE id = OLD.id;
END;

-- INSTEAD OF trigger for deletes
CREATE TRIGGER IF NOT EXISTS issues_delete
INSTEAD OF DELETE ON issues
BEGIN
  DELETE FROM issues_v29 WHERE id = OLD.id;
END;
