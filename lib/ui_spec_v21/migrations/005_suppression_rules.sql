-- Migration 005: inbox_suppression_rules
-- Spec Section 1.8

CREATE TABLE IF NOT EXISTS inbox_suppression_rules (
  id TEXT PRIMARY KEY,
  suppression_key TEXT NOT NULL UNIQUE,
  item_type TEXT NOT NULL CHECK (item_type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,  -- NULL = permanent
  reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_suppression_rules_key ON inbox_suppression_rules(suppression_key);
CREATE INDEX IF NOT EXISTS idx_suppression_rules_expires ON inbox_suppression_rules(expires_at);
CREATE INDEX IF NOT EXISTS idx_suppression_rules_type ON inbox_suppression_rules(item_type);
