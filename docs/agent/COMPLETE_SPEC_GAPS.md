# Complete Spec Gap Analysis — CLIENT-UI-SPEC-v2.9.md

*Revised: 2026-02-09T05:35Z — **100% Complete***

---

## Summary

| Category | Code | Migration | Status |
|----------|------|-----------|--------|
| §0 Conventions | ✅ | ✅ | Complete |
| §1 Inbox | ✅ | ✅ | Complete |
| §2 Client Index | ✅ | ✅ | Complete |
| §3 Client Detail | ✅ | ✅ | Complete |
| §4 Recently Active | ✅ | ✅ | Complete |
| §5 Cold Clients | ✅ | ✅ | Complete |
| §6 Data Contracts | ✅ | ✅ | Complete |
| §7 API Endpoints | ✅ | ✅ | Complete |

**All migrations executed. All test vectors pass.**

---

## §0. Definitions & Conventions

### §0.1 Global Conventions

| Requirement | Status | Location |
|-------------|--------|----------|
| Timestamp format (24-char UTC) | ✅ | `time_utils.py` |
| Timestamp normalization | ✅ | `time_utils.py:normalize_timestamp()` |
| Storage test vectors | ✅ | `time_utils.py:STORAGE_TEST_VECTORS` |
| Normalization test vectors | ✅ | `time_utils.py:NORMALIZATION_TEST_VECTORS` |
| DST zone rejection | ✅ | `time_utils.py:validate_org_timezone()` |
| Per-request today_local | ✅ | `time_utils.py:RequestContext` |
| `org.base_currency` setting | ✅ | `org_settings.py` + `org_settings` table |
| `org.timezone` setting | ✅ | `org_settings.py` + `org_settings` table |
| Currency validation | ✅ | `org_settings.py:validate_invoice_currency()` |
| Multi-currency flagging | ✅ | `org_settings.py:create_currency_mismatch_signal()` |
| `finance_calc_version` | ✅ | `org_settings.py` + `org_settings` table |
| Severity ordering | ✅ | `endpoints.py:SEVERITY_ORDER` |

### §0.3-§0.4 UI Labels & Actions

| Requirement | Status | Location |
|-------------|--------|----------|
| Issue state → UI label | ✅ | `constants/labels.ts` |
| Inbox state → UI label | ✅ | `constants/labels.ts` |
| Severity → UI label | ✅ | `constants/labels.ts` |
| Button label → action mapping | ✅ | `constants/labels.ts` |

### §0.5 Attention Age

| Requirement | Status | Location |
|-------------|--------|----------|
| `attention_age_start_at` | ✅ | `endpoints.py` |
| `is_unprocessed()` | ✅ | `endpoints.py` |

---

## §1. Control Room — Inbox

| Requirement | Status | Location |
|-------------|--------|----------|
| Inbox as primary page | ✅ | Route `/` |
| Header with counts | ✅ | `Inbox.tsx` |
| Three tabs | ✅ | `Inbox.tsx` |
| Filters: type, severity, client | ✅ | `Inbox.tsx` |
| Sort options | ✅ | `Inbox.tsx` |
| `by_severity` counts | ✅ | `endpoints.py`, `Inbox.tsx` |
| `by_type` counts | ✅ | `endpoints.py`, `Inbox.tsx` |
| Snooze duration picker | ✅ | `Inbox.tsx:InboxDrawer` |
| All inbox lifecycle states | ✅ | `inbox_lifecycle.py` |
| All inbox actions | ✅ | `inbox_lifecycle.py` |

---

## §2. Client Index Page

| Requirement | Status | Location |
|-------------|--------|----------|
| Three swimlanes | ✅ | `ClientIndex.tsx` |
| Active client card | ✅ | `ClientIndex.tsx:ActiveClientCard` |
| Recently active card | ✅ | `ClientIndex.tsx:RecentlyActiveCard` |
| Cold client card | ✅ | `ClientIndex.tsx:ColdClientCard` |
| Tier/issue/AR filters | ✅ | `ClientIndex.tsx` |

---

## §3. Client Detail Page

| Requirement | Status | Location |
|-------------|--------|----------|
| 5 tabs | ✅ | `ClientDetailSpec.tsx` |
| Tab 1: Overview | ✅ | `OverviewTab` |
| Tab 2: Engagements | ✅ | `EngagementsTab` |
| Tab 3: Financials | ✅ | `FinancialsTab` |
| Tab 4: Signals | ✅ | `SignalsTab` |
| Tab 5: Team | ✅ | `TeamTab` |

---

## §4. Recently Active Drilldown

| Requirement | Status | Location |
|-------------|--------|----------|
| Dedicated drilldown page | ✅ | `RecentlyActiveDrilldown.tsx` |
| Financial comparison | ✅ | — |
| Engagement history | ✅ | — |
| Invoice history | ✅ | — |

---

## §5. Cold Clients

| Requirement | Status | Location |
|-------------|--------|----------|
| Dedicated cold page | ✅ | `ColdClients.tsx` |
| Lifetime metrics only | ✅ | — |
| Tier filter and sort | ✅ | — |

---

## §6. Data Contracts

### §6.1-§6.6 Core Logic

| Requirement | Status | Location |
|-------------|--------|----------|
| Client status logic | ✅ | `endpoints.py` |
| Finance metrics | ✅ | `endpoints.py`, `health.py` |
| Evidence validation | ✅ | `evidence.py` |
| Issue lifecycle (10 states) | ✅ | `issue_lifecycle.py` |
| Health scoring | ✅ | `health.py` |

### §6.7 Engagement Lifecycle

| Requirement | Status | Location |
|-------------|--------|----------|
| 7 states defined | ✅ | `engagement_lifecycle.py:EngagementState` |
| State machine transitions | ✅ | `engagement_lifecycle.py:VALID_TRANSITIONS` |
| Heuristic triggers | ✅ | `engagement_lifecycle.py:HEURISTIC_TRIGGERS` |
| Available actions by state | ✅ | `engagement_lifecycle.py:AVAILABLE_ACTIONS` |
| Transition audit trail | ✅ | `engagement_transitions` table |
| 30-day timeout check | ✅ | `engagement_lifecycle.py:check_thirty_day_timeout()` |
| `engagements` table | ✅ | Created with 7-state CHECK constraint |
| `engagement_transitions` table | ✅ | Created with audit fields |

### §6.13-§6.19 Schema & Windows

| Requirement | Status | Location |
|-------------|--------|----------|
| Inbox items schema | ✅ | Migrations |
| Issues schema + aggregation_key | ✅ | `v29_spec_alignment.py` |
| Evidence meta-schema | ✅ | `evidence.py` |
| Detector window boundaries | ✅ | `time_utils.py` |

---

## §7. API Endpoints

| Endpoint | Status | Location |
|----------|--------|----------|
| GET /api/clients | ✅ | `spec_router.py` |
| GET /api/clients/:id | ✅ | `spec_router.py` |
| GET /api/clients/:id/snapshot | ✅ | `spec_router.py` |
| GET /api/clients/:id/signals | ✅ | `spec_router.py` |
| GET /api/clients/:id/team | ✅ | `spec_router.py` |
| GET /api/engagements | ✅ | `spec_router.py` |
| GET /api/engagements/:id | ✅ | `spec_router.py` |
| POST /api/engagements/:id/transition | ✅ | `spec_router.py` |
| GET /api/issues | ✅ | `spec_router.py` |
| GET /api/issues/:id | ✅ | `spec_router.py` |
| POST /api/issues/:id/transition | ✅ | `spec_router.py` |
| GET /api/inbox | ✅ | `spec_router.py` |
| GET /api/inbox/recent | ✅ | `spec_router.py` |
| GET /api/inbox/counts | ✅ | `spec_router.py` |
| POST /api/inbox/:id/action | ✅ | `spec_router.py` |
| POST /api/inbox/:id/read | ✅ | `spec_router.py` |
| POST /api/jobs/snooze-expiry | ✅ | `spec_router.py` |
| POST /api/jobs/regression-watch | ✅ | `spec_router.py` |
| GET /api/health | ✅ | `spec_router.py` |

---

## Implementation Files

### Backend

| Module | Purpose | Status |
|--------|---------|--------|
| `time_utils.py` | Timestamps, DST rejection, RequestContext | ✅ |
| `org_settings.py` | Org timezone, currency, finance_calc_version | ✅ |
| `inbox_lifecycle.py` | 4 states, 7 actions, snooze timer | ✅ |
| `issue_lifecycle.py` | 10 states, full transitions, regression watch | ✅ |
| `engagement_lifecycle.py` | 7 states, transitions, audit trail | ✅ |
| `suppression.py` | Dismiss rules, expiry | ✅ |
| `evidence.py` | Validation, link rendering | ✅ |
| `health.py` | Client + engagement health formulas | ✅ |
| `endpoints.py` | All endpoint implementations | ✅ |
| `spec_router.py` | FastAPI router with all endpoints | ✅ |

### Frontend

| Page | Route | Status |
|------|-------|--------|
| `Inbox.tsx` | `/` | ✅ |
| `ClientIndex.tsx` | `/clients` | ✅ |
| `ClientDetailSpec.tsx` | `/clients/:id` | ✅ |
| `RecentlyActiveDrilldown.tsx` | `/clients/:id/recently-active` | ✅ |
| `ColdClients.tsx` | `/clients/cold` | ✅ |
| `constants/labels.ts` | — | ✅ |

### Migrations

| File | Status | Tables Created |
|------|--------|----------------|
| `v29_spec_alignment.py` | ✅ Applied | issues aggregation_key |
| `v29_inbox_schema.py` | ✅ Applied | inbox_items, inbox_suppression_rules |
| `v29_engagement_lifecycle.py` | ✅ Applied | engagements, engagement_transitions |
| `v29_org_settings.py` | ✅ Applied | org_settings |

---

## Verification Results

```
✅ Frontend build passes (408KB bundle)
✅ All Python modules import successfully
✅ Storage test vectors: PASS
✅ Normalization test vectors: PASS
✅ All v29 database tables created
✅ Org settings initialized (Asia/Dubai, AED, v1)
✅ Client endpoints return data (9 active, 151 cold)
✅ Inbox counts include by_severity and by_type
✅ Issue lifecycle has 10 states with correct actions
✅ Engagement lifecycle has 7 states
```

### Database Tables

| Table | Status | Records |
|-------|--------|---------|
| `issues_v29` | ✅ | Spec-aligned |
| `inbox_items_v29` | ✅ | Spec-aligned |
| `signals_v29` | ✅ | Spec-aligned |
| `engagements` | ✅ | 7-state lifecycle |
| `engagement_transitions` | ✅ | Audit trail |
| `org_settings` | ✅ | Initialized |

---

*Completed: 2026-02-09T05:45Z*
