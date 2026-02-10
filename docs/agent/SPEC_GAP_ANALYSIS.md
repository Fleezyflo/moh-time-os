# Spec Gap Analysis — CLIENT-UI-SPEC-v2.9.md

*Systematic audit of spec requirements vs implementation status*

---

## Executive Summary

The spec defines a complete Client UI system. Implementation progress:

**✅ Completed this session:**
- Spec router integrated into server.py at `/api/v2`
- Control Room Inbox frontend page created
- Inbox is now primary route (/)
- 16 spec-compliant API endpoints added

**⚠️ Remaining gaps:**
- Client Index swimlanes need verification
- Client Detail 5-tab structure needs verification
- Recently Active / Cold client drilldowns
- Frontend-backend data flow testing

---

## Section-by-Section Audit

### §0 Definitions & Conventions

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| Timestamp format (24-char UTC) | ✅ | `time_utils.py` | — |
| Timestamp normalization | ✅ | `time_utils.py` | — |
| local_midnight_utc | ✅ | `time_utils.py` | — |
| DST zone rejection | ❓ | Not verified | Need validation |
| Severity ordering | ✅ | `endpoints.py` | — |
| utc_now_iso_ms_z() | ✅ | `time_utils.py` | — |

### §1 Control Room — Inbox (Proposals)

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| **1.1 Purpose** | — | — | — |
| **1.2 Inbox Structure** | ❌ | No dedicated page | Need `/inbox` route + page |
| Header with counts | ⚠️ | `_get_counts()` exists | Need UI component |
| Tabs: Needs Attention/Snoozed/Recently Actioned | ❌ | — | No tab UI |
| **1.3 Inbox Item Types** | ✅ | `inbox_lifecycle.py` | issue/flagged_signal/orphan/ambiguous defined |
| **1.4 Inbox Item Lifecycle** | ✅ | `inbox_lifecycle.py` | States + transitions |
| State machine diagram | ✅ | Code matches | — |
| Snooze timer job | ✅ | `process_snooze_expiry()` | — |
| **1.5 Inbox ↔ Entity Mapping** | ✅ | Implemented | — |
| **1.6 Primary Actions** | ✅ | `inbox_lifecycle.py` | tag/assign/snooze/dismiss/link/create/select |
| **1.7 Tag & Watch** | ✅ | Implemented | — |
| **1.7.1 Assign** | ✅ | Implemented | — |
| **1.8 Dismiss** | ✅ | `suppression.py` | — |
| Suppression key algorithm | ✅ | Implemented | — |
| **1.9 Inbox Counts** | ✅ | `_get_counts()` | — |
| is_unprocessed() | ✅ | Implemented | — |
| **1.10 Read vs Needs Attention** | ✅ | Implemented | — |

**Frontend Gap:** No `Inbox.tsx` page. Current `Snapshot.tsx` is not the Control Room Inbox.

### §2 Client Index Page

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| **2.1 Page Structure** | ⚠️ | `Clients.tsx` exists | May not match spec |
| Three swimlanes (active/recently_active/cold) | ❓ | Need to verify | — |
| **2.2 Active Client Card** | ❓ | Need to verify | — |
| Health score badge | ❓ | — | — |
| AR metrics | ❓ | — | — |
| **2.3 Recently Active Card** | ❓ | — | — |
| **2.4 Cold Client Card** | ❓ | — | — |
| **2.5 Sorting & Filtering** | ❓ | — | — |

### §3 Active Client Detail Page

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| **3.1 Header** | ❓ | `ClientDetail.tsx` | Need to verify |
| **3.2 Tab 1: Overview** | ❓ | — | — |
| Health score prominent | ❓ | — | — |
| Top issues | ❓ | — | — |
| Active engagements | ❓ | — | — |
| **3.3 Tab 2: Engagements** | ❓ | — | — |
| **3.4 Tab 3: Financials** | ❓ | — | — |
| AR aging breakdown | ❓ | — | — |
| Invoice list | ❓ | — | — |
| **3.5 Tab 4: Signals** | ❓ | — | — |
| **3.6 Tab 5: Team** | ❓ | — | — |

### §4 Recently Active Client Drilldown

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| Drilldown page | ❌ | No dedicated route | Need implementation |
| Last 12m vs prev 12m metrics | ❌ | — | — |

### §5 Cold Clients

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| Cold clients view | ❌ | — | Need implementation |
| Lifetime metrics only | ❌ | — | — |

### §6 Canonical Data + Logic Contract

| Requirement | Status | Location | Gap |
|-------------|--------|----------|-----|
| **6.1 Client Status Logic** | ✅ | `endpoints.py` | 90d/270d boundaries |
| **6.2 Finance Metrics** | ⚠️ | Partial | Need verification |
| AR_outstanding | ✅ | — | — |
| AR_overdue | ✅ | — | — |
| ar_overdue_pct | ✅ | — | — |
| **6.3 Task Linking** | ❓ | — | — |
| **6.4 Evidence Rules** | ✅ | `evidence.py` | — |
| **6.5 Issue Lifecycle** | ✅ | `issue_lifecycle.py` | — |
| 10 states | ✅ | Implemented | — |
| resolved never persisted | ✅ | Updated | — |
| regression_watch_until | ✅ | Implemented | — |
| **6.6 Health Score Formula** | ✅ | `health.py` | — |
| Client health | ✅ | Implemented | — |
| Engagement health | ✅ | Implemented | — |
| **6.7 Engagement Lifecycle** | ⚠️ | Partial | 7 states defined? |
| **6.8 Engagement Creation** | ❓ | — | — |
| **6.9 Recently Active Exclusions** | ❓ | — | — |
| **6.10 Xero Linking** | ✅ | `evidence.py` | No deep links |
| **6.11 Signal Source Mapping** | ✅ | Defined | — |
| **6.12 Signals Taxonomy** | ❓ | — | — |
| **6.13 Inbox Items Schema** | ✅ | `migrations/` | — |
| **6.14 Issues Schema** | ✅ | `migrations/` | aggregation_key added |
| **6.14.1 Aggregation Key** | ✅ | `v29_spec_alignment.py` | — |
| **6.15 Signals Schema** | ✅ | `migrations/` | — |
| **6.16 Evidence Meta-Schema** | ✅ | `evidence.py` | — |
| **6.17 Tasks Source Definition** | ❓ | — | — |
| **6.18 Tier Values** | ✅ | Defined | platinum/gold/silver/bronze/none |
| **6.19 Detector Windows** | ✅ | `time_utils.py` | — |

### §7 Minimum API Endpoints

| Endpoint | Status | Location | Gap |
|----------|--------|----------|-----|
| **7.1 GET /api/clients** | ✅ | `endpoints.py` | — |
| **7.2 GET /api/clients/:id** | ✅ | `endpoints.py` | — |
| **7.3 GET /api/clients/:id/snapshot** | ✅ | `endpoints.py` | — |
| **7.4 GET /api/engagements** | ❓ | — | — |
| **7.5 GET /api/clients/:id/invoices** | ✅ | `endpoints.py` | — |
| **7.6 GET /api/issues** | ⚠️ | — | Need verification |
| **7.6 POST /api/issues/:id/transition** | ✅ | `issue_lifecycle.py` | — |
| **7.7 GET /api/signals** | ❓ | — | — |
| **7.8 GET /api/team** | ❓ | — | — |
| **7.9 GET /api/clients/:id (recently_active)** | ⚠️ | — | Include policy |
| **7.10 GET /api/inbox** | ✅ | `endpoints.py` | — |
| **7.10 GET /api/inbox/recent** | ✅ | `endpoints.py` | — |
| **7.10 POST /api/inbox/:id/action** | ✅ | `endpoints.py` | — |
| **7.11 POST /api/engagements/:id/transition** | ❓ | — | — |

---

## Priority Gaps

### P0 — Critical (Blocks Core Functionality)

1. **Control Room Inbox Page** — No frontend route/component
2. **API Server** — Is there a Flask/FastAPI server running these endpoints?
3. **Database Schema** — Are migrations actually applied?

### P1 — High (Core Features Missing)

4. **Client Index swimlanes** — Verify UI matches spec
5. **Client Detail tabs** — Verify 5 tabs per spec
6. **Recently Active drilldown** — Missing page
7. **Cold clients view** — Missing page

### P2 — Medium (Spec Compliance)

8. **Engagement lifecycle** — Verify 7 states
9. **Signals endpoint** — Missing
10. **Team endpoint** — Missing

### P3 — Low (Polish)

11. **UI copy mapping** — Verify labels match spec
12. **Error responses** — Verify error formats

---

## Next Steps

1. **Verify database state** — Are tables created? Run migrations?
2. **Verify API server** — Is there a running server? FastAPI? Flask?
3. **Audit frontend pages** — Do they match spec structure?
4. **Create Control Room Inbox** — Primary missing page
5. **Systematic implementation** — Section by section

---

*Generated: 2026-02-09*
