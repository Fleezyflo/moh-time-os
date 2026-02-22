# DQ-1.1: Collector Freshness Tracker

## Objective

Track when each data source was last successfully synced, per entity where applicable. Surface stale data sources as intelligence signals.

## What Exists

- `lib/collectors/orchestrator.py` — runs collectors, tracks run metadata
- `lib/collectors/recorder.py` — event recording
- Collectors store sync cursors (Gmail, Calendar, Chat, Asana, Xero)
- No per-entity freshness tracking exists

## Deliverables

### New table: `data_freshness` (via v33 migration)

```sql
CREATE TABLE IF NOT EXISTS data_freshness (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,          -- 'gmail', 'calendar', 'asana', 'xero', 'chat'
    entity_type TEXT,              -- NULL for source-level, 'client'/'project' for entity-level
    entity_id TEXT,                -- NULL for source-level
    last_sync_at TEXT NOT NULL,    -- ISO timestamp of last successful sync
    items_synced INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'ok', -- 'ok', 'partial', 'failed'
    error_message TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(source, entity_type, entity_id)
);

CREATE INDEX idx_freshness_source ON data_freshness(source);
CREATE INDEX idx_freshness_entity ON data_freshness(entity_type, entity_id);
CREATE INDEX idx_freshness_staleness ON data_freshness(last_sync_at);
```

### New file: `lib/intelligence/data_freshness.py`

```python
class FreshnessTracker:
    """Tracks data source freshness and detects staleness."""

    # Staleness thresholds per source (configurable)
    THRESHOLDS = {
        "gmail": timedelta(hours=1),
        "calendar": timedelta(hours=4),
        "asana": timedelta(hours=2),
        "xero": timedelta(hours=24),  # Xero syncs less frequently
        "chat": timedelta(hours=1),
    }

    def __init__(self, db_path: Path): ...

    def record_sync(self, source: str, entity_type: str = None,
                    entity_id: str = None, items_synced: int = 0,
                    status: str = "ok", error: str = None) -> bool:
        """Record a successful (or failed) sync event."""

    def get_freshness(self, source: str = None) -> list[dict]:
        """Get freshness status for all sources or a specific source."""

    def get_entity_freshness(self, entity_type: str, entity_id: str) -> dict:
        """Get data freshness across all sources for a specific entity.
        Returns: { source: { last_sync_at, age_minutes, stale: bool } }
        """

    def get_stale_sources(self) -> list[dict]:
        """Return all sources that have exceeded their freshness threshold."""

    def get_source_health(self) -> dict:
        """Aggregate: { source: { status, last_sync, items_24h, failure_rate_7d } }"""
```

### Integration with collectors

After each collector run completes (in `orchestrator.py`), call `FreshnessTracker.record_sync()` with the source name, items synced, and status. This is a one-line addition per collector.

### Staleness signals

Register stale data sources as intelligence signals. In `_intelligence_phase()` (autonomous_loop.py), after the main intelligence sub-steps, check for stale sources and emit `data_source_stale` events to `IntelligenceEventStore`.

## Validation

- record_sync persists correctly
- get_freshness returns accurate ages
- get_stale_sources identifies sources past threshold
- Stale source emits intelligence event
- Failed sync recorded with error message
- Entity-level freshness aggregates across sources

## Estimated Effort

~200 lines
