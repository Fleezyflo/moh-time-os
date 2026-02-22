# DG-2.1: Data Export API

## Objective
Bulk export endpoints for all major entities. JSON and CSV formats. Streaming for large datasets. Field-level filtering respects data classification.

## Context
No way to get data out of the system except raw SQLite queries. Need programmatic export for compliance (subject access requests), analytics, and backup verification.

## Implementation

### Export Entities
| Entity | Source Tables | Default Fields | Restricted Fields |
|--------|-------------|----------------|-------------------|
| clients | client health, invoices, tasks | name, health_score, revenue | email bodies, financial details |
| team_members | capacity, tasks, calendar | name, utilization, task_count | email, calendar details |
| communications | communications, gmail_* | date, from, subject, thread_id | body, attachments |
| tasks | tasks, asana_* | name, project, status, assignee | custom_fields, notes |
| invoices | invoices, xero_* | number, client, amount, status | line_items, payment_details |
| calendar_events | calendar_events, calendar_* | summary, start, end, type | attendees, description, conference_url |
| patterns | patterns, signals | type, severity, entity, detected_at | signals detail |
| actions | actions, audit | type, status, proposed_at, result | payload details |

### Export Engine
```python
class DataExporter:
    def export_entity(
        self,
        entity_type: str,
        format: str = "json",  # "json" or "csv"
        filters: dict = None,  # {field: value} filters
        date_from: str = None,
        date_to: str = None,
        include_restricted: bool = False,  # requires admin role
        stream: bool = False,
    ) -> Iterator[dict] | bytes:
        """Export entity data with classification-aware field filtering."""

    def export_subject_data(self, identifier: str) -> dict:
        """Export ALL data related to a person/entity across all tables."""
```

### API Endpoints
```
GET /api/v1/export/{entity_type}?format=json&from=2025-01-01&to=2025-12-31
GET /api/v1/export/{entity_type}?format=csv&include_restricted=true  (admin only)
GET /api/v1/export/{entity_type}/count  — row count without downloading
```

### Streaming for Large Exports
```python
from fastapi.responses import StreamingResponse

@router.get("/api/v1/export/{entity_type}")
async def export_data(entity_type: str, format: str = "json"):
    exporter = DataExporter(db)
    if format == "csv":
        return StreamingResponse(
            exporter.stream_csv(entity_type),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={entity_type}.csv"}
        )
    return StreamingResponse(
        exporter.stream_json(entity_type),
        media_type="application/json"
    )
```

## Validation
- [ ] All 8 entity types exportable
- [ ] JSON and CSV formats produce valid output
- [ ] Restricted fields excluded unless admin + include_restricted=true
- [ ] Date range filtering works
- [ ] Streaming works for >10,000 rows without memory spike
- [ ] Export audit logged (who exported what, when)

## Files Created
- `lib/governance/export.py` — DataExporter with streaming support
- `api/governance_router.py` — export endpoints (shared with other DG tasks)

## Estimated Effort
Medium — ~200 lines, query builders + streaming + format converters
