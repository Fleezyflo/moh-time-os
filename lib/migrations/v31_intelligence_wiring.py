"""
Intelligence Wiring Migration (v31)

Creates tables for persisting intelligence outputs:
- pattern_snapshots: Detected patterns with evidence per cycle
- cost_snapshots: Cost-to-serve computations per entity/portfolio
- intelligence_events: Event hooks for downstream consumers (Brief 17 IW-4.1)

signal_state already exists (created by signal detection system).

Run: python -m lib.migrations.v31_intelligence_wiring
"""

import logging
import sqlite3
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)

SCHEMA = """
-- Pattern snapshots: persist every detected pattern per cycle
CREATE TABLE IF NOT EXISTS pattern_snapshots (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    pattern_id TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium',
    entities_involved TEXT NOT NULL,   -- JSON array of {type, id, name, role_in_pattern}
    evidence TEXT NOT NULL,            -- JSON: metrics, narrative, signals
    cycle_id TEXT                      -- Links to specific daemon cycle run
);

CREATE INDEX IF NOT EXISTS idx_pattern_snap_time
ON pattern_snapshots(detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_snap_pattern
ON pattern_snapshots(pattern_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_snap_cycle
ON pattern_snapshots(cycle_id);

-- Cost snapshots: persist cost-to-serve per entity per cycle
CREATE TABLE IF NOT EXISTS cost_snapshots (
    id TEXT PRIMARY KEY,
    computed_at TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,       -- 'client' | 'project' | 'portfolio'
    entity_id TEXT,                    -- NULL for portfolio snapshots
    effort_score REAL,
    efficiency_ratio REAL,
    profitability_band TEXT,
    cost_drivers TEXT,                 -- JSON array of driver strings
    data TEXT NOT NULL,                -- Full JSON of CostProfile.to_dict()
    cycle_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_cost_snap_time
ON cost_snapshots(computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_cost_snap_entity
ON cost_snapshots(entity_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_cost_snap_type
ON cost_snapshots(snapshot_type, computed_at DESC);

-- Intelligence events: downstream consumer hooks
CREATE TABLE IF NOT EXISTS intelligence_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,          -- 'signal_fired' | 'signal_cleared' | 'signal_escalated'
                                      -- 'pattern_detected' | 'pattern_resolved'
                                      -- 'compound_risk_detected' | 'health_threshold_crossed'
    severity TEXT NOT NULL,            -- 'critical' | 'warning' | 'watch' | 'info'
    entity_type TEXT,                  -- 'client' | 'project' | 'person' | 'portfolio'
    entity_id TEXT,
    event_data TEXT NOT NULL,          -- JSON payload with event details
    source_module TEXT,                -- 'signals' | 'patterns' | 'correlation' | 'cost'
    created_at TEXT NOT NULL,
    consumed_at TEXT,                  -- Set when a downstream consumer processes the event
    consumer TEXT                      -- Which consumer processed it
);

CREATE INDEX IF NOT EXISTS idx_intel_events_unconsumed
ON intelligence_events(consumed_at, created_at DESC)
WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_intel_events_entity
ON intelligence_events(entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intel_events_type
ON intelligence_events(event_type, created_at DESC);

-- Archive table for consumed events (cleanup after 30 days)
CREATE TABLE IF NOT EXISTS intelligence_events_archive (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,
    source_module TEXT,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    consumer TEXT,
    archived_at TEXT NOT NULL
);
"""


def run_migration(db_path: Path | None = None) -> dict:
    """
    Run the intelligence wiring migration.

    Creates pattern_snapshots, cost_snapshots, and intelligence_events tables.
    Safe to run multiple times (IF NOT EXISTS).
    """
    db = db_path or paths.db_path()
    result = {"tables_created": [], "errors": []}

    try:
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA journal_mode=WAL")

        # Get existing tables before migration
        existing = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        # Execute schema
        conn.executescript(SCHEMA)

        # Check what was created
        after = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        new_tables = after - existing
        result["tables_created"] = sorted(new_tables)

        conn.close()
        logger.info("v31 migration complete: created %s", result["tables_created"])

    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error("v31 migration failed: %s", e)
        result["errors"].append(str(e))

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_migration()
    print(f"Migration result: {result}")
