# Time OS — Client UI Spec Executive Summary

*For review and critique — 2026-02-07*

---

## 1. Core Entities

### Clients
- **Status:** `active` (invoiced ≤90d) → `recently_active` (91-270d) → `cold` (270d+ or no invoices)
- **Tier:** platinum / gold / silver / bronze / none
- **Health Score:** 0-100, computed from AR overdue + open issues (high/critical only)
- Status is computed, not stored. Boundaries are inclusive (exactly 90d = active).

### Engagements
- Child of Client → Brand
- **Types:** project (time-bound) or retainer (ongoing)
- **States (7):** planned → active → blocked/paused → delivering → delivered → completed
- Health score gated: requires 90%+ task linking coverage

### Issues
- Tracked problems derived from signals
- **Categories:** financial, schedule_delivery, communication, risk
- **Severity:** critical → high → medium → low → info (derived from rules, not manual)
- **States (10):** See state machine below

### Signals
- Single observations from source systems
- **Sources (7):** asana, gmail, gchat, calendar, meet, minutes, xero
- **Sentiment:** good / neutral / bad
- Can be flagged by detectors → becomes inbox proposal

### Inbox Items
- Proposals wrapping underlying entities
- **Types:** issue, flagged_signal, orphan, ambiguous
- Separate lifecycle from issues (proposal ≠ problem)

---

## 2. State Machines

### Inbox Item Lifecycle (4 states)

```
proposed ──┬── [Tag/Assign] ──→ linked_to_issue (terminal)
           ├── [Snooze] ──→ snoozed ──[timer]──→ proposed
           └── [Dismiss] ──→ dismissed (terminal)
```

- Terminal states excluded from default API; fetchable via `/recent`
- Snooze hides the proposal, NOT the underlying problem

### Issue Lifecycle (10 states)

```
detected ──[threshold]──→ surfaced ──┬── [Acknowledge] ──→ acknowledged
                                     ├── [Snooze] ──→ snoozed ──[timer]──→ surfaced
                                     └── [Suppress via inbox] ──→ (stays surfaced, suppressed=true)

acknowledged ──[Assign]──→ addressing ──→ awaiting_resolution ──→ resolved

resolved ──[immediate]──→ regression_watch ──┬── [90d clear] ──→ closed
                                             └── [recurrence] ──→ regressed ──→ surfaced
```

**Health-counted states:** surfaced, acknowledged, addressing, awaiting_resolution, regressed
**Excluded from health:** detected, snoozed, resolved, regression_watch, closed

### Engagement Lifecycle (7 states)

```
planned ──[task started]──→ active ──┬── blocked
                                     └── paused

active ──[80% complete]──→ delivering ──[all done]──→ delivered ──[paid/30d]──→ completed
```

Triggers are heuristic (best-effort pattern matching), not deterministic.

---

## 3. Key Business Rules

### Suppression (Dismiss)
- Dismissing creates a suppression rule (prevents re-proposal)
- Suppression key = SHA-256 hash of entity identifiers
- Expiry: Issue 90d, Flagged Signal 30d, Orphan 180d, Ambiguous 30d
- Suppression ≠ state change; it's a parallel flag
- Source of truth: `inbox_suppression_rules` table (not inbox item field)

### Snooze Semantics
- **Inbox snooze:** Hides reminder; issue stays open; health penalty still applies
- **Issue snooze:** Defers issue; excluded from health; archives any related inbox item
- Timer job runs hourly to resurface expired snoozes

### Tag vs Assign
- **Tag:** → acknowledged state; starts watch loop
- **Assign:** → addressing state; sets assignee; also records who tagged
- Both preserve "first confirmation" (tagged_by never overwritten)

### Escalation
- Parallel flag (like suppression), not a state
- Sets escalated=true + optionally bumps severity
- Available from addressing/awaiting_resolution states

### Orphan/Ambiguous Resolution
- **Orphan:** Signal references unknown project → Link or Create engagement
- **Ambiguous:** Signal matches multiple engagements → Select primary candidate
- After resolution, item becomes actionable (Tag/Assign available)

---

## 4. Health Scoring

### Client Health (v1 — provisional)
```
AR_penalty = floor(min(40, (AR_overdue / AR_outstanding) × 60))
Issue_penalty = min(30, open_high_critical_issues × 10)
Health = max(0, 100 - AR_penalty - Issue_penalty)
```

- Only high/critical issues count
- Suppressed and snoozed issues excluded
- "Provisional" label until task-based signals added

### Engagement Health (v1)
```
Gating: tasks_in_source > 0 AND linking_coverage ≥ 90%
Overdue_penalty = floor(min(50, (tasks_overdue / tasks_total) × 80))
Completion_lag = floor(min(30, avg_days_late × 5))
Health = max(0, 100 - Overdue_penalty - Completion_lag)
```

- Returns null with reason if gating fails
- `tasks_in_source` = open tasks only (excludes completed/archived/subtasks)

---

## 5. Evidence Structure

All evidence uses standardized envelope:

| Field | Description |
|-------|-------------|
| version | Schema version (v1) |
| kind | invoice, asana_task, gmail_thread, calendar_event, minutes_analysis, gchat_message |
| url | Deep link (nullable — null for minutes, xero) |
| display_text | Always present; human-readable label |
| source_system | Matches signal source |
| source_id | Unique ID in source system |
| payload | Kind-specific fields |

**Link rendering rules:**
- Xero: NEVER render link (no stable deep links)
- Minutes: No link (no direct access)
- Others: Render if URL present

---

## 6. API Contract Summary

### Client Index
- Filter: status, tier, has_issues, has_overdue_ar
- Sort: ar_overdue, last_invoice, name
- Returns grouped by status (active/recently_active/cold)

### Client Detail
- Default: union shape with null for excluded sections
- `?include=` for specific sections; strict (403 if forbidden)
- Always-present: id, name, status, tier
- recently_active/cold: limited data (no health, issues, signals, team)

### Inbox
- Filter: type, severity, state (proposed|snoozed only), client_id, unread_only
- Sort: severity desc → age asc → id asc (deterministic)
- Terminal states via `/recent` only
- Actions: tag, assign, snooze, dismiss, link, create, select

### Issues
- Filter: state (10 + all_open/all_closed/all), severity, type
- `detected` excluded from all_open by default
- `include_suppressed` and `include_snoozed` params
- Returns `available_actions` per state

### Financials
- Returns `finance_calc_version` for audit
- `issued_prior_year` / `issued_ytd` (not static year number)
- Invoices include server-computed `aging_bucket` and `status_inconsistent`

---

## 7. Timezone & Time Handling

- **Storage:** All timestamps UTC with Z suffix (TEXT, 24 chars exact)
- **org.timezone:** Required setting (default Asia/Dubai)
- **"Today":** Computed at request time using org timezone
- **Day boundaries:** Local midnight in org timezone
- **days=N params:** Use org-local day boundaries, not rolling 24h

---

## 8. User Scope Model

**Single-org, multi-user team with org-global shared state:**
- read_at, snooze, dismiss affect entire org (not per-user)
- User references (dismissed_by, snoozed_by) for audit trail only
- Suppression is org-wide

---

## 9. Severity Derivation (Examples)

| Category | Severity | Condition |
|----------|----------|-----------|
| Financial | critical | Invoice 45+ days overdue OR total overdue > 100k |
| Financial | high | Invoice 30-44 days overdue OR total overdue > 50k |
| Schedule | critical | 5+ tasks overdue by 7+ days |
| Schedule | high | 3+ tasks overdue OR any task 5+ days late |
| Communication | high | 3+ negative signals in 7d OR escalation keyword |

---

## 10. Detector Rules (Flagged Signals)

| Rule ID | Source | Trigger |
|---------|--------|---------|
| invoice_overdue_30d | xero | Invoice 30+ days past due |
| invoice_status_inconsistent | xero | status=sent but due_date ≤ today |
| task_overdue_7d | asana | Task 7+ days overdue |
| escalation_keyword | gmail/gchat | Keywords: "urgent", "escalate", "unacceptable" |
| meeting_cancelled | calendar | Meeting cancelled <24h before start |
| negative_sentiment_cluster | minutes | 3+ negative signals in 7 days |

---

## 11. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Inbox snooze semantics | Reminder snooze (issue stays open) | User defers notification, not problem |
| Suppression scope | Org-global | Team shares triage decisions |
| Evidence schema | Standardized envelope | Consistent rendering, unified audit |
| Invoice anomaly precedence | Issue wins over flagged_signal | Avoid duplicate proposals |
| Engagement triggers | Best-effort heuristics | Pattern-based, not test-critical |
| Xero links | Never render | No stable deep links available |

---

## 12. Constraints & Invariants

### Database
- Exactly one of underlying_issue_id / underlying_signal_id set
- Terminal states require resolved_at
- linked_to_issue requires resolved_issue_id
- dismissed requires dismissed_at + dismissed_by + suppression_key
- snoozed requires snooze_until
- Max one active inbox item per underlying entity (dedupe index)

### Application
- snooze_until must be future (DB can't enforce with TEXT)
- Inbox item scoping must match underlying entity scoping
- Suppression enforcement checks rules table, not inbox item field
- Dismiss is single transaction (inbox + underlying + rule)

---

## 13. Open for Implementation Team

1. Detector rule tuning (thresholds, keywords)
2. Async job scheduling (snooze expiry hourly)
3. UI copy refinements (especially snooze messaging)
4. Engagement heuristic confidence tuning
5. Minutes analysis provider integration (Gemini)
6. Task sync frequency optimization

---

## 14. Test Coverage Required

- 40 required test cases covering:
  - Suppression expiry and enforcement
  - Snooze boundary conditions
  - Ambiguous resolution flow
  - Health scoring exclusions
  - Client status boundaries
  - Constraint violations
  - API validation
  - Dedupe behavior
  - Timezone conversions

---

*End of executive summary.*
