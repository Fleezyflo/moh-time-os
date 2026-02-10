-- Migration 001: inbox_items table
-- Spec Section 6.13

-- Create inbox_items table
CREATE TABLE IF NOT EXISTS inbox_items (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
  state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'snoozed', 'dismissed', 'linked_to_issue')),
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

  -- Timestamps
  proposed_at TEXT NOT NULL,
  read_at TEXT,
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
  evidence TEXT NOT NULL,  -- JSON
  evidence_version TEXT NOT NULL DEFAULT 'v1',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_inbox_items_state ON inbox_items(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_type ON inbox_items(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_client ON inbox_items(client_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_proposed ON inbox_items(proposed_at);
CREATE INDEX IF NOT EXISTS idx_inbox_items_suppression ON inbox_items(suppression_key);
CREATE INDEX IF NOT EXISTS idx_inbox_items_severity ON inbox_items(severity);
CREATE INDEX IF NOT EXISTS idx_inbox_items_resolved ON inbox_items(resolved_at);
CREATE INDEX IF NOT EXISTS idx_inbox_items_underlying_issue ON inbox_items(underlying_issue_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_underlying_signal ON inbox_items(underlying_signal_id);
