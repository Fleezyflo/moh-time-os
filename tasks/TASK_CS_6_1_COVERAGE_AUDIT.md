# CS-6.1: Collector Coverage Audit & Validation

## Objective
Run every expanded collector against live APIs, verify all new data lands correctly in the DB, produce a coverage report documenting field-by-field mapping.

## Context
After CS-1.1 through CS-5.2, every collector should be pulling ≥85% of available API data into properly typed schema columns. This task validates that claim with evidence.

## Implementation

### Coverage Report Structure
For each collector, produce:
```
COLLECTOR: Asana
API Coverage: 92% (46/50 available fields)
Tables Written: projects, tasks, asana_custom_fields, asana_subtasks,
                asana_sections, asana_stories, asana_task_dependencies,
                asana_portfolios, asana_goals, asana_attachments
Row Counts: tasks=1,247  subtasks=3,891  sections=89  stories=12,450 ...
Missing Fields: [list any intentionally skipped fields with rationale]
Errors: 0 fatal, 2 retried (rate limit), 0 circuit breaks
```

### Validation Steps

1. **Schema Integrity** — Every new table exists, all columns present with correct types
2. **Row Count Sanity** — Each new table has >0 rows after a full sync
3. **Foreign Key Validity** — All FK references resolve to existing parent rows
4. **Data Quality Spot Checks**:
   - Sample 5 Asana tasks → verify custom fields, subtasks, sections match Asana UI
   - Sample 5 Gmail threads → verify participants, attachments, labels match Gmail UI
   - Sample 5 Calendar events → verify attendees, recurrence, conference_url match Calendar UI
   - Sample 5 Chat messages → verify reactions, threading matches Chat UI
   - Sample 5 Xero invoices → verify line items, tax amounts match Xero UI
5. **Resilience Verification** — Confirm CollectionResult logs show retry/backoff activity
6. **Incremental Sync** — Run collector twice, verify second run processes fewer items

### Coverage Score Calculation
```python
coverage_score = (fields_collected / fields_available_in_api) * 100
# Target: ≥85% per collector
# Document any intentionally skipped fields with rationale
```

## Deliverables
- [ ] Coverage report for all 5 collectors (Asana, Gmail, Calendar, Chat, Xero)
- [ ] All collectors achieve ≥85% coverage score
- [ ] Zero data integrity errors (broken FKs, null required fields)
- [ ] Resilience layer activated — retry/backoff logs present
- [ ] Incremental sync reduces API calls on second run
- [ ] Field mapping document: API field → DB column for every collected field

## Files Modified
- New: `scripts/collector_coverage_audit.py` or run as part of existing validation infrastructure

## Estimated Effort
Medium — mostly running collectors + building verification queries
