# IA-3.1: Portfolio & Aggregate Endpoints

## Objective

Expose portfolio-level intelligence — the "agency control room" data. These endpoints power the main dashboard landing page showing overall health, top concerns, and aggregate metrics.

## Dependencies

- IA-1.1 (router + envelope)
- Brief 17 (persistence layer)
- Brief 18 ID-3.1 (entity profiles for top-entities lists)

## Endpoints

### GET `/api/v3/intelligence/portfolio/dashboard`

The single endpoint for the main dashboard. Returns everything the control room needs in one call.

```json
{
  "data": {
    "overall_health": {
      "score": 68,
      "classification": "stable",
      "trend": "declining",
      "previous_score": 72,
      "change": -4
    },
    "entity_counts": {
      "clients": { "total": 160, "critical": 3, "at_risk": 12, "stable": 89, "healthy": 56 },
      "projects": { "total": 354, "critical": 5, "at_risk": 18, "stable": 201, "healthy": 130 },
      "persons": { "total": 71, "overloaded": 4, "underutilized": 8, "balanced": 59 }
    },
    "top_concerns": [
      { "entity_type": "client", "entity_id": "...", "entity_name": "...", "score": 28, "primary_signal": "sig_overdue_tasks", "attention_level": "urgent" }
    ],
    "active_signals_summary": {
      "critical": 4, "warning": 18, "watch": 42,
      "new_since_yesterday": 3, "cleared_since_yesterday": 7
    },
    "active_patterns_summary": {
      "structural": 2, "operational": 8, "informational": 15,
      "worsening": 3, "new": 5, "resolving": 4
    },
    "top_proposals": [
      { "proposal_type": "client_risk", "urgency": "immediate", "summary": "...", "entity_name": "..." }
    ],
    "financial_snapshot": {
      "total_ar": 245000,
      "overdue_ar": 38000,
      "avg_collection_days": 42,
      "portfolio_profitability": "healthy"
    }
  },
  "meta": { ... }
}
```

### GET `/api/v3/intelligence/portfolio/entities`

Query params: `entity_type` (required), `sort_by` (score|name|trend), `classification` (filter), `limit` (default 50), `offset`

Paginated list of entities with health summaries. Powers entity list views.

### GET `/api/v3/intelligence/portfolio/health/history`

Query params: `days` (default 30), `granularity` (daily/weekly)

Portfolio-level health trend for the top-line chart.

### GET `/api/v3/intelligence/portfolio/proposals`

Query params: `urgency` (immediate/this_week/monitor), `type` (filter), `limit` (default 10)

Ranked proposals with priority scores. Powers the "action items" panel.

## Data Sources

| Endpoint | Reads From |
|----------|-----------|
| /dashboard | `score_history` (latest per entity), `signal_state`, `pattern_snapshots`, proposals (live ranked), `invoices` |
| /entities | `score_history` via `HealthUnifier.get_all_latest_health()` |
| /health/history | `score_history` aggregated by day |
| /proposals | `generate_proposals_from_live_data()` → `rank_proposals()` |

**Note on /dashboard:** This assembles from multiple persisted sources. No heavy computation. The daemon pre-computes everything. Target: <200ms.

**Note on /proposals:** Proposal generation reads persisted signals and patterns, then applies ranking. This is the most computation-heavy read endpoint. Target: <500ms. Consider caching with 5-minute TTL.

## Validation

- Dashboard returns all sections populated
- Entity list pagination works (offset + limit)
- Sorting by score returns correct order
- Classification filtering works
- Proposals ranked by priority (highest first)
- Portfolio health history matches sum of entity histories
- Response times within targets

## Estimated Effort

~300 lines
