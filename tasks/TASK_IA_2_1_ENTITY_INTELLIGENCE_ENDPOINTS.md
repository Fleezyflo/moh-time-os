# IA-2.1: Entity Intelligence Endpoints

## Objective

Expose per-entity intelligence via REST endpoints. A client page, project page, or person page in the UI should be able to fetch a single JSON blob containing everything the intelligence layer knows about that entity.

## Dependencies

- IA-1.1 (router + envelope)
- Brief 18 ID-3.1 (entity profiles must exist)
- Brief 17 IW-1.1/IW-2.1 (persistence + health unifier)

## Endpoints

### GET `/api/v3/intelligence/entity/{entity_type}/{entity_id}/profile`

Returns the full `EntityIntelligenceProfile` (from ID-3.1):
- Health score + classification + trend direction
- Active signals with severity and age
- Active patterns with direction (new/persistent/resolving/worsening)
- Trajectory projection (30-day forward)
- Cost profile (effort, efficiency, profitability band)
- Compound risks
- Narrative summary
- Attention level (urgent/elevated/normal/stable)
- Recommended actions

**Response shape:**
```json
{
  "data": {
    "entity_type": "client",
    "entity_id": "abc123",
    "entity_name": "Client X",
    "health": {
      "score": 72,
      "classification": "healthy",
      "trend": "declining",
      "trend_velocity": -2.3
    },
    "signals": [
      { "signal_id": "sig_overdue_tasks", "severity": "warning", "detected_at": "...", "age_days": 3 }
    ],
    "patterns": [
      { "pattern_id": "pat_engagement_drop", "severity": "operational", "direction": "worsening", "confidence": 0.82 }
    ],
    "trajectory": {
      "projected_score_30d": 65,
      "confidence": 0.71,
      "direction": "declining"
    },
    "cost": {
      "effort_score": 45,
      "efficiency_ratio": 0.83,
      "profitability_band": "healthy"
    },
    "attention_level": "elevated",
    "narrative": "Client X shows declining engagement with 3 overdue tasks and a worsening engagement pattern...",
    "recommended_actions": ["Review overdue tasks", "Schedule check-in call"]
  },
  "meta": { ... }
}
```

### GET `/api/v3/intelligence/entity/{entity_type}/{entity_id}/health`

Lightweight endpoint — just the health score, classification, and trend. For list views and cards that don't need full profiles.

### GET `/api/v3/intelligence/entity/{entity_type}/{entity_id}/health/history`

Query params: `days` (default 30), `granularity` (daily/weekly)

Returns time series of health scores for charting.

### GET `/api/v3/intelligence/entity/{entity_type}/{entity_id}/signals`

Query params: `severity` (filter), `active_only` (default true)

Returns all signals for this entity.

### GET `/api/v3/intelligence/entity/{entity_type}/{entity_id}/timeline`

Returns a chronological feed of events: score changes, signals raised/cleared, patterns detected, actions taken. Useful for entity detail pages.

## Data Sources (Read-Only)

| Endpoint | Reads From |
|----------|-----------|
| /profile | `score_history`, `signal_state`, `pattern_snapshots`, `cost_snapshots` + live computation via `build_entity_profile()` |
| /health | `score_history` via `HealthUnifier.get_latest_health()` |
| /health/history | `score_history` via `HealthUnifier.get_health_history()` |
| /signals | `signal_state` via `get_active_signals()` |
| /timeline | `intelligence_events` via `IntelligenceEventStore.get_recent_events()` |

**Note on /profile:** This is the ONE endpoint that may do light computation (assembling the profile from persisted parts). It should NOT re-run scoring/signals/patterns — only read persisted results and assemble. Target: <100ms response time.

## Validation

- Profile returns all sections populated for a real entity
- Profile returns 404 for unknown entity
- Health history returns correct time series shape
- Signal filtering by severity works
- Timeline returns chronological events
- Response times: /health <20ms, /profile <100ms, /history <50ms

## Estimated Effort

~400 lines
