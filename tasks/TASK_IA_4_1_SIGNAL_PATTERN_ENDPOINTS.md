# IA-4.1: Signal & Pattern Query Endpoints

## Objective

Expose signal state and pattern detection results through queryable endpoints. Powers the signals panel, pattern analysis views, and notification routing.

## Dependencies

- IA-1.1 (router + envelope)
- Brief 17 IW-1.1 (signal_state table, pattern_snapshots table)
- Brief 18 ID-5.1 (pattern trending — direction classification)

## Endpoints

### Signals

#### GET `/api/v3/intelligence/signals`
Active signals across all entities.
Query params: `severity` (critical/warning/watch), `entity_type`, `category` (threshold/trend/anomaly/compound), `state` (new/ongoing/escalated), `limit`, `offset`

#### GET `/api/v3/intelligence/signals/{signal_key}`
Single signal detail with full evidence, history, and related patterns.

#### GET `/api/v3/intelligence/signals/summary`
Aggregate signal counts by severity, category, entity_type. Powers the signal health bar in the dashboard.

#### GET `/api/v3/intelligence/signals/history`
Query params: `days` (default 7), `entity_type`, `entity_id`
Signal state transitions (raised, escalated, cleared) over time. Powers the signal activity chart.

#### POST `/api/v3/intelligence/signals/{signal_key}/acknowledge`
Mark a signal as acknowledged. Records in signal_state. Used by the UI when Molham explicitly acknowledges a signal.

### Patterns

#### GET `/api/v3/intelligence/patterns`
All detected patterns with direction classification.
Query params: `severity` (structural/operational/informational), `type` (concentration/cascade/degradation/drift/correlation), `direction` (new/persistent/resolving/worsening), `limit`, `offset`

#### GET `/api/v3/intelligence/patterns/{pattern_id}`
Single pattern detail with evidence chain, affected entities, confidence score, and trend history.

#### GET `/api/v3/intelligence/patterns/summary`
Aggregate pattern counts by type, severity, direction. Powers the pattern overview widget.

#### GET `/api/v3/intelligence/patterns/{pattern_id}/history`
Query params: `cycles` (default 10)
How this pattern has evolved over recent daemon cycles — confidence changes, entity set changes, severity shifts.

## Data Sources

| Endpoint | Source |
|----------|--------|
| /signals | `signal_state` table via `get_active_signals()` |
| /signals/{key} | `signal_state` + `intelligence_events` for history |
| /signals/summary | `get_signal_summary()` |
| /signals/history | `signal_state` with `detected_at`/`cleared_at` range queries |
| /signals/{key}/acknowledge | `acknowledge_signal()` |
| /patterns | `pattern_snapshots` + `PatternTrendAnalyzer` (from ID-5.1) |
| /patterns/{id} | `pattern_snapshots` + evidence from snapshot JSON |
| /patterns/summary | Aggregate query on `pattern_snapshots` |
| /patterns/{id}/history | `pattern_snapshots` filtered by pattern_id ordered by cycle_id |

## Response Shapes

Signal list item:
```json
{
  "signal_key": "sig_client_overdue_tasks::client_abc",
  "signal_type": "client_overdue_tasks",
  "entity_type": "client",
  "entity_id": "abc",
  "entity_name": "Client X",
  "severity": "warning",
  "category": "threshold",
  "state": "ongoing",
  "detected_at": "2026-02-19T08:30:00Z",
  "age_days": 2,
  "evidence": { "overdue_count": 7, "threshold": 5 },
  "acknowledged": false
}
```

Pattern list item:
```json
{
  "pattern_id": "revenue_concentration",
  "pattern_type": "concentration",
  "severity": "structural",
  "direction": "persistent",
  "confidence": 0.87,
  "entities_involved": ["client_a", "client_b", "client_c"],
  "summary": "Top 3 clients account for 52% of revenue",
  "detected_at": "2026-02-21T06:00:00Z",
  "cycle_id": "cycle_2026-02-21_06"
}
```

## Validation

- Signal filtering by severity, entity_type, category all work
- Pattern direction classification matches PatternTrendAnalyzer output
- Acknowledge updates signal_state correctly
- History endpoints return correct chronological order
- Summary aggregations match detail counts
- Empty results return valid empty arrays, not errors

## Estimated Effort

~350 lines
