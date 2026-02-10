# Contract Map — Time OS Client UI Specification v2.1

*Derived from spec_time_os_v2_1_final.md — 2026-02-07*

## 1. Database Tables

### 1.1 Core Tables

| Table | Spec Section | Purpose |
|-------|--------------|---------|
| `inbox_items` | 6.13 | Proposal wrappers for issues/signals/orphans/ambiguous |
| `issues` | 6.14 | Tracked problems from aggregated signals |
| `signals` | 6.15 | Single observations from source systems |
| `issue_transitions` | 6.5 | Audit trail for issue state changes |
| `engagement_transitions` | 6.7 | Audit trail for engagement state changes |
| `inbox_suppression_rules` | 1.8 | Suppression keys to prevent re-proposals |

### 1.2 Table Constraints (inbox_items)

| Constraint | Type | SQL |
|------------|------|-----|
| `chk_underlying_exclusive` | CHECK | `(underlying_issue_id IS NOT NULL) != (underlying_signal_id IS NOT NULL)` |
| `chk_type_issue_mapping` | CHECK | `type != 'issue' OR (underlying_issue_id IS NOT NULL AND underlying_signal_id IS NULL)` |
| `chk_type_signal_mapping` | CHECK | `type NOT IN ('flagged_signal', 'orphan', 'ambiguous') OR (underlying_signal_id IS NOT NULL AND underlying_issue_id IS NULL)` |
| `chk_snooze_requires_until` | CHECK | `state != 'snoozed' OR snooze_until IS NOT NULL` |
| `chk_dismissed_requires_key` | CHECK | `state != 'dismissed' OR suppression_key IS NOT NULL` |
| `chk_terminal_requires_resolved` | CHECK | `state NOT IN ('dismissed', 'linked_to_issue') OR resolved_at IS NOT NULL` |
| `chk_linked_requires_issue` | CHECK | `state != 'linked_to_issue' OR resolved_issue_id IS NOT NULL` |
| `chk_dismissed_requires_audit` | CHECK | `state != 'dismissed' OR (dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL)` |

### 1.3 Unique Partial Indexes

| Index | Purpose |
|-------|---------|
| `idx_inbox_items_unique_active_issue` | At most one active inbox item per underlying issue |
| `idx_inbox_items_unique_active_signal` | At most one active inbox item per underlying signal |

---

## 2. Endpoints

### 2.1 Client Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/clients` | GET | 7.1 | Client index with sections active/recently_active/cold |
| `/api/clients/:id` | GET | 7.2 | Client detail with include policy |
| `/api/clients/:id/snapshot` | GET | 7.3 | Cold client snapshot from inbox |
| `/api/clients/:id/engagements` | GET | 7.4 | Engagements grouped by brand |
| `/api/clients/:id/financials` | GET | 7.5 | Financial summary with calc version |
| `/api/clients/:id/invoices` | GET | 7.5 | Invoice list with aging |
| `/api/clients/:id/issues` | GET | 7.6 | Issues with state/severity filters |
| `/api/clients/:id/signals` | GET | 7.7 | Signals summary and list |
| `/api/clients/:id/team` | GET | 7.8 | Team involvement and workload |
| `/api/clients/search` | GET | 7.10 | Client search |

### 2.2 Issue Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/issues/:id/transition` | POST | 7.6 | Issue state transitions |
| `/api/issues/:id/unsuppress` | POST | 7.6 | Unsuppress issue (idempotent) |

### 2.3 Inbox Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/inbox` | GET | 7.10 | Active inbox items (proposed/snoozed) |
| `/api/inbox/recent` | GET | 7.10 | Terminal items for audit |
| `/api/inbox/counts` | GET | 7.10 | Inbox counts by grouping |
| `/api/inbox/:id/action` | POST | 7.10 | Inbox actions (tag/assign/snooze/dismiss/link/select) |
| `/api/inbox/:id/mark_read` | POST | 7.10 | Mark item as read |
| `/api/inbox/mark_all_read` | POST | 7.10 | Bulk mark all as read |
| `/api/inbox/bulk_action` | POST | 7.10 | Bulk snooze/dismiss |
| `/api/inbox/search` | GET | 7.10 | Inbox search |

### 2.4 Engagement Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/engagements/:id` | GET | 7.11 | Engagement detail |
| `/api/engagements/:id/transition` | POST | 7.11 | Engagement state transition |

---

## 3. State Machines

### 3.1 Issue Lifecycle (10 states)

```
detected → surfaced → acknowledged → addressing → awaiting_resolution → resolved → regression_watch → closed
                  ↓                                                                              ↓
              snoozed ←──────────────────────────────────────────────────────────────────── regressed
```

| State | Health Penalty | Open/Closed |
|-------|----------------|-------------|
| detected | No | Open |
| surfaced | Yes | Open |
| snoozed | No | Open |
| acknowledged | Yes | Open |
| addressing | Yes | Open |
| awaiting_resolution | Yes | Open |
| resolved | No | Closed |
| regression_watch | No | Closed |
| closed | No | Closed |
| regressed | Yes | Open |

### 3.2 Inbox Item Lifecycle (4 states)

```
proposed → snoozed → proposed (resurface)
      ↓        ↓
  linked_to_issue (terminal)
      ↓
  dismissed (terminal)
```

### 3.3 Engagement Lifecycle (7 states)

```
planned → active → delivering → delivered → completed
            ↓↑          ↓↑
         blocked, paused
```

---

## 4. Timers

| Timer | Frequency | Action |
|-------|-----------|--------|
| Snooze expiry (inbox) | Hourly | `snoozed` → `proposed` if `snooze_until <= now()` |
| Snooze expiry (issue) | Hourly | `snoozed` → `surfaced` + log transition |
| Regression watch | Daily | After 90d: `regression_watch` → `closed` |
| Suppression cleanup | Daily | Delete expired `inbox_suppression_rules` |

---

## 5. Deterministic Calculations

### 5.1 Timezone (0.1)

```python
def local_midnight_utc(org_tz: str, date: date) -> datetime:
    local_midnight = datetime.combine(date, time.min, tzinfo=ZoneInfo(org_tz))
    return local_midnight.astimezone(UTC)

def window_start(org_tz: str, days: int) -> datetime:
    local_today = datetime.now(ZoneInfo(org_tz)).date()
    local_start_date = local_today - timedelta(days=days)
    return local_midnight_utc(org_tz, local_start_date)
```

### 5.2 Client Status (6.1)

```
Active:          MAX(invoices.issue_date) >= today - 90 days
Recently Active: MAX(invoices.issue_date) >= today - 270 days AND < today - 90 days
Cold:            MAX(invoices.issue_date) < today - 270 days OR no invoices
```

### 5.3 Client Health (6.6)

```python
AR_penalty = floor(min(40, overdue_ratio * 60))
Issue_penalty = min(30, high_critical_open_issues * 10)
Health = max(0, 100 - AR_penalty - Issue_penalty)
```

### 5.4 Engagement Health (6.6/6.17)

```python
if open_tasks_in_source == 0:
    return None, "no_tasks"
if linked_pct < 0.90:
    return None, "task_linking_incomplete"
Overdue_penalty = floor(min(50, overdue_ratio * 80))
Completion_lag = floor(min(30, avg_days_late * 5))
Health = max(0, 100 - Overdue_penalty - Completion_lag)
```

### 5.5 Suppression Key (1.8)

```python
def suppression_key(item_type: str, data: dict) -> str:
    payload = {"v": "v1", "t": item_type, **data}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return "sk_" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]
```

### 5.6 Invoice Aging (7.5)

| status | Condition | days_overdue | aging_bucket | status_inconsistent |
|--------|-----------|--------------|--------------|---------------------|
| overdue | due_date not null | `max(0, today - due_date)` | Computed | false |
| overdue | due_date null | null | 90_plus | false |
| sent | due_date > today | null | current | false |
| sent | due_date <= today | Computed | Computed | **true** |
| paid/voided/draft | any | null | null | false |

---

## 6. Severity Ordering (0.1)

| Severity | Weight |
|----------|--------|
| critical | 5 |
| high | 4 |
| medium | 3 |
| low | 2 |
| info | 1 |

---

## 7. Suppression Expiry Defaults (1.8)

| Item Type | Expiry |
|-----------|--------|
| Issue | 90 days |
| Flagged Signal | 30 days |
| Orphan | 180 days |
| Ambiguous | 30 days |

---

## 8. Action Payload Validation (7.10)

| Action | Required | Optional | Reject if Present |
|--------|----------|----------|-------------------|
| tag | — | note | assign_to, snooze_days, link_engagement_id, select_candidate_id |
| assign | assign_to | note | snooze_days, link_engagement_id, select_candidate_id |
| snooze | snooze_days | note | assign_to, link_engagement_id, select_candidate_id |
| dismiss | — | note | assign_to, snooze_days, link_engagement_id, select_candidate_id |
| link | link_engagement_id | note | assign_to, snooze_days, select_candidate_id |
| select | select_candidate_id | note | assign_to, snooze_days, link_engagement_id |

---

## 9. Detector Rules (6.4)

| Rule ID | Source | Trigger |
|---------|--------|---------|
| meeting_cancelled_short_notice | calendar | Cancelled < 24h before start |
| email_unanswered_48h | gmail | Client email unanswered 48h+ |
| task_overdue | asana | Task past due_date |
| sentiment_negative | gmail/gchat/minutes | Sentiment < -0.3 |
| escalation_keyword | gchat | "urgent", "escalate", "problem" |
| invoice_overdue | xero | Invoice past due_date |
| invoice_status_inconsistent | xero | status='sent' AND due_date <= today |

---

## 10. Patch Notes (Contradiction Resolutions)

None detected. Spec is internally consistent.

---

*End of contract map.*
