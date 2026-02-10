-- Migration 003: signals table
-- Spec Section 6.15

CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL CHECK (source IN ('asana', 'gmail', 'gchat', 'calendar', 'meet', 'minutes', 'xero')),
  source_id TEXT NOT NULL,

  -- Classification
  sentiment TEXT NOT NULL CHECK (sentiment IN ('good', 'neutral', 'bad')),
  signal_type TEXT,
  rule_triggered TEXT,

  -- Scoping (derived or explicit)
  client_id TEXT,
  brand_id TEXT,
  engagement_id TEXT,

  -- Content
  summary TEXT NOT NULL,
  evidence TEXT NOT NULL,  -- JSON
  analysis_provider TEXT,

  -- Dismissal (if dismissed without becoming issue)
  dismissed INTEGER NOT NULL DEFAULT 0,
  dismissed_at TEXT,
  dismissed_by TEXT,

  -- Timestamps
  observed_at TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source);
CREATE INDEX IF NOT EXISTS idx_signals_client ON signals(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_sentiment ON signals(sentiment);
CREATE INDEX IF NOT EXISTS idx_signals_observed ON signals(observed_at);
CREATE INDEX IF NOT EXISTS idx_signals_engagement ON signals(engagement_id);
CREATE INDEX IF NOT EXISTS idx_signals_dismissed ON signals(dismissed);
CREATE INDEX IF NOT EXISTS idx_signals_rule ON signals(rule_triggered);

-- Unique constraint on source + source_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_source_unique ON signals(source, source_id);
