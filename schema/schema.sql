-- MOH Time OS canonical store (SQLite) — v0.1
-- Focus: stable IDs, attribution, versioning, dedupe, proposals, change bundles.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Key/value config with versioning (authoritative runtime config)
CREATE TABLE IF NOT EXISTS config_kv (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events_raw (
  id TEXT PRIMARY KEY,
  surface TEXT NOT NULL, -- gmail|calendar|tasks|chat|manual
  source_ref TEXT NOT NULL, -- provider-native id(s)
  captured_at_ms INTEGER NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  lane TEXT,
  project_id TEXT,
  status TEXT NOT NULL,
  urgency TEXT,
  impact TEXT,
  deadline_kind TEXT, -- hard|soft
  deadline_date TEXT, -- YYYY-MM-DD
  effort_min_minutes INTEGER,
  effort_max_minutes INTEGER,
  waiting_for TEXT,
  deps_json TEXT,
  sensitivity_json TEXT,
  recommended_next_action TEXT,
  dedupe_key TEXT NOT NULL UNIQUE,
  conflicts_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  involvement_type TEXT,
  recognizers_json TEXT,
  rules_bundle_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS conflicts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  claims_json TEXT NOT NULL,
  confidence_json TEXT NOT NULL,
  proposed_resolution_json TEXT,
  execution_gated INTEGER NOT NULL DEFAULT 1,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL, -- task_create|task_update|calendar_block_proposal|delegation_packet|alert
  payload_json TEXT NOT NULL,
  attribution_json TEXT NOT NULL,
  assumptions_json TEXT,
  created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS change_bundles (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  mode TEXT NOT NULL, -- propose|execute
  manifest_json TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  applied_at_ms INTEGER,
  rolled_back_at_ms INTEGER
);
