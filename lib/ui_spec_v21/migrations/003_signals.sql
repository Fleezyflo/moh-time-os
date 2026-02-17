-- Migration 003: signals_v29 table (primary table)
-- Spec Section 6.15 - using v29 naming for API compatibility

CREATE TABLE IF NOT EXISTS signals_v29 (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,

  -- Classification
  sentiment TEXT CHECK (sentiment IN ('good', 'neutral', 'bad')),
  signal_type TEXT,
  rule_triggered TEXT,
  severity TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  title TEXT,

  -- Scoping (derived or explicit)
  client_id TEXT,
  brand_id TEXT,
  engagement_id TEXT,

  -- Content
  summary TEXT,
  payload TEXT,
  evidence TEXT,
  analysis_provider TEXT,

  -- Dismissal (if dismissed without becoming issue)
  dismissed_at TEXT,
  dismissed_by TEXT,

  -- Timestamps
  first_seen_at TEXT,
  last_seen_at TEXT,
  observed_at TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  cleared_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_signals_v29_source ON signals_v29(source);
CREATE INDEX IF NOT EXISTS idx_signals_v29_client ON signals_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_sentiment ON signals_v29(sentiment);
CREATE INDEX IF NOT EXISTS idx_signals_v29_observed ON signals_v29(observed_at);
CREATE INDEX IF NOT EXISTS idx_signals_v29_engagement ON signals_v29(engagement_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_rule ON signals_v29(rule_triggered);

-- Create signals as view for backward compatibility
CREATE VIEW IF NOT EXISTS signals AS SELECT * FROM signals_v29;

-- INSTEAD OF trigger for inserts
CREATE TRIGGER IF NOT EXISTS signals_insert
INSTEAD OF INSERT ON signals
BEGIN
  INSERT INTO signals_v29 (
    id, source, source_id, sentiment, signal_type, rule_triggered, severity, title,
    client_id, brand_id, engagement_id, summary, payload, evidence, analysis_provider,
    dismissed_at, dismissed_by, first_seen_at, last_seen_at, observed_at, ingested_at, cleared_at, created_at, updated_at
  ) VALUES (
    NEW.id, NEW.source, NEW.source_id, NEW.sentiment, NEW.signal_type, NEW.rule_triggered, NEW.severity, NEW.title,
    NEW.client_id, NEW.brand_id, NEW.engagement_id, NEW.summary, NEW.payload, NEW.evidence, NEW.analysis_provider,
    NEW.dismissed_at, NEW.dismissed_by, NEW.first_seen_at, NEW.last_seen_at, NEW.observed_at, NEW.ingested_at, NEW.cleared_at, NEW.created_at, NEW.updated_at
  );
END;

-- INSTEAD OF trigger for updates
CREATE TRIGGER IF NOT EXISTS signals_update
INSTEAD OF UPDATE ON signals
BEGIN
  UPDATE signals_v29 SET
    source = NEW.source, source_id = NEW.source_id,
    sentiment = NEW.sentiment, signal_type = NEW.signal_type, rule_triggered = NEW.rule_triggered, severity = NEW.severity, title = NEW.title,
    client_id = NEW.client_id, brand_id = NEW.brand_id, engagement_id = NEW.engagement_id,
    summary = NEW.summary, payload = NEW.payload, evidence = NEW.evidence, analysis_provider = NEW.analysis_provider,
    dismissed_at = NEW.dismissed_at, dismissed_by = NEW.dismissed_by,
    first_seen_at = NEW.first_seen_at, last_seen_at = NEW.last_seen_at, observed_at = NEW.observed_at, ingested_at = NEW.ingested_at, cleared_at = NEW.cleared_at,
    updated_at = NEW.updated_at
  WHERE id = OLD.id;
END;

-- INSTEAD OF trigger for deletes
CREATE TRIGGER IF NOT EXISTS signals_delete
INSTEAD OF DELETE ON signals
BEGIN
  DELETE FROM signals_v29 WHERE id = OLD.id;
END;
