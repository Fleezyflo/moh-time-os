# Exhaustiveness-Grade Closure Audit

Generated: 2026-03-12
Baseline: `docs/endpoint-fix-audit.md` (41 handler bugs as of latest pass)

---

## Phase 1: Schema Baseline

Exact column lists from `lib/schema.py` for every table involved in defect families.

### notifications (schema.py:740)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | TEXT PRIMARY KEY | — | NO |
| type | TEXT NOT NULL | — | NO |
| priority | TEXT NOT NULL | 'normal' | NO |
| title | TEXT NOT NULL | — | NO |
| body | TEXT | — | YES |
| action_url | TEXT | — | YES |
| action_data | TEXT | — | YES |
| channels | TEXT | — | YES |
| sent_at | TEXT | — | YES |
| read_at | TEXT | — | YES |
| acted_on_at | TEXT | — | YES |
| created_at | TEXT NOT NULL | — | NO |

**12 columns. No: dismissed, dismissed_at, task_id, target_id, recipient_id, delivery_channel, delivery_id.**

### decisions (schema.py:719)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | TEXT PRIMARY KEY | — | NO |
| domain | TEXT NOT NULL | — | NO |
| decision_type | TEXT NOT NULL | — | NO |
| description | TEXT | — | YES |
| input_data | TEXT | — | YES |
| options | TEXT | — | YES |
| selected_option | TEXT | — | YES |
| rationale | TEXT | — | YES |
| confidence | REAL | 0.5 | YES |
| requires_approval | INTEGER | 1 | YES |
| approved | INTEGER | — | YES |
| approved_at | TEXT | — | YES |
| executed | INTEGER | 0 | YES |
| executed_at | TEXT | — | YES |
| outcome | TEXT | — | YES |
| created_at | TEXT NOT NULL | — | NO |

**16 columns. No: type, target_id, proposed_changes, reason, processed_by, modifications.**

### governance_audit_log (schema.py:1221)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | TEXT PRIMARY KEY | — | NO |
| timestamp | TEXT | — | YES |
| action | TEXT | — | YES |
| actor | TEXT | — | YES |
| subject_identifier | TEXT | — | YES |
| details | TEXT | — | YES |
| ip_address | TEXT | — | YES |
| created_at | TEXT | — | YES |

**8 columns. No table named `governance_history` exists in schema.py.**

### actions (schema.py:757)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | TEXT PRIMARY KEY | — | NO |
| type | TEXT NOT NULL | — | NO |
| target_system | TEXT | — | YES |
| payload | TEXT NOT NULL | — | NO |
| status | TEXT | 'pending' | YES |
| requires_approval | INTEGER | 1 | YES |
| approved_by | TEXT | — | YES |
| approved_at | TEXT | — | YES |
| executed_at | TEXT | — | YES |
| result | TEXT | — | YES |
| error | TEXT | — | YES |
| retry_count | INTEGER | 0 | YES |
| created_at | TEXT NOT NULL | — | NO |

**13 columns.**

### cycle_logs (schema.py:804)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | TEXT PRIMARY KEY | — | NO |
| cycle_number | INTEGER | — | YES |
| phase | TEXT | — | YES |
| data | TEXT | — | YES |
| duration_ms | REAL | — | YES |
| created_at | TEXT NOT NULL | — | NO |

**6 columns.**

### communications (schema.py:251)
50 columns. Key ones for audit:
- id, source, source_id, thread_id, from_email, from_domain, to_emails, subject, snippet, body_text, body_text_source, content_hash, received_at, client_id, link_status, priority, requires_response, response_deadline, sentiment, labels, processed, sensitivity, stakeholder_tier, is_read, is_starred, importance, has_attachments, attachment_count, label_ids, lane, is_vip, from_name, is_unread, is_important, priority_reasons, response_urgency, expected_response_by, processed_at, action_taken, linked_task_id, age_hours, created_at, updated_at.

**No: channel, type, actionable, sender, recipient, body (as column name).**

### entity_links (schema.py:1526)
| Column | Type | Default | Nullable |
|---|---|---|---|
| id | INTEGER PRIMARY KEY | — | NO |
| from_artifact_id | TEXT | — | YES |
| to_entity_type | TEXT NOT NULL | — | NO |
| to_entity_id | TEXT NOT NULL | — | NO |
| confidence | REAL | 1.0 | YES |
| method | TEXT | 'system' | YES |
| created_at | TEXT NOT NULL | datetime('now') | NO |

**7 columns. No: status, confirmed_by, confirmed_at, updated_at, confidence_reasons, link_id, entity_id, linked_id, entity_type.**

### saved_filters
**Does not exist in schema.py.** No TABLES["saved_filters"] definition. Not created by any inline CREATE TABLE (confirmed via grep in prior pass).

---

## Phase 2: Notifications family — full occurrence sweep

Search method: `grep -rn '"notifications"' api/server.py lib/` + `grep -rn 'INSERT.*notifications\|UPDATE.*notifications'` across full repo.

### 2a. INSERTs into `notifications`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| N-I1 | api/server.py:1127 | POST /api/tasks/{id}/delegate — notify assignee | `recipient_id`, `task_id`, `dismissed` | id, type, title, body, created_at | FATAL — store.insert() builds INSERT with non-existent columns → sqlite3.OperationalError. Wrapped in try at :1120, caught at :1157 → **re-raised as HTTPException(500)**. Entire delegate operation fails. | BUG |
| N-I2 | api/server.py:1303 | POST /api/tasks/{id}/escalate — notify escalation target | `recipient_id`, `task_id`, `dismissed`, `priority` (priority exists) | id, type, title, body, created_at | FATAL — same mechanism. Wrapped in outer try/except that re-raises as HTTP 500. Entire escalation fails. | BUG |
| N-I3 | api/server.py:1322 | POST /api/tasks/{id}/escalate — notify original assignee | `recipient_id`, `task_id`, `dismissed` | id, type, title, body, created_at | FATAL — same. Part of same try block as N-I2, re-raised as HTTP 500. | BUG |
| N-I4 | api/server.py:2245 | POST /api/decisions/{decision_id} — api_decision() delegation_approved side-effect | `recipient_id`, `task_id`, `dismissed` | id, type, title, body, created_at | CAUGHT — wrapped in `except (sqlite3.Error, ValueError) as e:` at line 2258. Side-effect silently fails. Approval succeeds but notification is lost. | BUG (degraded) |
| N-I5 | api/server.py:2277 | POST /api/decisions/{id}/approve — escalation_approved side-effect | `recipient_id`, `task_id`, `dismissed`, `priority` (priority exists) | id, type, title, body, created_at | CAUGHT — same try/except block at line 2291. Side-effect silently fails. | BUG (degraded) |
| N-I6 | lib/autonomous_loop.py:1547 | _create_notification() helper | — | id, type, priority, title, body, action_data, channels, created_at | All columns exist in schema. | CLEAN |
| N-I7 | lib/executor/handlers/delegation.py:152 | DelegationHandler — delegation accepted notif | — | id, type, priority, title, body, created_at | All columns exist. | CLEAN |
| N-I8 | lib/executor/handlers/delegation.py:234 | DelegationHandler — delegation rejected notif | — | id, type, priority, title, body, created_at | All columns exist. | CLEAN |
| N-I9 | lib/executor/handlers/notification.py:60 | NotificationHandler._create_notification() | — | id, type, priority, title, body, action_url, action_data, channels, created_at | All columns exist. | CLEAN |
| N-I10 | lib/notifier/engine.py:476 | NotificationEngine.create_notification() | — | id, type, priority, title, body, action_url, action_data, channels, created_at | All columns exist. | CLEAN |

**INSERTs total: 10 occurrences. 5 BUGS (N-I1 through N-I5), 5 CLEAN (N-I6 through N-I10).**

Bad columns across INSERT bugs: `recipient_id` (5×), `task_id` (5×), `dismissed` (5×). These three columns do not exist on the notifications table.

### 2b. UPDATEs on `notifications`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| N-U1 | api/server.py:3039 | POST /api/notifications/{id}/dismiss | `dismissed`, `dismissed_at` | — | FATAL — store.update() builds SET clause with non-existent columns → sqlite3.OperationalError. No try/except. Crashes the endpoint. | BUG |
| N-U2 | api/server.py:3056 | POST /api/notifications/dismiss-all — loop body | `dismissed`, `dismissed_at` | — | FATAL — same mechanism. No try/except. Crashes the endpoint. | BUG |

**UPDATEs total: 2 occurrences. 2 BUGS (N-U1, N-U2), 0 CLEAN.**

**Note:** N-U3 (engine.py:207) and N-U4 (engine.py:399) were identified as candidates but are **ALREADY FIXED** in source. Lines 210-213 and 402-404 contain audit fix comments: "delivery_channel / delivery_id do NOT exist in notifications table — setting them caused OperationalError on EVERY send (audit fix)." Both now only set `sent_at`. Excluded from bug count.

Bad columns across UPDATE bugs: `dismissed` (2×), `dismissed_at` (2×).

### 2c. SELECTs / queries on `notifications`

| # | File:Line | Context | Bad Columns | Runtime | Classification |
|---|---|---|---|---|---|
| N-S1 | api/server.py:3008 | GET /api/notifications — WHERE filter | `dismissed` in WHERE clause | SILENT — SQLite allows `WHERE dismissed = 0 OR dismissed IS NULL` on a non-existent column **only if safe_sql.select() wraps it in a subquery or uses column names**. However, `safe_sql.where_and()` just returns a string. The actual query is `SELECT * FROM notifications WHERE (dismissed = 0 OR dismissed IS NULL)`. SQLite 3.37.2 **will error** on unknown column name in WHERE. → FATAL. | BUG |
| N-S2 | api/server.py:3052 | POST /api/notifications/dismiss-all — fetch undismissed | `dismissed` in WHERE clause | Same as N-S1. Raw SQL `SELECT id FROM notifications WHERE dismissed = 0 OR dismissed IS NULL` → sqlite3.OperationalError. | BUG |
| N-S3 | api/server.py:3028 | GET /api/notifications/stats — count total | — | `store.count("notifications")` — no column references. | CLEAN |
| N-S4 | api/server.py:3029 | GET /api/notifications/stats — count unread | `read_at IS NULL` | `read_at` exists in schema. | CLEAN |
| N-S5 | lib/notifier/engine.py:515-518 | _check_rate_limit() — count sent today | `priority`, `sent_at` | Both exist. | CLEAN |
| N-S6 | lib/executor/handlers/notification.py:132 | _cancel_notification — get by id | — | `store.get()` — no column filter. | CLEAN |

**SELECTs total: 6 occurrences. 2 BUGS (N-S1, N-S2), 4 CLEAN (N-S3 through N-S6).**

### 2d. DELETEs on `notifications`

| # | File:Line | Context | Classification |
|---|---|---|---|
| N-D1 | lib/executor/handlers/notification.py:136 | _cancel_notification — delete by id | CLEAN — `store.delete("notifications", notif_id)` uses primary key only. |

**DELETEs total: 1 occurrence. 0 BUGS.**

### 2e. Notifications family summary

| Category | Total | Bugs | Clean |
|---|---|---|---|
| INSERTs | 10 | 5 | 5 |
| UPDATEs | 2 | 2 | 0 |
| SELECTs | 6 | 2 | 4 |
| DELETEs | 1 | 0 | 1 |
| **Total** | **19** | **9** | **10** |

Distinct bad columns: `recipient_id`, `task_id`, `dismissed`, `dismissed_at` — 4 phantom columns total. (N-U3/N-U4 delivery_channel/delivery_id already fixed in source — see Phase 2b note.)

### 2f. Adjacent bug found during notifications sweep

executor/handlers/notification.py:142 — `_log_action()` inserts into the `actions` table with columns `domain`, `action_type`, `target_id`, `data`. The `actions` schema has: id, type, target_system, payload, status, requires_approval, approved_by, approved_at, executed_at, result, error, retry_count, created_at. None of `domain`, `action_type`, `target_id`, `data` exist. Deferred to Phase 6.

## Phase 3: Decisions family — full occurrence sweep

Search method: `grep -rn '"decisions"' api/server.py lib/` across full repo. Schema reference: `decisions` has 16 columns (id, domain, decision_type, description, input_data, options, selected_option, rationale, confidence, requires_approval, approved, approved_at, executed, executed_at, outcome, created_at).

### 3a. INSERTs into `decisions`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| D-I1 | api/server.py:863 | PUT /api/tasks/{id} — pending decision when governance denies auto-exec | `type` (should be `decision_type`), `target_id`, `proposed_changes`, `reason` | id, description, created_at | FATAL — 4 non-existent columns. No try/except around this insert. Crashes the endpoint when governance blocks auto-execution. | BUG |
| D-I2 | api/server.py:1083 | POST /api/tasks/{id}/delegate — pending delegation decision | `type`, `target_id`, `proposed_changes`, `reason` | id, description, created_at | FATAL — same 4 bad columns. No try/except. | BUG |
| D-I3 | api/server.py:1257 | POST /api/tasks/{id}/escalate — pending escalation decision | `type`, `target_id`, `proposed_changes`, `reason` | id, description, created_at | FATAL — same 4 bad columns. No try/except. | BUG |
| D-I4 | lib/executor/handlers/email.py:67 | EmailHandler._create_draft() — email send decision | — | id, domain, decision_type, description, input_data, requires_approval, created_at | All columns exist in schema. | CLEAN |
| D-I5 | lib/executor/handlers/email.py:133 | EmailHandler._create_proactive_draft() — proactive email decision | — | id, domain, decision_type, description, input_data, requires_approval, created_at | All columns exist. | CLEAN |
| D-I6 | lib/reasoner/decisions.py:194 | DecisionMaker.create_decision() — core decision creation | — | id, domain, decision_type, description, input_data, options, selected_option, rationale, confidence, requires_approval, approved, approved_at, created_at | All columns exist. This is the correct canonical path. | CLEAN |

**INSERTs total: 6 occurrences. 3 BUGS (D-I1 through D-I3), 3 CLEAN (D-I4 through D-I6).**

Bad columns across INSERT bugs: `type` (3× — should be `decision_type`), `target_id` (3×), `proposed_changes` (3×), `reason` (3×). All 4 columns do not exist on the decisions table.

Note: D-I1/D-I2/D-I3 also omit `domain` (NOT NULL) — the INSERT would fail on the NOT NULL constraint even if the phantom columns didn't exist.

### 3b. UPDATEs on `decisions`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| D-U1 | api/server.py:2202 | POST /api/decisions/{decision_id} — api_decision() main approval path | `processed_by` | approved, approved_at | FATAL — `processed_by` does not exist. Wrapped in try at :2200, caught and **re-raised as HTTP 500** at :2350. Entire approval fails. | BUG |
| D-U2 | api/server.py:3105 | POST /api/approvals/{decision_id}/modify — modify_approval() | `modifications` | approved, approved_at | FATAL — `modifications` does not exist. No try/except. Crashes the endpoint. | BUG |
| D-U3 | api/server.py:3081 | POST /api/approvals/{id} — simple approve/reject | — | approved, approved_at | Both columns exist. | CLEAN |
| D-U4 | lib/reasoner/decisions.py:239 | approve_decision() | — | approved, approved_at | Both columns exist. | CLEAN |
| D-U5 | lib/reasoner/decisions.py:255 | reject_decision() | — | approved, approved_at | Both columns exist. | CLEAN |

**UPDATEs total: 5 occurrences. 2 BUGS (D-U1, D-U2), 3 CLEAN (D-U3 through D-U5).**

Bad columns across UPDATE bugs: `processed_by` (1×), `modifications` (1×).

### 3c. SELECTs / queries on `decisions`

| # | File:Line | Context | Classification |
|---|---|---|---|
| D-S1 | api/server.py:1998 | GET /api/decisions — `SELECT * FROM decisions WHERE approved IS NULL` | CLEAN — `approved` exists. |
| D-S2 | api/server.py:264 | GET /api/dashboard — `store.count("decisions", "approved IS NULL")` | CLEAN |
| D-S3 | api/server.py:3076 | POST /api/approvals/{id} — `store.get("decisions", decision_id)` | CLEAN |
| D-S4 | api/server.py:3100 | POST /api/approvals/{id}/modify — `store.get("decisions", decision_id)` | CLEAN |
| D-S5 | api/server.py:3401 | GET /api/control-room — `store.count("decisions", "approved IS NULL")` | CLEAN |
| D-S6 | lib/reasoner/engine.py:49 | run_cycle() — `store.get("decisions", id)` | CLEAN |
| D-S7 | lib/reasoner/engine.py:62 | get_pending_count() — `store.count("decisions", "approved IS NULL")` | CLEAN |
| D-S8 | lib/reasoner/decisions.py:235 | approve_decision() — `store.get("decisions", id)` | CLEAN |
| D-S9 | lib/reasoner/decisions.py:251 | reject_decision() — `store.get("decisions", id)` | CLEAN |
| D-S10 | lib/autonomous_loop.py:1646 | get_status() — `store.count("decisions", "approved IS NULL")` | CLEAN |

**SELECTs total: 10 occurrences. 0 BUGS.**

Note: `lib/v4/issue_service.py:483` queries `decision_log` (a different V4 table), not `decisions`. Excluded from this family.

### 3d. Decisions family summary

| Category | Total | Bugs | Clean |
|---|---|---|---|
| INSERTs | 6 | 3 | 3 |
| UPDATEs | 5 | 2 | 3 |
| SELECTs | 10 | 0 | 10 |
| **Total** | **21** | **5** | **16** |

Distinct bad columns: `type` (should be decision_type), `target_id`, `proposed_changes`, `reason`, `processed_by`, `modifications` — 6 phantom columns total.

Additional structural defect in D-I1/D-I2/D-I3: `domain` (NOT NULL) is omitted from the INSERT dict.

## Phase 4: Governance family — full occurrence sweep

Search method: `grep -rn 'governance_history\|governance_audit_log' --include='*.py'` across full repo.

The schema defines `governance_audit_log` (8 columns: id, timestamp, action, actor, subject_identifier, details, ip_address, created_at). No table named `governance_history` exists anywhere in `lib/schema.py` or any inline `CREATE TABLE`.

### 4a. References to `governance_history` (wrong table name)

| # | File:Line | Context | Operation | Columns Referenced | Runtime | Classification |
|---|---|---|---|---|---|---|
| G-1 | api/server.py:2314 | POST /api/decisions/{id}/approve — log to governance history | INSERT via store.insert() | `id, decision_id, action, type, target_id, processed_by, side_effects, created_at` | FATAL — table doesn't exist → sqlite3.OperationalError. Not wrapped in try/except at this level (the outer try at line 2200 catches it, but this line is AFTER the decision UPDATE at 2202, so the decision is already partially mutated). | BUG |
| G-2 | api/server.py:3183 | GET /api/governance/history — read history | SELECT `SELECT * FROM governance_history` | All | FATAL — table doesn't exist → sqlite3.OperationalError. No try/except. | BUG |
| G-3 | api/server.py:5260 | POST /api/control-room/fix-data/{type}/{id}/resolve — log resolution | INSERT via raw `cur.execute()` | `id, decision_id, action, type, target_id, processed_by, created_at` | FATAL — table doesn't exist. Uses raw cursor on a separate connection → sqlite3.OperationalError. Caught by function-level try/except at line ~5270. | BUG |

**Wrong-table references: 3 occurrences. All 3 are BUGS.**

Column mismatch analysis (even if table existed): `governance_audit_log` has columns (id, timestamp, action, actor, subject_identifier, details, ip_address, created_at). The server.py INSERTs use (decision_id, type, target_id, processed_by, side_effects) — none of which exist on `governance_audit_log` either. So the fix requires BOTH renaming the table AND remapping columns.

### 4b. References to `governance_audit_log` (correct table name)

| # | File:Line | Context | Operation | Classification |
|---|---|---|---|---|
| G-C1 | lib/schema.py:1221 | TABLES definition | Schema | Source of truth |
| G-C2 | lib/governance/audit_log.py:63 | `CREATE TABLE IF NOT EXISTS governance_audit_log` | DDL (inline CREATE, redundant with schema_engine) | Structural issue — inline CREATE duplicates schema.py. Not a column bug. |
| G-C3 | lib/governance/audit_log.py:112 | INSERT into `governance_audit_log` | INSERT with columns: id, timestamp, action, actor, subject_identifier, details, ip_address, created_at | CLEAN — all 8 columns match schema exactly. |
| G-C4 | lib/governance/audit_log.py:162 | `SELECT * FROM governance_audit_log WHERE 1=1` | SELECT | CLEAN |
| G-C5 | lib/governance/audit_log.py:216 | `SELECT COUNT(*) FROM governance_audit_log WHERE 1=1` | SELECT | CLEAN |
| G-C6 | lib/governance/subject_access.py:320 | Exclusion check — skip audit_log in SAR scans | Logic | CLEAN |

**Correct-table references: 5 occurrences (excluding schema definition). 0 BUGS.**

### 4c. Governance family summary

| Category | Total | Bugs | Clean |
|---|---|---|---|
| Wrong table (`governance_history`) | 3 | 3 | 0 |
| Correct table (`governance_audit_log`) | 5 | 0 | 5 |
| **Total** | **8** | **3** | **5** |

Key finding: The entire `governance_history` usage in `server.py` is a parallel, incompatible schema. G-1/G-2/G-3 expect columns (decision_id, type, target_id, processed_by, side_effects) while the actual `governance_audit_log` uses (timestamp, action, actor, subject_identifier, details, ip_address). The fix must either: (a) add these columns to `governance_audit_log`, or (b) remap server.py's data to fit the existing audit_log schema (preferred — `actor`≈`processed_by`, `details`≈JSON of the rest).

## Phase 5: Smaller known families

### 5a. `saved_filters` (missing table)

| # | File:Line | Context | Operation | Runtime | Classification |
|---|---|---|---|---|---|
| SF-1 | api/server.py:2738 | GET /api/filters | SELECT `SELECT * FROM saved_filters ORDER BY name` | FATAL — table does not exist → sqlite3.OperationalError | BUG |

**Total: 1 occurrence. 1 BUG.** Frontend (`SavedFilterSelector.tsx`) fetches this endpoint. Table must be created in schema.py.

### 5b. `actions` table — column mismatches

Schema: actions has 13 columns: id, type, target_system, payload, status, requires_approval, approved_by, approved_at, executed_at, result, error, retry_count, created_at.

#### INSERTs into `actions`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| A-I1 | lib/executor/handlers/notification.py:142 | _log_action() — log notification action | `domain`, `action_type`, `target_id`, `data` | id, result, status, created_at | FATAL — 4 non-existent columns. Also omits `type` (NOT NULL) and `payload` (NOT NULL). | BUG |
| A-I2 | lib/executor/handlers/delegation.py:267 | _log_action() — log delegation action | `domain`, `action_type`, `target_id`, `data` | id, result, status, created_at | FATAL — same 4 bad columns, same 2 missing NOT NULLs. | BUG |
| A-I3 | lib/actions/action_framework.py:464 | _store_proposal() — store action proposal | `target_entity`, `target_id`, `risk_level`, `source`, `confidence_score` | id, type, payload, requires_approval, status, approved_by, approved_at, created_at | FATAL — 5 non-existent columns. | BUG |
| A-I4 | lib/executor/engine.py:223 | queue_action() — queue new action | — | id, type, target_system, payload, status, requires_approval, created_at | All columns exist. | CLEAN |
| A-I5 | lib/reasoner/decisions.py:286 | _create_action_from_decision() | — | id, type, target_system, payload, status, requires_approval, approved_at, created_at | All columns exist. | CLEAN |
| A-I6 | lib/executor/handlers/task.py:247 | _log_action() | — | id, type, target_system, payload, status, requires_approval, result, created_at | All columns exist. **This is the correct _log_action pattern.** | CLEAN |

**INSERTs total: 6 occurrences. 3 BUGS (A-I1 through A-I3), 3 CLEAN (A-I4 through A-I6).**

Note: A-I1 and A-I2 are copy-paste clones of the same wrong `_log_action()` pattern. A-I6 (`task.py`) is the correct version.

#### UPDATEs on `actions`

| # | File:Line | Context | Bad Columns | Good Columns | Runtime | Classification |
|---|---|---|---|---|---|---|
| A-U1 | lib/actions/action_framework.py:282 | reject_action() | `rejected_by`, `rejection_reason` | status | FATAL — 2 non-existent columns. | BUG |
| A-U2 | lib/executor/engine.py:208 | execute_action() | — | status, result, executed_at, error, retry_count | All exist. | CLEAN |
| A-U3 | lib/executor/engine.py:246 | approve_action() | — | status, approved_by, approved_at | All exist. | CLEAN |
| A-U4 | lib/executor/engine.py:265 | reject_action() | — | status, error | Both exist. | CLEAN |
| A-U5 | lib/actions/action_framework.py:267 | approve_action() | — | status, approved_by, approved_at, payload | All exist. | CLEAN |
| A-U6 | lib/actions/action_framework.py:334 | execute_action() — mark executing | — | status | Exists. | CLEAN |
| A-U7 | lib/actions/action_framework.py:402 | execute_action() — store result | — | status, result, executed_at, error | All exist. | CLEAN |

**UPDATEs total: 7 occurrences. 1 BUG (A-U1), 6 CLEAN (A-U2 through A-U7).**

#### SELECTs on `actions`

| # | File:Line | Context | Bad Columns | Classification |
|---|---|---|---|---|
| A-S1 | lib/actions/action_framework.py:450 | get_action_history() — `WHERE target_id = ?` in raw SQL | `target_id` does not exist on actions table | BUG — sqlite3.OperationalError. |
| A-S2 | lib/actions/action_framework.py:422 | get_pending_actions() | — | CLEAN (uses status, type) |
| A-S3 | lib/actions/action_framework.py:485 | _get_proposal() — store.get() by id | — | CLEAN |
| A-S4 | lib/executor/engine.py:242 | approve_action() — store.get() by id | — | CLEAN |
| A-S5 | lib/executor/engine.py:261 | reject_action() — store.get() by id | — | CLEAN |

**SELECTs total: 5 occurrences. 1 BUG (A-S1), 4 CLEAN.**

#### Actions family summary

| Category | Total | Bugs | Clean |
|---|---|---|---|
| INSERTs | 6 | 3 | 3 |
| UPDATEs | 7 | 1 | 6 |
| SELECTs | 5 | 1 | 4 |
| **Total** | **18** | **5** | **13** |

Distinct bad columns: `domain`, `action_type`, `target_id`, `data` (from _log_action clones), `target_entity`, `risk_level`, `source`, `confidence_score` (from _store_proposal), `rejected_by`, `rejection_reason` (from reject) — 10 phantom columns total.

## Phase 6: Adjacent-family automated sweep

Method: For every table referenced in failing endpoints, diff all INSERT/UPDATE/SELECT column names against schema.py. Also check for tables referenced that don't exist in TABLES dict.

### 6a. `entity_links` — critical schema divergence

**lib/schema.py** defines 7 columns: id (INTEGER PK), from_artifact_id, to_entity_type, to_entity_id, confidence, method, created_at.

**lib/v4/entity_link_service.py** and **lib/migrations/v4_milestone1_truth_proof.py** use a different 12-column schema: link_id (TEXT PK), from_artifact_id, to_entity_type, to_entity_id, method, confidence, confidence_reasons, status, created_at, updated_at, confirmed_by, confirmed_at.

| # | File:Line | Operation | Bad Columns | Classification |
|---|---|---|---|---|
| EL-1 | lib/v4/entity_link_service.py:144 | INSERT | `link_id` (PK mismatch — schema has `id`), `confidence_reasons`, `status`, `updated_at` | BUG — 4 extra columns |
| EL-2 | lib/v4/entity_link_service.py:116 | UPDATE | `confidence_reasons`, `updated_at` + `WHERE link_id=?` | BUG — 2 extra columns + wrong PK name |
| EL-3 | lib/v4/entity_link_service.py:199 | UPDATE | `status`, `confirmed_by`, `confirmed_at`, `updated_at` + `WHERE link_id=?` | BUG — 4 extra columns |
| EL-4 | lib/v4/entity_link_service.py:225 | UPDATE | `status`, `confirmed_by`, `confirmed_at`, `updated_at` + `WHERE link_id=?` | BUG — same 4 |
| EL-5 | api/spec_router.py:2286 | UPDATE | `status`, `confirmed_by`, `confirmed_at` + `WHERE link_id=?` | BUG |
| EL-6 | api/server.py:5179 | UPDATE | `updated_at` + `WHERE id=?` (correct PK, but `updated_at` doesn't exist) | BUG |
| EL-7 | lib/entity_link_confirmer.py:66 | UPDATE | `status`, `confirmed_by`, `confirmed_at`, `updated_at` + `WHERE status=?` | BUG |
| EL-8 | lib/v4/entity_link_service.py:103 | SELECT | `link_id`, `status` in SELECT list | BUG — columns don't exist |
| EL-9 | lib/v4/entity_link_service.py:256 | SELECT | `link_id`, `confidence_reasons`, `status` | BUG |
| EL-10 | lib/v4/entity_link_service.py:299 | SELECT | `link_id`, `confidence_reasons`, `status` | BUG |
| EL-11 | scripts/validate_data_foundation.py:177 | SELECT | `WHERE status='confirmed'` | BUG |

**Root cause:** The migration `v4_milestone1_truth_proof.py` defines the full schema but `lib/schema.py` TABLES["entity_links"] was never updated to match. schema_engine.converge() uses the 7-column version.

**Resolution:** Update TABLES["entity_links"] in schema.py to match the 12-column migration schema. converge() will ALTER TABLE ADD COLUMN for the missing 5 columns. The PK mismatch (id vs link_id) requires a separate migration or acceptance of dual-key access.

### 6b. `insights.severity` — missing column

| # | File:Line | Operation | Classification |
|---|---|---|---|
| INS-1 | api/server.py:2997 | SELECT `ORDER BY severity DESC` | BUG — column doesn't exist → sqlite3.OperationalError |
| INS-2 | api/server.py:3388 | Python filter `a.get("severity")` | BENIGN — .get() returns None, no crash, but wrong behavior (no anomalies shown) |

**Resolution:** Add `("severity", "TEXT DEFAULT 'medium'")` to TABLES["insights"] in schema.py.

### 6c. `identities` — wrong table name

The schema defines `client_identities` (id, client_id, identity_type, identity_value, source, confidence, verified, verified_at, created_at, updated_at). No `identities` table exists.

| # | File:Line | Operation | Classification |
|---|---|---|---|
| ID-1 | api/server.py:4964 | `CREATE TABLE IF NOT EXISTS identities(...)` inline with WRONG schema (id, display_name, source, canonical_id, confidence_score) | BUG — creates a shadow table that doesn't match client_identities |
| ID-2 | api/server.py:4988 | SELECT from `identities` | BUG — queries shadow table |
| ID-3 | api/server.py:5167 | UPDATE `identities` | BUG — updates shadow table |
| ID-4 | api/spec_router.py:1561 | SELECT from `identities` | BUG — table may not exist (depends on fix-data endpoint having been called first) |
| ID-5 | api/spec_router.py:2281 | UPDATE `identities SET confidence_score = 1.0` | BUG — same |

**Resolution:** Rewrite to use `client_identities` with correct columns, remove inline CREATE TABLE.

### 6d. `couplings` — querying wrong table

spec_router.py:1507 queries `entity_links` for coupling-specific columns (coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, coupling_type, strength, why). None of these exist on entity_links.

| # | File:Line | Operation | Classification |
|---|---|---|---|
| CP-1 | api/spec_router.py:1507 | SELECT from entity_links with coupling columns | BUG — 7 non-existent columns |

**Resolution:** Wire to CouplingService which manages its own `couplings` table, or add `couplings` to schema.py TABLES dict.

### 6e. `item_history` — evidence endpoint column mismatch

`item_history` exists (created by store.py inline SQL) with columns: id, item_id, timestamp, change, changed_by.

| # | File:Line | Operation | Bad Columns | Classification |
|---|---|---|---|---|
| IH-1 | api/spec_router.py:2503 | SELECT `e.artifact_id, e.excerpt_text, e.context_json, e.item_type` from item_history | 4 non-existent columns | BUG |
| IH-2 | api/spec_router.py:2387 | INSERT into item_history (id, item_id, timestamp, change, changed_by) | — | CLEAN — correct columns for adding issue notes |

### 6f. `cycle_logs` — test data mismatch

| # | File:Line | Operation | Bad Columns | Classification |
|---|---|---|---|---|
| CL-T1 | tests/test_sync_schedule.py:117 | INSERT (source, status, completed_at) | All 3 non-existent | TEST BUG — test creates data with wrong columns |
| CL-T2 | tests/test_sync_schedule.py:133 | INSERT (source, status, completed_at) | Same 3 | TEST BUG |
| CL-T3 | tests/test_sync_schedule.py:161 | INSERT (source, status, completed_at) | Same 3 | TEST BUG |
| CL-T4 | tests/test_sync_schedule.py:177 | INSERT (source, status, completed_at) | Same 3 | TEST BUG |

### 6g. Adjacent sweep summary

| Family | Bugs | Clean |
|---|---|---|
| entity_links divergence | 11 | 0 |
| insights.severity | 2 | 0 |
| identities (wrong table) | 5 | 0 |
| couplings (wrong table) | 1 | 0 |
| item_history (evidence) | 1 | 1 |
| cycle_logs (test only) | 4 | 0 |
| **Total** | **24** | **1** |

## Phase 7: Frontend contract lock

For each TypeScript interface that maps to a failing endpoint, map field-by-field to what the backend actually returns.

### 7a. Notification (api.ts:1197)

| TS Field | TS Type | Backend Source | Status |
|---|---|---|---|
| id | string | notifications.id | OK |
| type | string | notifications.type | OK |
| message | string | No `message` column — schema has `title` + `body` | MISMATCH |
| task_id | string\|null | Column doesn't exist (phantom) | BROKEN |
| target_id | string\|null | Column doesn't exist (phantom) | BROKEN |
| dismissed | number | Column doesn't exist — plan adds it | BROKEN until PR1 |
| dismissed_at | string\|null | Column doesn't exist — plan adds it | BROKEN until PR1 |
| created_at | string | notifications.created_at | OK |

**Contract fix:** After PR1 adds `dismissed`/`dismissed_at`, endpoint returns `SELECT *` giving all schema columns. Frontend `message` must map to `title` (or backend adds alias). `task_id`/`target_id` will be absent unless added to schema — frontend must tolerate null.

### 7b. EmailItem (api.ts:1288)

| TS Field | TS Type | Backend Source | Status |
|---|---|---|---|
| id | string | communications.id | OK |
| subject | string\|null | communications.subject | OK |
| sender | string\|null | No `sender` column — schema has `from_email`, `from_name` | MISMATCH |
| recipient | string\|null | No `recipient` column — schema has `to_emails` | MISMATCH |
| body | string\|null | No `body` column — schema has `body_text` | MISMATCH |
| received_at | string\|null | communications.received_at | OK |
| actionable | number | No `actionable` column — schema has `requires_response` | MISMATCH |
| processed | number | communications.processed | OK |
| type | string | No `type` column on communications | BROKEN |

**Contract fix:** Endpoint queries `WHERE type = 'email'` — column doesn't exist. Fix: `WHERE from_email IS NOT NULL`. Backend must alias: `from_email AS sender`, `to_emails AS recipient`, `body_text AS body`, `requires_response AS actionable` in SELECT.

### 7c. Evidence (types/api.ts:259)

| TS Field | TS Type | Backend Source | Status |
|---|---|---|---|
| id | string | item_history.id | OK |
| artifact_id | string | No `artifact_id` on item_history | BROKEN |
| excerpt_text | string | No `excerpt_text` on item_history | BROKEN |
| context_json | string\|null | No `context_json` on item_history | BROKEN |
| created_at | string | item_history has `timestamp` not `created_at` | MISMATCH |
| source | string | JOIN wrong — communications has no `occurred_at` | BROKEN |
| artifact_type | string | Aliased from communications.type — doesn't exist | BROKEN |
| occurred_at | string | No `occurred_at` on communications | BROKEN |

**Contract fix:** Rebuild evidence endpoint on `artifacts` + `entity_links` join. Return artifact_id, type, source, occurred_at from artifacts; confidence, method from entity_links. Frontend Evidence interface needs revision OR backend aliases to match.

### 7d. FixData (types/api.ts:240)

| TS Field | TS Type | Backend Source | Status |
|---|---|---|---|
| identity_conflicts | Array | Queries `identities` table — doesn't exist. Created inline by server.py:4964. | FRAGILE |
| ambiguous_links | Array | Queries `entity_links` with inline CREATE that conflicts with schema.py | BROKEN |
| missing_mappings | unknown[] | Not returned by backend (both v1 and v2 omit this field) | BROKEN |
| total | number | Returned by server.py but not spec_router.py | BROKEN on v2 |

**Contract fix:** Rewrite fix-data to use `client_identities` (real table). Return `missing_mappings: []` and `total: N` to match frontend. Remove inline CREATE TABLE.

### 7e. GovernanceResponse (api.ts:1371)

| TS Field | TS Type | Backend Source | Status |
|---|---|---|---|
| domains | GovernanceDomain[] | `governance.get_all_domains()` — method doesn't exist | BROKEN |
| emergency_brake | boolean | `governance.is_emergency_brake_active()` — method doesn't exist | BROKEN |
| summary | Record | Not returned at all | BROKEN |

**Contract fix:** Use `governance.get_status()` which returns domain info. Map to GovernanceResponse interface.

---

## A. Prior Misses

The original `endpoint-fix-audit.md` documented 41 bugs across 23 endpoints. This closure audit found the following categories were ABSENT from that count:

1. **Actions table family (5 bugs: A-I1, A-I2, A-I3, A-U1, A-S1)** — notification.py and delegation.py `_log_action()` use wrong column names (domain, action_type, target_id, data vs type, target_system, payload). action_framework.py `_store_proposal()` adds 5 phantom columns. `reject_action()` uses 2 phantom columns. `get_action_history()` queries non-existent `target_id`.

2. **entity_links schema divergence (11 bugs: EL-1 through EL-11)** — lib/schema.py has 7 columns, entity_link_service.py uses 12 columns from the migration. PK is `id` in schema, `link_id` in code. 5 missing columns: confidence_reasons, status, updated_at, confirmed_by, confirmed_at.

3. **identities table misname (5 bugs: ID-1 through ID-5)** — server.py and spec_router.py reference `identities` (doesn't exist); correct table is `client_identities` with different columns.

4. **item_history evidence mismatch (1 bug: IH-1)** — spec_router.py evidence endpoint queries item_history for columns (artifact_id, excerpt_text, context_json, item_type) that don't exist on it.

5. **couplings endpoint wrong table (1 bug: CP-1)** — spec_router.py queries entity_links for 7 coupling-specific columns that don't exist.

6. **insights.severity (2 bugs: INS-1, INS-2)** — ORDER BY severity on a column that doesn't exist.

7. **cycle_logs test data (4 test bugs: CL-T1 through CL-T4)** — test inserts with wrong columns.

**Prior count: 41. New findings from closure audit: 21 additional production bugs + 4 test bugs = 25. Grand total: 62 distinct production bugs + 4 test bugs.** (See Section C for full reconciliation and explicit overlap mapping showing which 22 of the 43 occurrence-table bugs are re-enumerations of original-41 bugs.)

---

## B. New Findings (21 production + 4 test)

Listed below are bugs NOT in the original endpoint-fix-audit.md, verified by explicit mapping against all 41 original IDs (A1-A18, B1-B8, C1-C3, D1-D6, E1-E2, F1-F3, G1a-G1e). Bugs that DO map to the original 41 are excluded and tracked in Section C overlap table.

| ID | Phase | File:Line | Table | Bug | Severity |
|---|---|---|---|---|---|
| D-I1 | 3a | server.py:863 | decisions | INSERT with type, target_id, proposed_changes, reason (none exist) + omits domain (NOT NULL) | high |
| D-I2 | 3a | server.py:1083 | decisions | Same 4 bad columns + omits domain | high |
| D-I3 | 3a | server.py:1257 | decisions | Same 4 bad columns + omits domain | high |
| D-U1 | 3b | server.py:2202 | decisions | UPDATE with processed_by (doesn't exist) | high |
| D-U2 | 3b | server.py:3105 | decisions | UPDATE with modifications (doesn't exist) | high |
| A-I1 | 5b | notification.py:142 | actions | INSERT with domain, action_type, target_id, data (none exist) | high |
| A-I2 | 5b | delegation.py:267 | actions | INSERT clone of A-I1 | high |
| A-I3 | 5b | action_framework.py:464 | actions | INSERT with target_entity, target_id, risk_level, source, confidence_score | high |
| A-U1 | 5b | action_framework.py:282 | actions | UPDATE with rejected_by, rejection_reason | high |
| A-S1 | 5b | action_framework.py:450 | actions | SELECT WHERE target_id = ? (doesn't exist) | medium |
| EL-1 | 6a | entity_link_service.py:144 | entity_links | INSERT with link_id PK + 3 missing columns | critical |
| EL-2 | 6a | entity_link_service.py:116 | entity_links | UPDATE with confidence_reasons, updated_at | critical |
| EL-3 | 6a | entity_link_service.py:199 | entity_links | UPDATE status, confirmed_by, confirmed_at, updated_at | critical |
| EL-4 | 6a | entity_link_service.py:225 | entity_links | UPDATE (reject) — same 4 columns | critical |
| EL-7 | 6a | entity_link_confirmer.py:66 | entity_links | UPDATE status, confirmed_by, confirmed_at, updated_at | high |
| EL-8 | 6a | entity_link_service.py:103 | entity_links | SELECT link_id, status (don't exist) | high |
| EL-9 | 6a | entity_link_service.py:256 | entity_links | SELECT with confidence_reasons, status | high |
| EL-10 | 6a | entity_link_service.py:299 | entity_links | SELECT with confidence_reasons, status | high |
| EL-11 | 6a | validate_data_foundation.py:177 | entity_links | SELECT WHERE status='confirmed' | medium |
| INS-2 | 6b | server.py:3388 | insights | Python .get("severity") — benign but wrong | low |
| ID-2 | 6c | server.py:4988 | identities | SELECT from shadow table | high |
| CL-T1 | 6f | test_sync_schedule.py:117 | cycle_logs | Test INSERT with wrong columns | low (test) |
| CL-T2 | 6f | test_sync_schedule.py:133 | cycle_logs | Same | low (test) |
| CL-T3 | 6f | test_sync_schedule.py:161 | cycle_logs | Same | low (test) |
| CL-T4 | 6f | test_sync_schedule.py:177 | cycle_logs | Same | low (test) |

**Removed from prior version:**
- N-U3, N-U4: Already fixed in source (audit fix comments at engine.py:210-213 and 402-404)
- EL-5→A15, EL-6→A18, ID-1→D1, ID-3→A17, ID-4→B4, ID-5→A16/B7, CP-1→C1, IH-1→B3, INS-1→A5: Moved to overlap (were in original 41)

---

## C. Totals Reconciliation

### Corrected totals (hostile audit revision)

| Metric | Value | Derivation |
|---|---|---|
| Total occurrences scanned (Phases 2-6) | 92 | 19 notif + 21 decisions + 8 governance + 1 saved_filters + 18 actions + 11 entity_links + 2 insights + 5 identities + 1 couplings + 2 item_history + 4 cycle_logs |
| Confirmed bugs in occurrence tables | 47 | 9 notif + 5 decisions + 3 governance + 1 saved_filters + 5 actions + 11 entity_links + 2 insights + 5 identities + 1 couplings + 1 item_history + 4 cycle_logs(test) |
| Clean occurrences | 45 | 92 - 47 |
| Bugs that overlap with original 41 | 22 | See explicit mapping table below |
| NEW production bugs (not in original 41) | 21 | 43 production bugs - 22 overlap = 21 new |
| Test-only bugs | 4 | CL-T1..4 |
| **Grand total distinct production bugs** | **41 + 21 = 62** | Original 41 + 21 net new |
| Test bugs | 4 | Separate — not in production code |

### Arithmetic check

Occurrence-table bugs (47) = overlap-with-original (22) + new-production (21) + test-only (4) = 47. ✓

Grand total = original 41 + 21 new = 62 production bugs. The original 41 already counted the 22 overlapping bugs plus 19 additional endpoint bugs found in the prior audit pass that were NOT re-enumerated as occurrences in this closure audit (paginated_router column mismatches A1-A4, email WHERE type A7, calendar join A9, control-room clients A14, insights category A13, email mark-actionable A10, plus inline CREATE D2-D6, missing methods E1-E2, schema gaps F2-F3).

### Explicit overlap mapping (22 bugs)

Each closure-audit bug below maps to a specific original-41 bug ID from `endpoint-fix-audit.md`:

| Closure ID | Original ID | Match type | Evidence |
|---|---|---|---|
| N-I1 | G1a | EXACT | Same INSERT at server.py:1127→1132, same recipient_id bug |
| N-I2 | G1b | EXACT | Same INSERT at server.py:1303→1308 |
| N-I3 | G1c | EXACT | Same INSERT at server.py:1322→1327 |
| N-I4 | G1d | EXACT | Same INSERT at server.py:2245→2250 |
| N-I5 | G1e | EXACT | Same INSERT at server.py:2277→2282 |
| N-U1 | A11 | EXACT | Same UPDATE at server.py:3039→3042, dismissed column |
| N-U2 | A12 | EXACT | Same UPDATE at server.py:3052→3056 |
| N-S1 | A6 | EXACT | Same WHERE at server.py:3008, dismissed column |
| N-S2 | A12 (partial) | OVERLAP | Same endpoint dismiss-all, SELECT portion of A12 |
| G-1 | B8 | EXACT | Same INSERT governance_history at server.py:2314→2315 |
| G-2 | B1 | EXACT | Same SELECT governance_history at server.py:3183 |
| G-3 | B6 | EXACT | Same INSERT governance_history at server.py:5260 |
| SF-1 | B5/F1 | EXACT | Same missing saved_filters table at server.py:2738 |
| EL-5 | A15 | EXACT | Same UPDATE entity_links at spec_router.py:2286, same 4 wrong columns |
| EL-6 | A18 | EXACT | Same UPDATE entity_links at server.py:5179 (line shifted from 5247), updated_at |
| ID-1 | D1 | EXACT | Same inline CREATE identities at server.py:4950→4963 |
| ID-3 | A17 | EXACT | Same UPDATE identities at server.py:5167 (line shifted from 5233) |
| ID-4 | B4 | EXACT | Same SELECT from identities at spec_router.py:1561→1560 |
| ID-5 | A16/B7 | EXACT | Same UPDATE identities at spec_router.py:2281 |
| CP-1 | C1 | EXACT | Same SELECT coupling columns from entity_links at spec_router.py:1507 |
| IH-1 | B3 | EXACT | Same SELECT from item_history at spec_router.py:2503→2505 |
| INS-1 | A5 | EXACT | Same ORDER BY severity at server.py:2997 |

### Genuinely new production bugs (21)

| Closure ID | Why not in original 41 |
|---|---|
| D-I1 | PUT /api/tasks/{id} decisions INSERT — governance block path not in original scope |
| D-I2 | POST /api/tasks/{id}/delegate decisions INSERT — not in original scope |
| D-I3 | POST /api/tasks/{id}/escalate decisions INSERT — not in original scope |
| D-U1 | POST /api/decisions/{decision_id} processed_by UPDATE — not in original scope |
| D-U2 | POST /api/approvals/{decision_id}/modify modifications UPDATE — not in original scope |
| A-I1 | notification.py:142 _log_action() — lib/ code, not endpoint handler |
| A-I2 | delegation.py:267 _log_action() — lib/ code, not endpoint handler |
| A-I3 | action_framework.py:464 _store_proposal() — lib/ code |
| A-U1 | action_framework.py:282 reject_action() — lib/ code |
| A-S1 | action_framework.py:450 get_action_history() — lib/ code |
| EL-1 | entity_link_service.py:144 — V4 service layer, not endpoint |
| EL-2 | entity_link_service.py:116 — V4 service layer |
| EL-3 | entity_link_service.py:199 — V4 service layer |
| EL-4 | entity_link_service.py:225 — V4 service layer |
| EL-7 | entity_link_confirmer.py:66 — background service |
| EL-8 | entity_link_service.py:103 — V4 service layer |
| EL-9 | entity_link_service.py:256 — V4 service layer |
| EL-10 | entity_link_service.py:299 — V4 service layer |
| EL-11 | validate_data_foundation.py:177 — validation script |
| INS-2 | server.py:3388 Python .get() — benign, not a SQL crash |
| ID-2 | server.py:4988 SELECT from shadow table — consequence of D1, not separately listed |

### Correction from prior version

Prior document claimed 18 overlap and 27 new (grand total 68). Hostile audit found:
- **N-U3/N-U4 removed**: Already fixed in source. Prior document counted these as 2 new bugs. They are 0. (-2)
- **9 bugs reclassified from new to overlap**: EL-5→A15, EL-6→A18, ID-1→D1, ID-3→A17, ID-4→B4, ID-5→A16/B7, CP-1→C1, IH-1→B3, INS-1→A5. These were in the original 41 but the prior document failed to map them. (-9 new, +9 overlap)
- **5 bugs reclassified from overlap to new**: D-I1..3 and D-U1..2 were counted as overlap (18 included them). They are NOT in the original 41 — the decisions INSERT/UPDATE bugs at server.py:863/1083/1257/2202/3105 were not in categories A-G. (+5 new, -5 overlap)
- Net: overlap 18-5+9=22, new 27+5-9-2=21. Grand total: 41+21=62 (was 68).

---

## D. Full Occurrence Tables with Acceptance Columns

Every bug row includes: ID, file:line, function name, endpoint/execution path, referenced columns, schema reality, runtime classification, fix owner (PR bucket).

Runtime classification key:
- **FATAL** — store.insert()/store.update()/raw SQL with non-existent column → sqlite3.OperationalError, no try/except → crashes endpoint
- **CAUGHT-DEGRADED** — same crash mechanism but inside try/except → side-effect silently lost, parent operation succeeds
- **MIGRATION-DEP** — query is correct once PR1 schema changes land
- **BENIGN** — .get() on dict returns None; no crash but wrong behavior
- **TEST** — bug is in test code only

### D1. Notifications family (19 occurrences, 9 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Referenced Columns (bad in bold) | Schema Reality | Runtime | Fix Owner | Original-41 ID |
|---|---|---|---|---|---|---|---|---|
| N-I1 | server.py:1127 | delegate_task() | POST /api/tasks/{id}/delegate | id, type, title, body, created_at, **recipient_id**, **task_id**, **dismissed** | 12 cols; no recipient_id, task_id, dismissed | FATAL (re-raised as HTTP 500 at :1157) | PR3 | → G1a |
| N-I2 | server.py:1303 | escalate_task() | POST /api/tasks/{id}/escalate (target notif) | id, type, title, body, created_at, priority, **recipient_id**, **task_id**, **dismissed** | Same | FATAL (re-raised as HTTP 500) | PR3 | → G1b |
| N-I3 | server.py:1322 | escalate_task() | POST /api/tasks/{id}/escalate (original notif) | id, type, title, body, created_at, **recipient_id**, **task_id**, **dismissed** | Same | FATAL (re-raised as HTTP 500) | PR3 | → G1c |
| N-I4 | server.py:2245 | api_decision() | POST /api/decisions/{decision_id} (delegation side-effect) | id, type, title, body, created_at, **recipient_id**, **task_id**, **dismissed** | Same | CAUGHT-DEGRADED (except at :2258) | PR3 | → G1d |
| N-I5 | server.py:2277 | api_decision() | POST /api/decisions/{decision_id} (escalation side-effect) | id, type, title, body, created_at, priority, **recipient_id**, **task_id**, **dismissed** | Same | CAUGHT-DEGRADED (except at :2291) | PR3 | → G1e |
| N-U1 | server.py:3039 | dismiss_notification() | POST /api/notifications/{id}/dismiss | **dismissed**, **dismissed_at** | Neither exists | FATAL → MIGRATION-DEP (PR1 adds them) | PR1+PR3 | → A11 |
| N-U2 | server.py:3056 | dismiss_all_notifications() | POST /api/notifications/dismiss-all | **dismissed**, **dismissed_at** | Neither exists | FATAL → MIGRATION-DEP | PR1+PR3 | → A12 |
| N-S1 | server.py:3008 | get_notifications() | GET /api/notifications | WHERE **dismissed** = 0 | Column doesn't exist → OperationalError | FATAL → MIGRATION-DEP | PR1+PR3 | → A6 |
| N-S2 | server.py:3052 | dismiss_all_notifications() | POST /api/notifications/dismiss-all (fetch step) | WHERE **dismissed** = 0 | Same | FATAL → MIGRATION-DEP | PR1+PR3 | → A12 (partial) |

**N-U3/N-U4 removed:** engine.py:207 and engine.py:399 were ALREADY FIXED (delivery_channel/delivery_id removed with audit fix comments at lines 210-213 and 402-404). Not counted.

Clean: N-I6 (autonomous_loop.py:1547), N-I7 (delegation.py:152), N-I8 (delegation.py:234), N-I9 (notification.py:60), N-I10 (engine.py:476), N-S3 (server.py:3028), N-S4 (server.py:3029), N-S5 (engine.py:515), N-S6 (notification.py:132), N-D1 (notification.py:136). All verified against schema — every column exists.

### D2. Decisions family (21 occurrences, 5 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Referenced Columns (bad in bold) | Schema Reality | Runtime | Fix Owner | Original-41 ID |
|---|---|---|---|---|---|---|---|---|
| D-I1 | server.py:863 | update_task() | PUT /api/tasks/{id} (governance block) | id, description, created_at, **type**, **target_id**, **proposed_changes**, **reason** | 16 cols; none of those 4 exist. Also omits domain (NOT NULL). | FATAL | PR3 | NEW |
| D-I2 | server.py:1083 | delegate_task() | POST /api/tasks/{id}/delegate | Same 4 bad + omits domain | Same | FATAL | PR3 | NEW |
| D-I3 | server.py:1257 | escalate_task() | POST /api/tasks/{id}/escalate | Same 4 bad + omits domain | Same | FATAL | PR3 | NEW |
| D-U1 | server.py:2202 | api_decision() | POST /api/decisions/{decision_id} (approval path) | approved, approved_at, **processed_by** | processed_by doesn't exist | FATAL (re-raised as HTTP 500 at :2350) | PR3 | NEW |
| D-U2 | server.py:3105 | modify_approval() | POST /api/approvals/{decision_id}/modify | approved, approved_at, **modifications** | modifications doesn't exist | FATAL | PR3 | NEW |

Clean: D-I4 (email.py:67), D-I5 (email.py:133), D-I6 (decisions.py:194), D-U3 (server.py:3081), D-U4 (decisions.py:239), D-U5 (decisions.py:255), D-S1..S10 (10 SELECTs, all use valid columns).

### D3. Governance family (8 occurrences, 3 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Referenced Columns (bad in bold) | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|---|
| G-1 | server.py:2314 | api_decision() | POST /api/decisions/{decision_id} (audit log) | INSERT **governance_history**: id, **decision_id**, action, **type**, **target_id**, **processed_by**, **side_effects**, created_at | Table doesn't exist. Even if renamed, 5 of 8 columns don't match governance_audit_log. | FATAL (after partial decision mutation) | PR3 | → B8 |
| G-2 | server.py:3183 | get_governance_history() | GET /api/governance/history | SELECT * FROM **governance_history** | Table doesn't exist | FATAL | PR3 | → B1 |
| G-3 | server.py:5260 | resolve_fix_data() | POST /api/control-room/fix-data/{type}/{id}/resolve | INSERT **governance_history** via raw cursor | Table doesn't exist | CAUGHT-DEGRADED (function-level except at ~:5270) | PR3 | → B6 |

Clean: G-C2 (audit_log.py:63, redundant DDL), G-C3 (audit_log.py:112, correct INSERT), G-C4 (audit_log.py:162, correct SELECT), G-C5 (audit_log.py:216, correct count), G-C6 (subject_access.py:320, exclusion logic).

### D4. Actions family (18 occurrences, 5 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Referenced Columns (bad in bold) | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|---|
| A-I1 | notification.py:142 | _log_action() | Background: notification handler | id, result, status, created_at, **domain**, **action_type**, **target_id**, **data**. Omits type (NOT NULL), payload (NOT NULL). | 13 cols; 4 phantom + 2 NOT NULL missing | FATAL | PR-actions | NEW |
| A-I2 | delegation.py:267 | _log_action() | Background: delegation handler | Same as A-I1 (copy-paste clone) | Same | FATAL | PR-actions | NEW |
| A-I3 | action_framework.py:464 | _store_proposal() | ActionFramework proposal storage (live via POST /api/propose) | id, type, payload, requires_approval, status, approved_by, approved_at, created_at, **target_entity**, **target_id**, **risk_level**, **source**, **confidence_score** | 5 phantom columns | FATAL | PR-actions | NEW |
| A-U1 | action_framework.py:282 | reject_action() | ActionFramework rejection path | status, **rejected_by**, **rejection_reason** | 2 phantom columns | FATAL | PR-actions | NEW |
| A-S1 | action_framework.py:450 | get_action_history() | ActionFramework history query | WHERE **target_id** = ? | Column doesn't exist | FATAL | PR-actions | NEW |

Clean: A-I4 (engine.py:223), A-I5 (decisions.py:286), A-I6 (task.py:247 — correct _log_action pattern), A-U2..U7 (engine.py:208/246/265, action_framework.py:267/334/402), A-S2..S5 (action_framework.py:422/485, engine.py:242/261). All verified.

### D5. Saved Filters (1 occurrence, 1 bug)

| ID | File:Line | Function | Endpoint / Execution Path | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| SF-1 | server.py:2738 | get_filters() | GET /api/filters | Table saved_filters does not exist anywhere | FATAL | PR1 (create table) | → B5/F1 |

### D6. Entity Links divergence (11 occurrences, 11 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Referenced Columns (bad in bold) | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|---|
| EL-1 | entity_link_service.py:144 | create_link() | V4 link creation | **link_id** (PK), from_artifact_id, to_entity_type, to_entity_id, method, confidence, **confidence_reasons**, **status**, created_at, **updated_at** | PK is `id INTEGER`, no link_id/confidence_reasons/status/updated_at | FATAL | PR1 (schema sync) | NEW |
| EL-2 | entity_link_service.py:116 | update_confidence() | V4 confidence update | **confidence_reasons**, **updated_at**, WHERE **link_id**=? | Same | FATAL | PR1 | NEW |
| EL-3 | entity_link_service.py:199 | confirm_link() | V4 confirmation | **status**, **confirmed_by**, **confirmed_at**, **updated_at**, WHERE **link_id**=? | Same | FATAL | PR1 | NEW |
| EL-4 | entity_link_service.py:225 | reject_link() | V4 rejection | **status**, **confirmed_by**, **confirmed_at**, **updated_at**, WHERE **link_id**=? | Same | FATAL | PR1 | NEW |
| EL-5 | spec_router.py:2286 | resolve_fix_data_v2() | POST /api/v2/fix-data/{type}/{id}/resolve | **status**, **confirmed_by**, **confirmed_at**, WHERE **link_id**=? | Same | FATAL | PR1+PR4 | → A15 |
| EL-6 | server.py:5179 | resolve_fix_data() | POST /api/control-room/fix-data/{type}/{id}/resolve | **updated_at**, WHERE id=? (PK correct for schema.py, but `updated_at` doesn't exist) | updated_at doesn't exist | FATAL | PR1+PR3 | → A18 |
| EL-7 | entity_link_confirmer.py:66 | batch_confirm() | Background: link confirmation | **status**, **confirmed_by**, **confirmed_at**, **updated_at**, WHERE **status**=? | Same | FATAL | PR1 | NEW |
| EL-8 | entity_link_service.py:103 | get_links_for_entity() | V4 link query | SELECT **link_id**, **status** in column list | Columns don't exist in schema | FATAL | PR1 | NEW |
| EL-9 | entity_link_service.py:256 | get_unconfirmed_links() | V4 unconfirmed query | SELECT **link_id**, **confidence_reasons**, **status** | Same | FATAL | PR1 | NEW |
| EL-10 | entity_link_service.py:299 | get_links_by_method() | V4 method query | SELECT **link_id**, **confidence_reasons**, **status** | Same | FATAL | PR1 | NEW |
| EL-11 | validate_data_foundation.py:177 | validate() | Script: data validation | WHERE **status**='confirmed' | Column doesn't exist | FATAL | PR1 | NEW |

### D7. Insights severity (2 occurrences, 2 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| INS-1 | server.py:2997 | get_anomalies() | GET /api/anomalies | ORDER BY **severity** — column missing | FATAL | PR1 (add column) | → A5 |
| INS-2 | server.py:3388 | get_control_room() | GET /api/control-room (anomaly subset) | Python .get("severity") on dict | BENIGN (returns None) | PR1 | NEW |

### D8. Identities wrong table (5 occurrences, 5 bugs)

| ID | File:Line | Function | Endpoint / Execution Path | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| ID-1 | server.py:4950 | get_fix_data() | GET /api/control-room/fix-data | Inline CREATE TABLE `identities` (id, display_name, source, canonical_id, confidence_score) | Canonical table is `client_identities` (id, client_id, identity_type, identity_value, created_at) — completely different schema | CREATES SHADOW TABLE | PR3 | → D1 |
| ID-2 | server.py:4988 | get_fix_data() | GET /api/control-room/fix-data (identity query) | SELECT from `identities` | Queries shadow table — always empty on fresh DB | CAUGHT-DEGRADED | PR3 | NEW |
| ID-3 | server.py:5167 | resolve_fix_data() | POST /api/control-room/fix-data/{type}/{id}/resolve | UPDATE `identities` | Updates shadow table — real data in client_identities untouched | CAUGHT-DEGRADED | PR3 | → A17 |
| ID-4 | spec_router.py:1561 | get_fix_data_v2() | GET /api/v2/fix-data | SELECT from `identities` | Table may not exist (depends on v1 having been called first to trigger inline CREATE) | FATAL (order-dependent) | PR4 | → B4 |
| ID-5 | spec_router.py:2281 | resolve_fix_data_v2() | POST /api/v2/fix-data/{type}/{id}/resolve | UPDATE `identities` SET confidence_score = 1.0 | Same order dependency | FATAL (order-dependent) | PR4 | → A16/B7 |

### D9. Couplings wrong table (1 occurrence, 1 bug)

| ID | File:Line | Function | Endpoint / Execution Path | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| CP-1 | spec_router.py:1507 | get_couplings() | GET /api/v2/couplings | SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, coupling_type, strength, why FROM **entity_links** | entity_links has none of these 7 columns. Real data is in `couplings` table managed by CouplingService. | FATAL | PR4 | → C1 |

### D10. Item History evidence (2 occurrences, 1 bug)

| ID | File:Line | Function | Endpoint / Execution Path | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| IH-1 | spec_router.py:2503 | get_evidence() | GET /api/v2/evidence/{type}/{id} | SELECT **artifact_id**, **excerpt_text**, **context_json**, **item_type** FROM item_history | item_history has 5 cols (id, item_id, timestamp, change, changed_by) — 4 queried columns don't exist | FATAL | PR4 | → B3 |

Clean: IH-2 (spec_router.py:2387 — correct columns for issue note insertion).

### D11. Cycle Logs test bugs (4 occurrences, 4 test bugs)

| ID | File:Line | Function | Context | Schema Reality | Runtime | Fix Owner |
|---|---|---|---|---|---|---|
| CL-T1 | test_sync_schedule.py:117 | test_sync_needed_no_recent() | Test INSERT | Uses **source**, **status**, **completed_at** — none exist on cycle_logs (has: id, cycle_number, phase, data, duration_ms, created_at) | TEST | PR6 |
| CL-T2 | test_sync_schedule.py:133 | test_sync_not_needed_recent() | Test INSERT | Same 3 phantom columns | TEST | PR6 |
| CL-T3 | test_sync_schedule.py:161 | test_sync_needed_old_record() | Test INSERT | Same | TEST | PR6 |
| CL-T4 | test_sync_schedule.py:177 | test_sync_not_needed_multiple() | Test INSERT | Same | TEST | PR6 |

### D-summary. Occurrence totals

| Family | Occurrences | Bugs | Clean | Test-only |
|---|---|---|---|---|
| Notifications | 19 | 9 | 10 | 0 |
| Decisions | 21 | 5 | 16 | 0 |
| Governance | 8 | 3 | 5 | 0 |
| Actions | 18 | 5 | 13 | 0 |
| Saved Filters | 1 | 1 | 0 | 0 |
| Entity Links | 11 | 11 | 0 | 0 |
| Insights | 2 | 2 | 0 | 0 |
| Identities | 5 | 5 | 0 | 0 |
| Couplings | 1 | 1 | 0 | 0 |
| Item History | 2 | 1 | 1 | 0 |
| Cycle Logs | 4 | 0 | 0 | 4 |
| **Total** | **92** | **43** | **45** | **4** |

Reconciliation: 43 production bugs + 4 test bugs = 47 total bugs in occurrence tables. 92 - 47 = 45 clean.

Change from prior version: N-U3/N-U4 removed (already fixed in source → 2 fewer occurrences, 2 fewer bugs).

---

## E. entity_links Proof

### Schema comparison (side-by-side)

| Column | schema.py (line 1529) | Migration v4_milestone1_truth_proof.py (line 97) | entity_link_service.py usage | Exists in schema.py? |
|---|---|---|---|---|
| link_id | — | TEXT PRIMARY KEY | PK for all operations | NO |
| id | INTEGER PRIMARY KEY | — | server.py:5179 only | YES (but wrong type for V4) |
| from_artifact_id | TEXT | TEXT NOT NULL REFERENCES artifacts(artifact_id) | INSERT, SELECT | YES |
| to_entity_type | TEXT NOT NULL | TEXT NOT NULL | INSERT, SELECT, WHERE | YES |
| to_entity_id | TEXT NOT NULL | TEXT NOT NULL | INSERT, SELECT, WHERE | YES |
| method | TEXT DEFAULT 'system' | TEXT NOT NULL | INSERT, SELECT | YES |
| confidence | REAL DEFAULT 1.0 | REAL NOT NULL CHECK(>=0, <=1) | INSERT, UPDATE, SELECT | YES |
| confidence_reasons | — | TEXT DEFAULT '[]' | INSERT, UPDATE, SELECT | NO |
| status | — | TEXT NOT NULL DEFAULT 'proposed' | INSERT, UPDATE, SELECT, WHERE | NO |
| created_at | TEXT NOT NULL DEFAULT datetime('now') | TEXT NOT NULL DEFAULT datetime('now') | INSERT | YES |
| updated_at | — | TEXT NOT NULL DEFAULT datetime('now') | UPDATE (every write) | NO |
| confirmed_by | — | TEXT | UPDATE (confirm/reject) | NO |
| confirmed_at | — | TEXT | UPDATE (confirm/reject) | NO |

### PK mismatch detail

schema.py: `id INTEGER PRIMARY KEY` (autoincrement integer).
Migration: `link_id TEXT PRIMARY KEY` (UUID string).
entity_link_service.py: generates `link_id = str(uuid.uuid4())` and uses `WHERE link_id = ?` for all operations.
server.py:5179: uses `WHERE id = ?` — the ONLY caller using the integer PK.

converge() cannot rename a PK column or change its type. Resolution requires either: (a) drop-and-recreate with data migration, or (b) keep `id INTEGER` as vestigial and add `link_id TEXT UNIQUE NOT NULL` as the application PK with all V4 code using `link_id`. Option (b) is safer for existing data.

### Why 11 bugs

Every INSERT, UPDATE, and SELECT in entity_link_service.py (7 methods), entity_link_confirmer.py (1 method), spec_router.py (1 endpoint), server.py (1 endpoint), and validate_data_foundation.py (1 script) references at least one column that does not exist in schema.py's TABLES["entity_links"]. All 11 crash with sqlite3.OperationalError at runtime unless the migration has been run separately to create the table with the full schema before converge() touches it.

---

## F. identities Proof

### Two schemas, two tables

| Property | `identities` (inline CREATE in server.py:4950) | `client_identities` (schema.py:381) |
|---|---|---|
| Created by | Inline `CREATE TABLE IF NOT EXISTS` inside get_fix_data() | schema.py TABLES dict → converge() at startup |
| PK | id TEXT PRIMARY KEY | id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))) |
| Columns | id, display_name, source, canonical_id, confidence_score | id, client_id, identity_type, identity_value, created_at |
| Column overlap | id only | id only |
| Purpose | Identity conflict resolution | Canonical client identity storage |
| Data flow | Written to only if get_fix_data() is called; no other code writes to it | Written to by client onboarding, identity resolution |

### Call-order dependency

1. `GET /api/control-room/fix-data` (server.py:4940) executes first. It runs `CREATE TABLE IF NOT EXISTS identities(...)` at line 4950. This creates the shadow table in the same SQLite DB as all other tables.

2. If this endpoint has NEVER been called, the `identities` table does not exist.

3. `GET /api/v2/fix-data` (spec_router.py:1556) queries `SELECT ... FROM identities` at line 1561 WITHOUT any CREATE TABLE. If the v1 endpoint was never called → `sqlite3.OperationalError: no such table: identities`.

4. `POST /api/v2/fix-data/{type}/{id}/resolve` (spec_router.py:2279) runs `UPDATE identities SET confidence_score = 1.0 WHERE id = ?` at line 2281. Same dependency — fails if v1 was never called.

### Precise failure modes

| Scenario | What happens |
|---|---|
| Fresh DB, call v2 fix-data first | CRASH: `no such table: identities` (ID-4) |
| Fresh DB, call v1 fix-data first, then v2 | Works but queries empty shadow table. Real identity data is in `client_identities`, unreachable. |
| Any call to resolve via v1 or v2 | Updates shadow table. Real `client_identities` data unchanged. Resolution is performative — not functional. |

### Resolution

Remove inline `CREATE TABLE IF NOT EXISTS identities` from server.py:4950. Rewrite both endpoints (v1 and v2) to query `client_identities` with correct columns: `client_id`, `identity_type`, `identity_value`. Map to frontend FixData fields.

---

## G. Frontend Contract Status Tables

### G1. Notification interface (api.ts:1197)

| TS Field | TS Type | Exists Now (schema.py) | Added by PR1 | Transformed/Aliased | Status |
|---|---|---|---|---|---|
| id | string | YES (notifications.id) | — | — | OK |
| type | string | YES (notifications.type) | — | — | OK |
| message | string | NO | NO | Backend returns `title` — frontend must alias `title → message` or change interface | UNRESOLVED (contract decision needed) |
| task_id | string\|null | NO | YES (D8 adds task_id) | — | RESOLVED by PR1 |
| target_id | string\|null | NO | NO (D8: deferred — redundant with task_id) | — | UNRESOLVED (remove from TS interface or add to schema) |
| dismissed | number | NO | YES (D1 adds dismissed INTEGER DEFAULT 0) | — | RESOLVED by PR1 |
| dismissed_at | string\|null | NO | YES (D1 adds dismissed_at TEXT) | — | RESOLVED by PR1 |
| created_at | string | YES (notifications.created_at) | — | — | OK |

### G2. EmailItem interface (api.ts:1288)

| TS Field | TS Type | Exists Now (schema.py) | Added by PR1 | Transformed/Aliased | Status |
|---|---|---|---|---|---|
| id | string | YES (communications.id) | — | — | OK |
| subject | string\|null | YES (communications.subject) | — | — | OK |
| sender | string\|null | NO (schema has from_email) | — | Backend aliases `from_email AS sender` | RESOLVED by PR3 alias |
| recipient | string\|null | NO (schema has to_emails) | — | Backend aliases `to_emails AS recipient` | RESOLVED by PR3 alias |
| body | string\|null | NO (schema has body_text) | — | Backend aliases `body_text AS body` | RESOLVED by PR3 alias |
| received_at | string\|null | YES (communications.received_at) | — | — | OK |
| actionable | number | NO (schema has requires_response) | — | Backend aliases `requires_response AS actionable` | RESOLVED by PR3 alias |
| processed | number | YES (communications.processed) | — | — | OK |
| type | string | NO (no type column on communications) | — | Backend injects `'email' AS type` literal | RESOLVED by PR3 alias |

### G3. Evidence interface (types/api.ts:259)

| TS Field | TS Type | Exists Now (schema.py) | Added by PR1 | Transformed/Aliased | Status |
|---|---|---|---|---|---|
| id | string | YES (item_history.id) — but endpoint is being rewritten | — | — | UNRESOLVED (depends on new source table) |
| artifact_id | string | NO on item_history; YES on artifacts | — | Endpoint rewrite uses artifacts table | RESOLVED by PR4 rewrite |
| excerpt_text | string | NO anywhere | — | Removed from contract — no source for this data | UNRESOLVED (remove from TS interface) |
| context_json | string\|null | NO anywhere | — | Removed from contract — no source | UNRESOLVED (remove from TS interface) |
| created_at | string | YES (artifacts.created_at after rewrite) | — | — | RESOLVED by PR4 rewrite |
| source | string | YES (artifacts.source) | — | — | RESOLVED by PR4 rewrite |
| artifact_type | string | YES (artifacts.type after rewrite) | — | — | RESOLVED by PR4 rewrite |
| occurred_at | string | YES (artifacts.occurred_at) | — | — | RESOLVED by PR4 rewrite |

### G4. FixData interface (types/api.ts:240)

| TS Field | TS Type | Exists Now (schema.py) | Added by PR1 | Transformed/Aliased | Status |
|---|---|---|---|---|---|
| identity_conflicts | Array | NO — queries shadow `identities` table | — | Rewrite queries `client_identities` with correct columns | RESOLVED by PR3/PR4 rewrite |
| ambiguous_links | Array | PARTIAL — queries entity_links with inline CREATE schema | — | After PR1 schema sync, queries real entity_links | RESOLVED by PR1+PR3 |
| missing_mappings | unknown[] | NO — neither v1 (server.py) nor v2 (spec_router.py) returns this field | — | Both endpoints return `missing_mappings: []` (empty array) | RESOLVED — hardcoded [] |
| total | number | v1: YES (server.py returns it). v2: YES (spec_router.py returns it) | — | — | OK |

**FixData envelope confirmation:** After fixes, both v1 and v2 return `{identity_conflicts: [...], ambiguous_links: [...], missing_mappings: [], total: N}`. The `missing_mappings: []` and `total` fields are present in both versions.

### G5. GovernanceResponse interface (api.ts:1371)

| TS Field | TS Type | Exists Now (schema.py) | Added by PR1 | Transformed/Aliased | Status |
|---|---|---|---|---|---|
| domains | GovernanceDomain[] | NO — `governance.get_all_domains()` doesn't exist | — | PR3 rewrites to use `governance.get_status()` → extract domains | RESOLVED by PR3 rewrite |
| emergency_brake | boolean | NO — `governance.is_emergency_brake_active()` doesn't exist | — | PR3 rewrites to use `status.get("emergency_brake_active", False)` | RESOLVED by PR3 rewrite |
| summary | Record | NO — not returned at all | — | PR3 adds summary from status data | RESOLVED by PR3 rewrite |

---

## H. Residual Uncertainty

| # | What | Impact | Blocker? | Resolution Path |
|---|---|---|---|---|
| RU-1 | entity_links PK migration: `id INTEGER` → `link_id TEXT`. converge() cannot rename/retype PK. | If data exists in entity_links with integer IDs, drop-and-recreate loses it. | YES for PR1 if entity_links has data | Check `SELECT count(*) FROM entity_links` at runtime. If 0: safe to recreate. If >0: add `link_id TEXT UNIQUE` alongside `id`, backfill, then V4 code uses link_id. |
| RU-2 | Inline CREATE TABLE in store.py:131 creates `item_history` outside schema.py. Other tables may exist this way. | Converge() doesn't manage these tables. Schema drift possible. | NO — does not block any PR | **RESOLVED.** Grep found ~25 files with inline CREATE TABLE outside schema.py: store.py (item_history, 5 v4 tables), coupling_service.py, entity_link_service.py, identity_service.py, audit_log.py, notifications.py, key_manager.py, plus collector/intelligence layer tables. This is architectural debt but does not block endpoint fixes. Registration sweep is a separate task. |
| RU-3 | V4 service dual-DB-path: entity_link_service.py may connect to a separate SQLite file via `_ensure_tables()`. | schema.py changes would not propagate if service uses different DB path. | **NO** (was YES) | **RESOLVED.** entity_link_service.py:14 defines `DB_PATH = "../../data/moh_time_os.db"`. Line 49: `self.db_path = db_path or DB_PATH`. Line 620: `get_entity_link_service()` instantiates with NO db_path argument → uses hardcoded default. This resolves to the **same physical DB file** as the main store by coincidence (both use `data/moh_time_os.db`). schema.py changes WILL propagate. Risk: if the default ever changes, the services would diverge. Fragile but not blocking. |
| RU-4 | Test coverage: 4 cycle_logs test bugs suggest broader test-schema mismatch. | Other tests may silently pass with wrong columns if they use Mock instead of real SQLite. | NO — does not block production fixes | Sweep `tests/` for INSERT/UPDATE statements and diff columns against schema.py. Separate audit task. |
| RU-5 | Communications table: ~50 columns. Only email WHERE clause checked. | Other SELECTs may have phantom WHERE conditions not caught by this audit. | NO — email endpoint is the known broken one | Exhaustive SELECT sweep of communications table references. Low priority — most code uses `store.get()` or `SELECT *`. |
| RU-6 | action_framework.py _store_proposal(): 5 phantom columns. Entire proposal storage non-functional. | If ActionFramework.propose() is called in production, all proposals silently fail (caught by try/except in the framework). | **YES — live code** | **RESOLVED.** `_store_proposal()` IS called by `propose_action()` (line 226) which is registered as endpoint `POST /api/propose` via `api/action_router.py`, itself imported at server.py:142. This is NOT dead code — it is a live endpoint. All proposals crash silently. Must fix in PR-actions. |
| RU-7 | Notification `message` vs `title`: Frontend Notification interface has `message` field; backend schema has `title`. | UI may show undefined/null for notification text if not aliased. | YES for frontend contract | Either: (a) backend aliases `title AS message` in GET /api/notifications, or (b) frontend changes `message` to `title`. Decision needed. |
| RU-8 | Evidence interface `excerpt_text` and `context_json`: No source for these fields exists anywhere in the schema. | Frontend Evidence type has fields that will never be populated. | YES for frontend contract | Remove `excerpt_text` and `context_json` from Evidence TypeScript interface. They have no backing data source. |

---

## I. Schema Decisions

Each schema change below has semantic justification — not just "because the code wants it."

**D1. Add `dismissed` + `dismissed_at` to notifications.** Dismissed and read are semantically different states. `read_at` tracks when content was seen; `dismissed` tracks when user actively removed it from view.

**D2. Add `severity` to insights.** Anomalies need priority ordering. `confidence` (how sure) is orthogonal to `severity` (how bad).

**D3. Add `saved_filters` table.** Frontend SavedFilterSelector.tsx already fetches `/api/filters`. Real UX feature.

**D4. Sync `entity_links` schema.py with migration schema.** The migration (v4_milestone1_truth_proof.py:97) defines the production-grade 12-column schema. entity_link_service.py implements the full lifecycle. schema.py was never updated. Migration schema is correct.

**D5. Add `couplings` table to schema.py.** CouplingService creates it via `_ensure_tables()`. Registering in schema.py lets converge() manage it.

**D6. Do NOT add phantom columns to decisions.** server.py uses `type, target_id, proposed_changes, reason`. The correct pattern (decisions.py:194) uses `domain, decision_type, description, input_data`. Fix code, not schema.

**D7. Do NOT add phantom columns to actions.** notification.py/_log_action() uses `domain, action_type, target_id, data`. Correct pattern (task.py:247) uses `type, target_system, payload`. Fix code, not schema.

**D8. Add `task_id` and `recipient_id` to notifications.** `task_id` = which task; `recipient_id` = who gets it. `target_id` is redundant with task_id — do not add.

---

## J. Handler/Query Fixes by PR

### PR1 scope (schema.py only)
- saved_filters table (D3)
- severity column on insights (D2)
- dismissed + dismissed_at on notifications (D1)
- task_id + recipient_id on notifications (D8)
- couplings table (D5)
- entity_links sync to migration schema (D4)
- Bump SCHEMA_VERSION

### PR3 scope (server.py + lib/notifier/engine.py)
- N-I1..5: Fix 5 notification INSERTs
- N-U1..2: dismiss endpoints (migration-dependent on PR1)
- N-S1..2: dismiss SELECTs (migration-dependent on PR1)
- ~~N-U3..4~~: ALREADY FIXED in source — no action needed
- D-I1..3: Fix 3 decisions INSERTs — use correct columns
- D-U1..2: Fix 2 decisions UPDATEs — remove processed_by, modifications
- G-1..3: Fix governance_history → governance_audit_log + column remap
- INS-1: anomalies ORDER BY severity (migration-dependent on PR1)
- Email endpoint: WHERE from_email IS NOT NULL + column aliases
- Fix-data: remove inline CREATE, use client_identities (ID-1..3)
- Evidence: artifacts + entity_links join
- EL-6: server.py entity_links WHERE id → link_id

### PR4 scope (spec_router.py)
- CP-1: Wire couplings to CouplingService
- ID-4..5: Rewrite fix-data to use client_identities
- IH-1: Rewrite evidence to artifacts + entity_links
- EL-5: entity_links UPDATE after schema sync

### PR-actions scope (lib/ action handlers)
- A-I1..2: Rewrite _log_action() in notification.py + delegation.py
- A-I3: Rewrite _store_proposal() in action_framework.py
- A-U1: Rewrite reject_action()
- A-S1: Fix get_action_history()

### PR-entity-links scope (lib/v4/ + lib/entity_link_confirmer.py)
- EL-1..4, EL-7..11: All resolved by PR1 schema sync
- Verify post-merge: all 11 occurrences pass

### PR6 scope (tests + housekeeping)
- CL-T1..4: Fix test_sync_schedule.py column names
- smoke_test_endpoints.py commit

---

## K. Completion Gate

### Per-family verdict

| Family | Enumeration | Runtime classification | Schema reconciliation | Contract reconciliation | Verdict |
|---|---|---|---|---|---|
| Notifications | 19 occ (10 INSERT, 2 UPDATE, 6 SELECT, 1 DELETE). N-U3/N-U4 removed (already fixed). | 3 FATAL (re-raised HTTP 500), 2 CAUGHT-DEGRADED, 4 MIGRATION-DEP | 4 phantom columns, D1+D8 add 4, 2 removed from code | G1: 3 OK, 2 RESOLVED by PR1, 2 UNRESOLVED (RU-7, RU-8) | **PASS** — 2 contract decisions pending |
| Decisions | 21 occ (6 INSERT, 5 UPDATE, 10 SELECT) | 3 FATAL, 1 FATAL (re-raised HTTP 500), 1 FATAL | 6 phantom columns, D6: fix code not schema | N/A | **PASS** |
| Governance | 8 occ (3 wrong-table, 5 correct-table) | 2 FATAL, 1 CAUGHT-DEGRADED | Wrong table + wrong columns, remap to audit_log | G5: all 3 RESOLVED by PR3 | **PASS** |
| Actions | 18 occ (6 INSERT, 7 UPDATE, 5 SELECT) | 5 FATAL | 10 phantom columns, D7: fix code not schema. RU-6 RESOLVED: _store_proposal is live code via /api/propose. | N/A | **PASS** |
| Saved Filters | 1 occ | FATAL | Table missing, D3 creates it | N/A | **PASS** |
| Entity Links | 11 occ | All 11 FATAL | 5 missing columns + PK mismatch. D4 syncs schema. RU-3 RESOLVED: same db_path. RU-1 remains (PK strategy). | G4: ambiguous_links RESOLVED | **PARTIAL** — RU-1 PK migration not yet decided |
| Insights | 2 occ | 1 FATAL, 1 BENIGN | Severity column missing, D2 adds it | N/A | **PASS** |
| Identities | 5 occ | 1 CREATES-SHADOW, 2 CAUGHT-DEGRADED, 2 FATAL (order-dependent) | Shadow table vs canonical table fully mapped | G4: identity_conflicts RESOLVED | **PASS** |
| Couplings | 1 occ | FATAL | Wrong table, D5 + CouplingService wiring | N/A | **PASS** |
| Item History | 2 occ (1 bug, 1 clean) | FATAL | 4 phantom columns, rewrite to artifacts+entity_links | G3: 4 RESOLVED, 2 UNRESOLVED (RU-8) | **PASS** — TS cleanup needed |
| Cycle Logs | 4 occ | All TEST | 3 phantom columns in test code only | N/A | **PASS** |

### Gate statement

Two separate verdicts:

**Audit completeness: PASS.** Every family has exhaustive occurrence enumeration with file:line, function name (verified against source), endpoint, runtime classification, and explicit Original-41 ID mapping. Hostile audit validated all bug rows against source code and found/corrected: 2 function names, 3 line numbers, 2 already-fixed bugs, 4 misclassified runtime behaviors, and a fundamentally wrong overlap count (18→22). The 45 clean occurrences were NOT individually hostile-validated — they were spot-checked (10 samples, all confirmed). Clean classification is based on column-name matching against schema.py, not full trace-level validation.

**Remediation readiness: BLOCKED.** Cannot begin PR1 until RU-1 is decided (entity_links PK strategy: add `link_id TEXT UNIQUE` alongside `id INTEGER`, or drop-and-recreate with data migration). Two non-blocking contract decisions are also open: RU-7 (notification `message` vs `title` alias) and RU-8 (Evidence interface `excerpt_text`/`context_json` removal). These do not block PR1 but must be resolved before PR3/PR4 frontend contract work.

**Totals proof (see Appendix L for row-membership enumeration):**
- 92 occurrences scanned → 43 production bugs + 4 test bugs = 47 occurrence-table bugs
- 22 of the 43 overlap with original 41 (see Section C explicit mapping table with Original ID for each)
- 21 are genuinely new (see Section B table with justification for each)
- Grand total distinct production bugs: 41 + 21 = **62**
- Test bugs: 4 (CL-T1..T4)

---

## L. Row-Membership Proof

Every total is derived from the explicit row IDs below. No narration — just membership lists and arithmetic.

### Set 1: Overlap with original 41 (22 rows)

| # | Closure ID | Original-41 ID |
|---|---|---|
| 1 | N-I1 | G1a |
| 2 | N-I2 | G1b |
| 3 | N-I3 | G1c |
| 4 | N-I4 | G1d |
| 5 | N-I5 | G1e |
| 6 | N-U1 | A11 |
| 7 | N-U2 | A12 |
| 8 | N-S1 | A6 |
| 9 | N-S2 | A12 (partial) |
| 10 | G-1 | B8 |
| 11 | G-2 | B1 |
| 12 | G-3 | B6 |
| 13 | SF-1 | B5/F1 |
| 14 | EL-5 | A15 |
| 15 | EL-6 | A18 |
| 16 | ID-1 | D1 |
| 17 | ID-3 | A17 |
| 18 | ID-4 | B4 |
| 19 | ID-5 | A16/B7 |
| 20 | CP-1 | C1 |
| 21 | IH-1 | B3 |
| 22 | INS-1 | A5 |

Count: **22**

### Set 2: Net-new production bugs (21 rows)

| # | Closure ID | Family |
|---|---|---|
| 1 | D-I1 | decisions |
| 2 | D-I2 | decisions |
| 3 | D-I3 | decisions |
| 4 | D-U1 | decisions |
| 5 | D-U2 | decisions |
| 6 | A-I1 | actions |
| 7 | A-I2 | actions |
| 8 | A-I3 | actions |
| 9 | A-U1 | actions |
| 10 | A-S1 | actions |
| 11 | EL-1 | entity_links |
| 12 | EL-2 | entity_links |
| 13 | EL-3 | entity_links |
| 14 | EL-4 | entity_links |
| 15 | EL-7 | entity_links |
| 16 | EL-8 | entity_links |
| 17 | EL-9 | entity_links |
| 18 | EL-10 | entity_links |
| 19 | EL-11 | entity_links |
| 20 | INS-2 | insights |
| 21 | ID-2 | identities |

Count: **21**

### Set 3: Test-only bugs (4 rows)

| # | Closure ID | Family |
|---|---|---|
| 1 | CL-T1 | cycle_logs |
| 2 | CL-T2 | cycle_logs |
| 3 | CL-T3 | cycle_logs |
| 4 | CL-T4 | cycle_logs |

Count: **4**

### Arithmetic

```
Set 1 (overlap) + Set 2 (new) + Set 3 (test) = 22 + 21 + 4 = 47 total occurrence-table bugs
Production bugs in occurrence tables = Set 1 + Set 2 = 22 + 21 = 43
Grand total distinct production bugs = 41 (original) + 21 (Set 2, net-new) = 62
Test bugs = 4 (Set 3, separate from production count)
```

Cross-check: Sets 1, 2, 3 are mutually exclusive (no ID appears in more than one set). Union = all 47 bugs in the D-tables. Every bug row in D1-D11 is accounted for in exactly one set.

### Validation scope disclosure

**Bug rows (Sets 1-3, 47 rows):** Full hostile validation — file:line, function name, column names, runtime classification each verified against source code. 14 corrections applied (see Part A above).

**Clean rows (45 occurrences):** NOT individually hostile-validated. Classification based on column-name matching against schema.py TABLES dict. 10 samples spot-checked (N-I6, N-I7, D-I4, D-S3, G-C3, G-C4, A-I4, A-U2, A-S2, IH-2) — all confirmed clean. The remaining 35 clean rows carry schema-match confidence but not trace-level proof.
