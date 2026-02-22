# DQ-4.1: Quality Dashboard & Alerts

## Objective

Surface data quality information so Molham can see at a glance which entities have poor coverage and which collectors are failing. Generate signals when data quality degrades.

## Dependencies

- DQ-1.1 (freshness), DQ-2.1 (completeness), DQ-3.1 (confidence)

## Deliverables

### New signals (add to signal catalog in `signals.py`)

1. **`data_source_stale`** (severity: warning)
   - Fires when a collector hasn't synced within its threshold
   - Evidence: source name, last sync time, threshold, hours overdue

2. **`entity_data_sparse`** (severity: watch)
   - Fires when an entity's overall quality score drops below 0.4
   - Evidence: entity details, domain breakdown, gaps

3. **`entity_data_degrading`** (severity: warning)
   - Fires when an entity's quality score drops by >0.2 over 7 days
   - Evidence: entity details, previous quality, current quality, domains that degraded

### API endpoint (via Brief 26 IA router)

#### GET `/api/v3/intelligence/quality/overview`

Returns:
```json
{
  "data": {
    "collector_health": {
      "gmail": { "status": "ok", "last_sync": "...", "items_24h": 45 },
      "asana": { "status": "stale", "last_sync": "...", "hours_overdue": 3 },
      ...
    },
    "entity_quality": {
      "clients": { "avg": 0.72, "below_50pct": 8, "below_30pct": 2 },
      "projects": { "avg": 0.65, "below_50pct": 22, "below_30pct": 5 },
      "persons": { "avg": 0.81, "below_50pct": 3, "below_30pct": 0 }
    },
    "worst_entities": [
      { "entity_type": "client", "entity_id": "...", "name": "...", "quality": 0.22, "gaps": [...] }
    ],
    "active_quality_signals": 5,
    "recommendation": "Calendar sync is 3 hours stale. 8 clients have incomplete data coverage."
  }
}
```

### Integration with daemon

In `_intelligence_phase()`, add a quality sub-step after the existing 5 sub-steps:
```
Sub-step 6: DATA QUALITY
- Run FreshnessTracker.get_stale_sources() → emit signals
- Run DataQualityScorer.score_all() for each entity type → emit sparse/degrading signals
- Record quality metrics in intelligence events for tracking
```

## Validation

- Stale source signal fires when collector misses sync window
- Sparse entity signal fires for entities below 0.4 quality
- Degrading signal fires when quality drops >0.2 over 7 days
- Quality overview endpoint returns accurate collector health
- Worst entities sorted correctly
- Quality sub-step integrates into daemon without breaking existing phase

## Estimated Effort

~200 lines
