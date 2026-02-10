# Implementation Checklist — Time OS UI Spec v2.1

*Maps spec sections → code modules/files → tests*

---

## 1. Database Schema (Spec Section 6.13-6.15, 6.5, 6.7, 1.8)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 6.13 inbox_items | `migrations/001_inbox_items.sql` | #16, #17, #18, #21, #39, #40 |
| 6.14 issues | `migrations/002_issues.sql` | #2, #3, #7, #8 |
| 6.15 signals | `migrations/003_signals.sql` | #1 |
| 6.5 issue_transitions | `migrations/004_transitions.sql` | #5 |
| 6.7 engagement_transitions | `migrations/004_transitions.sql` | — |
| 1.8 inbox_suppression_rules | `migrations/005_suppression_rules.sql` | #1, #31, #32, #33, #34 |

**Constraints (via triggers):**
- `chk_underlying_exclusive` → Test #16
- `chk_snooze_requires_until` → Test #17
- `chk_dismissed_requires_key` → Test #18
- `chk_terminal_requires_resolved` → Test #39, #40
- `chk_linked_requires_issue` → Test #39
- `chk_dismissed_requires_audit` → Test #40

---

## 2. Time Utilities (Spec Section 0.1, 1.9)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 0.1 Timestamp Format | `time_utils.py` | Unit tests in module |
| 0.1 local_midnight_utc | `time_utils.py` | #37 |
| 1.9 window_start | `time_utils.py` | — |
| 0.1 days_late | `time_utils.py` | — |

---

## 3. Evidence Module (Spec Section 6.16, 6.10, 6.4)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 6.16 Evidence Meta-Schema | `evidence.py` | — |
| 6.10 Xero Linking | `evidence.py` | #12 |
| 6.4 Evidence Rules | `evidence.py` | — |

---

## 4. Suppression Module (Spec Section 1.8)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 1.8 Suppression Key Algorithm | `suppression.py` | #33 |
| 1.8 Suppression Rules | `suppression.py` | #1, #31, #34 |
| 1.8 Expiry Defaults | `suppression.py` | #1 |
| 1.8 Source of Truth | `suppression.py` | #31 |
| 1.8 Transaction Boundary | `suppression.py` | #2 |
| 7.6 Unsuppress | `suppression.py` | #3 |

---

## 5. Health Calculations (Spec Section 6.6, 6.17)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 6.6 Client Health | `health.py` | #7, #8 |
| 6.6 Engagement Health | `health.py` | #13, #14, #15 |
| 6.6 Health-counted States | `health.py` | #7, #8 |

---

## 6. Inbox Lifecycle (Spec Section 1.4, 1.6, 1.7, 1.8, 7.10)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 1.4 Inbox States | `inbox_lifecycle.py` | #4, #24 |
| 1.6 Primary Actions | `inbox_lifecycle.py` | #6 |
| 1.7 Tag & Watch | `inbox_lifecycle.py` | #29 |
| 1.8 Dismiss | `inbox_lifecycle.py` | #2, #35 |
| 7.10 Action Validation | `inbox_lifecycle.py` | #19, #20 |
| 1.4 Snooze Timer | `inbox_lifecycle.py` | #4 |
| 1.10 Mark Read | `inbox_lifecycle.py` | #28 |

---

## 7. Issue Lifecycle (Spec Section 6.5, 7.6)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 6.5 Issue States (10) | `issue_lifecycle.py` | #30 |
| 6.5 Snooze Timer | `issue_lifecycle.py` | #5, #23 |
| 6.5 Issue ↔ Inbox | `issue_lifecycle.py` | #23, #24 |
| 7.6 Transitions | `issue_lifecycle.py` | #38 |
| 7.6 Regression | `issue_lifecycle.py` | #36 |
| 7.6 Available Actions | `issue_lifecycle.py` | #30 |

---

## 8. Detectors (Spec Section 6.4)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 6.4 Detector Rules | `detectors.py` | — |
| 6.4 Financial Threshold | `detectors.py` | — |
| Decision C Precedence | `detectors.py` | #25, #26 |

---

## 9. Client Endpoints (Spec Section 7.1-7.3, 7.9)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 7.1 Client Index | `endpoints.py` | — |
| 7.2 Client Detail | `endpoints.py` | — |
| 7.3 Client Snapshot | `endpoints.py` | — |
| 7.9 Include Policy | `endpoints.py` | — |
| 6.1 Client Status | `endpoints.py` | #9, #10, #11 |

---

## 10. Financials Endpoints (Spec Section 7.5)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 7.5 Financials | `endpoints.py` | — |
| 7.5 Invoice Aging | `endpoints.py` | #25 |
| 7.5 AR Aging Buckets | `endpoints.py` | — |

---

## 11. Inbox Endpoints (Spec Section 7.10)

| Spec Section | Module/File | Tests |
|--------------|-------------|-------|
| 7.10 GET /api/inbox | `endpoints.py` | — |
| 7.10 GET /api/inbox/recent | `endpoints.py` | — |
| 7.10 POST action | `endpoints.py` | #19, #20 |
| 7.10 Counts | `endpoints.py` | — |

---

## Test Case Summary

| Test # | Name | Status |
|--------|------|--------|
| 1 | spec_1_dismiss_suppression_expiry | ✅ |
| 2 | spec_2_issue_suppression | ✅ |
| 3 | spec_3_unsuppress | ✅ |
| 4 | spec_4_snooze_expiry_boundary | ✅ |
| 5 | spec_5_issue_snooze_expiry_transition | ✅ |
| 6 | spec_6_ambiguous_select_actionable | ✅ |
| 7 | spec_7_suppressed_excluded_from_health | ✅ |
| 8 | spec_8_snoozed_excluded_from_health | ✅ |
| 9 | spec_9_client_status_exactly_90_days | ✅ |
| 10 | spec_10_client_status_exactly_270_days | ✅ |
| 11 | spec_11_client_status_no_invoices | ✅ |
| 12 | spec_12_no_xero_href | ✅ |
| 13 | spec_13_engagement_health_no_tasks | ✅ |
| 14 | spec_14_engagement_health_low_linking | ✅ |
| 15 | spec_15_engagement_health_coverage_source | ✅ |
| 16 | spec_16_constraint_underlying_exclusive | ✅ |
| 17 | spec_17_constraint_snooze_requires_until | ✅ |
| 18 | spec_18_constraint_dismiss_requires_key | ✅ |
| 19 | spec_19_action_payload_rejection | ✅ |
| 20 | spec_20_required_field_missing | ✅ |
| 21 | spec_21_no_duplicate_active_inbox_items | ✅ |
| 22 | spec_22_terminal_allows_new | ✅ |
| 23 | spec_23_issue_snooze_archives_inbox_item | ✅ |
| 24 | spec_24_inbox_snooze_independent_of_issue | ✅ |
| 25 | spec_25_sent_but_past_due | ✅ |
| 26 | spec_26_no_double_create | ✅ |
| 27 | spec_27_global_suppression | ✅ |
| 28 | spec_28_global_read_state | ✅ |
| 29 | spec_29_assign_sets_tagged_by | ✅ |
| 30 | spec_30_actions_match_state | ✅ |
| 31 | spec_31_suppression_source_of_truth | ✅ |
| 32 | spec_32_audit_key_preserved | ✅ |
| 33 | spec_33_suppression_key_entropy | ✅ |
| 34 | spec_34_dismiss_reason_persists | ✅ |
| 35 | spec_35_ambiguous_select_then_dismiss | ✅ |
| 36 | spec_36_new_inbox_item_on_regression | ✅ |
| 37 | spec_37_dubai_midnight_conversion | ✅ |
| 38 | spec_38_assign_after_tag_preserves_tagged_by | ✅ |
| 39 | spec_39_constraint_linked_requires_issue | ✅ |
| 40 | spec_40_constraint_dismissed_requires_audit | ✅ |

---

## File Structure

```
lib/ui_spec_v21/
├── __init__.py                    # Package exports
├── CONTRACT_MAP.md                # Derived contract map
├── IMPLEMENTATION_CHECKLIST.md    # This file
├── time_utils.py                  # Timezone + date utilities
├── suppression.py                 # Suppression key + rules
├── evidence.py                    # Evidence validation + link rendering
├── health.py                      # Client + engagement health
├── inbox_lifecycle.py             # Inbox state machine + actions
├── issue_lifecycle.py             # Issue state machine + transitions
├── detectors.py                   # Detector rules + precedence
├── endpoints.py                   # API endpoints
├── migrations/
│   ├── __init__.py               # Migration runner
│   ├── 001_inbox_items.sql       # inbox_items table
│   ├── 002_issues.sql            # issues table
│   ├── 003_signals.sql           # signals table
│   ├── 004_transitions.sql       # audit trail tables
│   └── 005_suppression_rules.sql # suppression rules
└── tests/
    ├── __init__.py
    └── test_spec_cases.py        # All 40 required test cases
```

---

## Running Tests

```bash
cd /Users/molhamhomsi/clawd/moh_time_os
python -m pytest lib/ui_spec_v21/tests/test_spec_cases.py -v
```

---

## Applying Migrations

```bash
cd /Users/molhamhomsi/clawd/moh_time_os
python -m lib.ui_spec_v21.migrations data/moh_time_os_v2.db
```

---

*End of checklist.*
