-- Migration 005: inbox_suppression_rules_v29 (primary table)
-- Spec Section 1.8 - using v29 naming for API compatibility

CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
  id TEXT PRIMARY KEY,
  suppression_key TEXT NOT NULL UNIQUE,
  item_type TEXT NOT NULL,
  scope_client_id TEXT,
  scope_engagement_id TEXT,
  scope_source TEXT,
  scope_rule TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_suppression_rules_v29_key ON inbox_suppression_rules_v29(suppression_key);
CREATE INDEX IF NOT EXISTS idx_suppression_rules_v29_expires ON inbox_suppression_rules_v29(expires_at);
CREATE INDEX IF NOT EXISTS idx_suppression_rules_v29_type ON inbox_suppression_rules_v29(item_type);

-- Create inbox_suppression_rules as view for backward compatibility
CREATE VIEW IF NOT EXISTS inbox_suppression_rules AS SELECT * FROM inbox_suppression_rules_v29;

-- INSTEAD OF trigger for inserts
CREATE TRIGGER IF NOT EXISTS inbox_suppression_rules_insert
INSTEAD OF INSERT ON inbox_suppression_rules
BEGIN
  INSERT INTO inbox_suppression_rules_v29 (
    id, suppression_key, item_type, scope_client_id, scope_engagement_id, scope_source, scope_rule,
    created_by, created_at, expires_at, reason
  ) VALUES (
    NEW.id, NEW.suppression_key, NEW.item_type, NEW.scope_client_id, NEW.scope_engagement_id, NEW.scope_source, NEW.scope_rule,
    NEW.created_by, NEW.created_at, COALESCE(NEW.expires_at, '9999-12-31T23:59:59'), NEW.reason
  );
END;

-- INSTEAD OF trigger for updates
CREATE TRIGGER IF NOT EXISTS inbox_suppression_rules_update
INSTEAD OF UPDATE ON inbox_suppression_rules
BEGIN
  UPDATE inbox_suppression_rules_v29 SET
    suppression_key = NEW.suppression_key, item_type = NEW.item_type,
    scope_client_id = NEW.scope_client_id, scope_engagement_id = NEW.scope_engagement_id, scope_source = NEW.scope_source, scope_rule = NEW.scope_rule,
    created_by = NEW.created_by, created_at = NEW.created_at, expires_at = NEW.expires_at, reason = NEW.reason
  WHERE id = OLD.id;
END;

-- INSTEAD OF trigger for deletes
CREATE TRIGGER IF NOT EXISTS inbox_suppression_rules_delete
INSTEAD OF DELETE ON inbox_suppression_rules
BEGIN
  DELETE FROM inbox_suppression_rules_v29 WHERE id = OLD.id;
END;
