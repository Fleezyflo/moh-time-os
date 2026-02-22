# Brief 9: COLLECTOR_SUPREMACY
> **Objective:** Max out every data source, expand DB schema to capture all available API data, add collector resilience.
>
> **Why now:** Collectors currently pull 20-40% of available API data. The DB schema maps only what was initially needed. Before building intelligence layers (Brief 11), the foundation must be complete — every field, every relationship, every signal available for future expansion.

## Scope

### What This Brief Does
1. **Asana collector expansion** — custom fields, subtasks, sections, stories, portfolios, goals, dependencies, attachments
2. **Gmail collector expansion** — attachments metadata, thread participants, Cc/Bcc, labels, read/starred/importance flags
3. **Calendar collector expansion** — attendee responses, video call links, recurrence rules, focus time, OOO events, multiple calendars, organizer field
4. **Chat collector expansion** — reactions, attachments, threading depth, space metadata, membership
5. **Xero collector expansion** — line items, tax breakdown, contact details, credit notes, bills, bank transactions, reports
6. **Schema expansion** — new tables and columns to store all expanded data
7. **Collector resilience** — retry with exponential backoff, circuit breakers, rate limiting, partial success handling

### What This Brief Does NOT Do
- Build new intelligence on expanded data (Brief 11)
- Create UI for new data (Brief 12)
- Wire autonomous scheduling (Brief 10)

## Dependencies
- Brief 8 (USER_READINESS) complete — daemon operational, snapshot pipeline working

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Schema Expansion | CS-1.1: New tables + columns for all collector expansions |
| 2 | Collector Resilience | CS-2.1: Base collector retry/backoff/circuit breaker infrastructure |
| 3 | Asana Deep Pull | CS-3.1: Expand Asana collector to ~90% API coverage |
| 4 | Communication Sources | CS-4.1: Gmail expansion, CS-4.2: Chat expansion |
| 5 | Time & Finance | CS-5.1: Calendar expansion, CS-5.2: Xero expansion |
| 6 | Validation | CS-6.1: Full coverage audit + integration test |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | CS-1.1 | Expand DB Schema for Full API Coverage | PENDING |
| 2 | CS-2.1 | Build Collector Resilience Infrastructure | PENDING |
| 3 | CS-3.1 | Asana Collector Deep Pull | PENDING |
| 4 | CS-4.1 | Gmail Collector Expansion | PENDING |
| 5 | CS-4.2 | Google Chat Collector Expansion | PENDING |
| 6 | CS-5.1 | Calendar Collector Expansion | PENDING |
| 7 | CS-5.2 | Xero Collector Expansion | PENDING |
| 8 | CS-6.1 | Collector Coverage Audit & Validation | PENDING |

## Success Criteria
- Every collector pulls ≥85% of available API data
- All new data stored in properly typed schema columns
- Retry/backoff on every collector — zero silent failures
- Circuit breakers prevent cascade failures
- Full coverage audit passes with documented field mapping
