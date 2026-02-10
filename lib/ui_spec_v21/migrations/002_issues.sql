-- Migration 002: issues table
-- Spec Section 6.14

CREATE TABLE IF NOT EXISTS issues (
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
  evidence TEXT NOT NULL,  -- JSON
  evidence_version TEXT NOT NULL DEFAULT 'v1',

  -- Tagging (set on Tag or Assign)
  tagged_by_user_id TEXT,
  tagged_at TEXT,

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
  suppressed_at TEXT,
  suppressed_by TEXT,

  -- Escalation (parallel flag, not a state)
  escalated INTEGER NOT NULL DEFAULT 0,
  escalated_at TEXT,
  escalated_by TEXT,

  -- Timestamps
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_issues_client ON issues(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(type);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_suppressed ON issues(suppressed);
CREATE INDEX IF NOT EXISTS idx_issues_engagement ON issues(engagement_id);
CREATE INDEX IF NOT EXISTS idx_issues_brand ON issues(brand_id);
CREATE INDEX IF NOT EXISTS idx_issues_snoozed_until ON issues(snoozed_until) WHERE state = 'snoozed';
