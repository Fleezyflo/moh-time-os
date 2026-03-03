# Client UI Specification — Time OS

*Executable spec for implementation — 2026-02-07*

**Status:** v2.1 FINAL

---

## 0. Definitions (Glossary)

| Term | Definition |
|------|------------|
| **Inbox Item** | A proposal wrapper around an underlying entity (issue, signal, orphan). Has its own lifecycle. |
| **Issue** | A tracked problem derived from aggregated signals. Has its own lifecycle separate from Inbox. |
| **Signal** | A single observation from a source system (Asana, Gmail, etc.). Classified as good/neutral/bad. |
| **Flagged Signal** | A signal that triggered an out-of-norm detector rule but hasn't yet aggregated into an issue. |
| **Orphan** | A signal referencing an engagement/project not found in the database. |
| **Ambiguous** | A signal that matches multiple possible engagements with similar confidence. |
| **Watch Loop** | Background behavior that enriches context and alerts on escalation. Not a state. |
| **AR_outstanding** | Total unpaid invoices: `SUM(amount) WHERE status IN ('sent', 'overdue')`. Used as AR_total in formulas. |
| **Engagement Resolver** | System logic that matches signals to engagements using GID, invoice reference, meeting title, or email subject parsing. See 6.8. |
| **Engagement** | A project or retainer linked to a client and brand. Has its own lifecycle (6.7). |
| **Brand** | A sub-entity of a client representing a distinct business unit or product line. |
| **Client Status** | Computed classification: `active`, `recently_active`, `cold`. See 6.1. |
| **Tier** | Client classification for prioritization. Values: `platinum`, `gold`, `silver`, `bronze`, `none`. |
| **Severity** | Issue/inbox item priority: `critical`, `high`, `medium`, `low`, `info`. |

---

## 0.1 Global Conventions

**Timestamp Format:**

All timestamp fields stored as TEXT use ISO 8601 format:
- **Storage:** Always UTC with `Z` suffix: `YYYY-MM-DDTHH:MM:SS.sssZ`
- **Format:** Exactly 24 characters: `YYYY-MM-DDTHH:MM:SS.sssZ`
- **Ingestion:** Accept offsets (`±HH:MM`) at API boundary, normalize to UTC on write
- **Validation:** App-layer regex: `/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/`

**DB Constraint Limitations:** TEXT timestamps cannot enforce temporal ordering (e.g., "future") in SQL. DB CHECK constraints enforce only nullability and terminal invariants. All time ordering validation is app-layer.

**JSON Fields:**

All `evidence` and structured data fields use JSON (or JSONB where supported). Application layer validates structure per schema definitions.

**Calculation Versioning:**

Financial calculations carry a version marker for historical comparisons:
- Current: `finance_calc_version = 'v1'`
- v1: No partial payments; invoices fully paid or fully unpaid
- **API exposure:** Include `finance_calc_version` in financial summary responses

**Severity Ordering (Canonical):**

For all server-side sorts and comparisons:

| Severity | Sort Weight | Description |
|----------|-------------|-------------|
| `critical` | 5 | Immediate action required |
| `high` | 4 | Urgent attention needed |
| `medium` | 3 | Should address soon |
| `low` | 2 | Can wait |
| `info` | 1 | Informational only |

Descending sort: critical → high → medium → low → info.

**Canonical "Today" (Timezone):**

All date boundary calculations ("today - 90 days", etc.) use the **org's configured timezone**:
- **Required:** `org.timezone` setting (default: `Asia/Dubai`)
- Date boundaries computed at local midnight (00:00:00 in org timezone)
- Stored as UTC after conversion
- **"today" computed at:** Request time, using org timezone

```python
def local_midnight_utc(org_tz: str, date: date) -> datetime:
    """Returns UTC timestamp for midnight of given date in org timezone."""
    local_midnight = datetime.combine(date, time.min, tzinfo=ZoneInfo(org_tz))
    return local_midnight.astimezone(UTC)
```

Example: "today" on 2026-02-07 in Asia/Dubai = 2026-02-06T20:00:00Z to 2026-02-07T19:59:59Z.

**"days=N" Query Parameters:** Use org-local day boundaries, not rolling 24-hour windows.

**User Scope:**

This spec assumes **single-org, multi-user team with org-global shared state**:
- `read_at`, `snooze`, `dismiss` are org-global (affect all team members)
- Suppression rules are org-wide (one user's dismiss affects everyone)
- No per-user inbox state tables required
- User references (`dismissed_by`, `snoozed_by`, etc.) track actor for audit

If per-user state is added later:
- Add `inbox_item_reads (inbox_item_id, user_id, read_at)`
- Add `scope` field to `inbox_suppression_rules`
- Define whether snooze is personal or global

**Rounding Conventions:**

| Metric | Rounding | Example |
|--------|----------|---------|
| `ar_overdue_pct` | `round()` (nearest integer) | 34.6% → 35 |
| Health penalties | `floor()` | 34.6 → 34 |
| Years in relationship | `floor(x * 10) / 10` (1 decimal) | 3.7 years |

**Time Library Contract:**

All date-only fields are interpreted as org-local date at midnight. All conversions and comparisons use org-local date boundaries.

```python
def days_late(due_date: date, completed_at: datetime, org_tz: str) -> int:
    """Compute days late using org-local dates."""
    due_local = due_date  # already a date
    completed_local = completed_at.astimezone(ZoneInfo(org_tz)).date()
    return max(0, (completed_local - due_local).days)

def payment_date_local(status_changed_at: datetime, org_tz: str) -> date:
    """Convert payment timestamp to org-local date."""
    return status_changed_at.astimezone(ZoneInfo(org_tz)).date()
```

---

## 0.2 Strategic Design Decisions

**Decision A: Inbox Snooze = "Reminder Snooze" (not "Problem Snooze")**

Snoozing an inbox item hides the **proposal/reminder**, not the underlying problem:
- Issue remains in `surfaced` state (or whatever state it was in)
- Health penalty still applies (issue is still open)
- User is deferring the notification, not the problem

**UX implication:** Clearly message in UI that snoozing an inbox item does NOT defer the issue itself. If user wants to defer the issue (and its health impact), they must snooze the issue directly from the client detail page.

**Required UI copy:** "Snoozing hides this reminder. The issue remains open and affects health score."

**Decision B: Standardized Evidence Schema**

All evidence fields across issues, signals, and inbox_items use the same envelope structure (see 6.16). This enables:
- Consistent frontend rendering
- Unified audit trail

---

## 0.3 UI Label Mapping

| API State/Value | UI Label | Display Bucket |
|-----------------|----------|----------------|
| `detected` | (hidden from user) | — |
| `surfaced` | "Surfaced" | Open |
| `snoozed` | "Snoozed" | Open |
| `acknowledged` | "Acknowledged" | Open |
| `addressing` | "Addressing" | Open |
| `awaiting_resolution` | "Awaiting resolution" | Open |
| `resolved` | "Resolved" | Closed |
| `regression_watch` | "Regression watch (90d)" | Closed |
| `closed` | "Closed" | Closed |
| `regressed` | "Regressed" | Open |

**Never use "watch loop" as a state label in UI.** "Watch loop" is background behavior only.

**read_at / Unprocessed:**
- UI label: "Unprocessed" (not "Unread")
- API endpoint: `/mark_read` (preserved for compatibility)
- Meaning: User has explicitly acknowledged seeing the item
- Simpler migrations when evidence evolves

**Decision C: Invoice Anomaly Precedence**

When an invoice qualifies for both a financial issue AND a flagged_signal (e.g., overdue AND status-inconsistent):
- **Issue takes precedence** once aggregation threshold is reached
- Do NOT create a flagged_signal for the same invoice+rule in the same detector run
- Exception: `invoice_status_inconsistent` flagged_signal is created ONLY if no financial issue exists for that invoice

This prevents duplicate proposals and conflicting actions.

---

## 1. Control Room — Inbox (Proposals)

### 1.1 Purpose

The Inbox is the **global intake surface** for items requiring your attention. The system sifts signals from other people's meetings, tasks, chats, calendar, and email—then proposes out-of-norm items here with context and proof.

This is where the watch loop begins.

### 1.2 Inbox Structure

```
CONTROL ROOM — INBOX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Needs Attention: 12]  [Snoozed: 3]  [Recently Actioned: 8]

Filter: [All ▼] [Issues ▼] [Flagged Signals ▼] [Orphans ▼] [Ambiguous ▼]
Sort:   [Severity ▼] [Age ▼] [Client ▼]

┌─────────────────────────────────────────────────────────────────┐
│ 💰 FINANCIAL — Invoice 45 days overdue              [critical]  │
│    Client: Acme Corp · Brand A                                  │
│    Inbox State: proposed · Proposed 2d ago                      │
│    Evidence: INV-1234 · AED 35,000 · Due 2025-12-20             │
│                                                                 │
│    [Tag & Watch]  [Assign]  [Snooze 7d]  [Dismiss]              │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ SCHEDULE — 4 tasks overdue across Brand A retainer    [high] │
│    Client: Acme Corp · Brand A: Monthly Retainer 2026           │
│    Inbox State: proposed · Proposed 1d ago                      │
│    Evidence: View in Asana ↗                                    │
│      "Q1 Deliverables Review" — 5d overdue (Sarah)              │
│      "Monthly Report" — 3d overdue (Sarah)                      │
│      "Asset Delivery" — 1d overdue (Mike)                       │
│      +1 more                                                    │
│                                                                 │
│    [Tag & Watch]  [Assign]  [Snooze 7d]  [Dismiss]              │
├─────────────────────────────────────────────────────────────────┤
│ 🔍 FLAGGED SIGNAL — Unusual meeting cancellation        [medium]│
│    Client: GlobalTech · (no engagement linked)                  │
│    Source: Calendar                                             │
│    "Quarterly Review" cancelled 2h before start                 │
│    No reschedule detected                                       │
│                                                                 │
│    [Tag & Watch]  [Assign]  [Snooze 7d]  [Dismiss]              │
├─────────────────────────────────────────────────────────────────┤
│ 💬 COMMUNICATION — Negative sentiment cluster           [high]  │
│    Client: Sunrise Media · Brand B                              │
│    Inbox State: proposed · Proposed 3d ago                      │
│    Evidence: 3 negative signals in 7 days                       │
│      Gmail: "We're disappointed with turnaround..."             │
│      Chat: Escalation keyword detected                          │
│      Minutes: Client expressed frustration (Gemini)             │
│                                                                 │
│    [Tag & Watch]  [Assign]  [Snooze 7d]  [Dismiss]              │
├─────────────────────────────────────────────────────────────────┤
│ 🔗 ORPHAN — Signal without engagement                   [info]  │
│    Client: NewCo Industries                                     │
│    Source: Asana                                                │
│    Task "Website Redesign Kickoff" in unlinked project          │
│    Project GID: 1234567890 not found in DB                      │
│                                                                 │
│    [Create Engagement]  [Link to Engagement]  [Dismiss]         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Inbox Item Types

| Type | API Value | Source | Appears When |
|------|-----------|--------|--------------|
| **Issue** | `issue` | Signal aggregation | Signals crossed threshold for issue type |
| **Flagged Signal** | `flagged_signal` | Detector | Single signal flagged as unusual/out-of-norm |
| **Orphan** | `orphan` | Any source | Signal references unknown engagement/project |
| **Ambiguous** | `ambiguous` | Engagement Resolver | Signal could match multiple engagements with similar confidence |

**Note on Ambiguous:** Arises from Engagement Resolver (which may use name matching), NOT from Task Linking (which never uses name matching). See 6.3 and 6.8.

### 1.4 Inbox Item Lifecycle (Separate from Issue Lifecycle)

**Inbox items are proposals.** They wrap underlying entities (issues, signals, orphans) and have their own state. Inbox states are distinct from Issue states.

```
                    ┌──────────────────────────────────────┐
                    │       INBOX ITEM LIFECYCLE           │
                    └──────────────────────────────────────┘

                            ┌──────────┐
                            │ proposed │ ← Item appears in Inbox
                            └────┬─────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
      ┌─────────────┐     ┌──────────┐         ┌──────────┐
      │linked_to    │     │ snoozed  │         │ dismissed│
      │  _issue     │     └────┬─────┘         └──────────┘
      └─────────────┘          │                (terminal)
        (terminal)             │ timer expires
                               ▼
                         ┌──────────┐
                         │ proposed │ (resurfaces)
                         └──────────┘
```

**Inbox item states:**

| State | API Value | Definition | Terminal | Fetchable via API |
|-------|-----------|------------|----------|-------------------|
| `proposed` | `proposed` | Awaiting user action | No | Yes |
| `snoozed` | `snoozed` | Hidden for N days | No | Yes (separate tab) |
| `dismissed` | `dismissed` | User dismissed; logged for audit | Yes | No (default) / Yes via `/recent` |
| `linked_to_issue` | `linked_to_issue` | Item resolved into tracked issue | Yes | No (default) / Yes via `/recent` |

**Note:** There is no separate `tagged` state. All "Tag & Watch" actions result in `linked_to_issue` (issue is created or linked, inbox item archived).

**Terminal State Behavior:**
- Default `GET /api/inbox` excludes terminal states (dismissed, linked_to_issue)
- `GET /api/inbox/recent?days=N` fetches terminal items actioned within N days (for audit/review)
- Terminal items in `/recent` are read-only; `read_at` is not affected by viewing them

---

**Terminal State Transitions (Atomic Writes):**

When transitioning to terminal states (`dismissed`, `linked_to_issue`), all fields must be set atomically in a single transaction to satisfy CHECK constraints:

```sql
-- Example: dismiss action
UPDATE inbox_items SET
  state = 'dismissed',
  resolved_at = now(),
  updated_at = now(),
  dismissed_by = :user_id,
  dismissed_at = now(),
  dismiss_reason = :note,
  suppression_key = :computed_key
WHERE id = :item_id;
```

Never set `state` first then timestamps — this violates `chk_terminal_requires_resolved`.

---

**Inbox Item Snooze Timer Execution:**

Snooze expiry for inbox items is executed by a **scheduled job** (runs hourly, same job as issue snooze):

1. Query: `SELECT * FROM inbox_items WHERE state = 'snoozed' AND snooze_until <= now()`
2. For each expired item:
   - Update `inbox_items.state = 'proposed'`
   - Clear snooze fields: `snooze_until = NULL`, `snoozed_by = NULL`, `snoozed_at = NULL`, `snooze_reason = NULL`
   - Update `inbox_items.updated_at = now()`

### 1.5 Inbox Item ↔ Underlying Entity Mapping

| Inbox Item Type | Underlying Entity | On "Tag & Watch" | On "Dismiss" |
|-----------------|-------------------|------------------|--------------|
| **Issue** | `issues` record | Issue → `acknowledged` state; watch loop starts | Issue suppressed (`issues.suppressed = true`); no state change |
| **Flagged Signal** | `signals` record | Creates new issue, links signal; watch loop starts | Signal marked `signals.dismissed = true`; no issue created |
| **Orphan** | `signals` + missing link | Requires "Link to Engagement" or "Create Engagement" action first | Signal marked `signals.dismissed = true` |
| **Ambiguous** | `signals` + multiple candidates | Requires "Select Primary" action first | Signal marked `signals.dismissed = true` |

**Key distinction:** "Dismiss" is an **Inbox action only**. It does not add a state to the Issue lifecycle. Instead, it sets a `suppressed` flag on the underlying issue (if one exists) or a `dismissed` flag on the underlying signal.

### 1.6 Primary Actions

| Action | API Value | Applies To | Effect |
|--------|-----------|------------|--------|
| **Tag & Watch** | `tag` | Issue, Flagged Signal | Creates/links issue, transitions issue to `acknowledged`, starts watch loop |
| **Assign** | `assign` | Issue, Flagged Signal | Creates/links issue, assigns to team member, transitions issue to `addressing` |
| **Snooze** | `snooze` | Any | Hides inbox item for N days, resurfaces as `proposed` |
| **Dismiss** | `dismiss` | Any | Archives inbox item, suppresses underlying entity (see 1.5) |
| **Link to Engagement** | `link` | Orphan, Ambiguous | Associates signal with existing engagement, resolves orphan/ambiguous |
| **Create Engagement** | `create` | Orphan | Opens engagement creation flow, then links signal |
| **Select Primary** | `select` | Ambiguous | User picks one candidate; system resolves ambiguity; item becomes actionable via Tag/Assign |

**Select Primary Flow:**
1. User views candidate list in Ambiguous inbox item
2. User selects one engagement
3. System links signal to selected engagement
4. Inbox item type remains same, but is now actionable
5. Available actions change to: `[Tag & Watch] [Assign] [Snooze 7d] [Dismiss]`

### 1.7 Tag & Watch Action (Detailed)

When you click **Tag & Watch**:

1. If Flagged Signal: create new issue from signal
2. If Issue: use existing issue
3. Set `issues.tagged_by_user_id = current_user`
4. Set `issues.tagged_at = now()`
5. Transition issue to `acknowledged` state
6. **Watch loop begins** (background behavior, not a state):
   - System gathers additional context from related signals
   - Adds new evidence as it arrives
   - Alerts if situation escalates
   - Continues until issue reaches `resolved` or `closed`
7. Archive inbox item as `linked_to_issue`

**Clarification:** "Watch loop" is a **background behavior**, not a state. The issue moves through its own lifecycle states (`acknowledged` → `addressing` → etc.) while the watch loop runs.

**Audit fields written:**

| Table | Field | Value |
|-------|-------|-------|
| `issues` | `tagged_by_user_id` | UUID of user who tagged |
| `issues` | `tagged_at` | Timestamp of tag action |
| `inbox_items` | `state` | `linked_to_issue` |
| `inbox_items` | `resolved_at` | Timestamp |
| `inbox_items` | `resolved_issue_id` | UUID of created/linked issue |

### 1.7.1 Assign Action (Detailed)

When you click **Assign**:

1. If Flagged Signal: create new issue from signal
2. If Issue: use existing issue
3. **Preserve first confirmation:** Set `tagged_by_user_id` and `tagged_at` only if currently NULL
4. Set `issues.assigned_to = assign_to` (user being assigned)
5. Set `issues.assigned_at = now()`
6. Set `issues.assigned_by = current_user`
7. Transition issue to `addressing` state (skips acknowledged)
8. **Watch loop begins** (same as Tag)
9. Archive inbox item as `linked_to_issue`

**Audit fields written:**

| Table | Field | Value | Condition |
|-------|-------|-------|-----------|
| `issues` | `tagged_by_user_id` | UUID of user | Only if NULL |
| `issues` | `tagged_at` | Timestamp | Only if NULL |
| `issues` | `assigned_to` | UUID of assignee | Always |
| `issues` | `assigned_at` | Timestamp | Always |
| `issues` | `assigned_by` | UUID of user who assigned | Always |
| `inbox_items` | `state` | `linked_to_issue` | Always |
| `inbox_items` | `resolved_at` | Timestamp | Always |
| `inbox_items` | `resolved_issue_id` | UUID of created/linked issue | Always |

**Note:** `tagged_by_user_id/tagged_at` preserve the first user confirmation. If issue was already acknowledged/tagged and later assigned, these fields are NOT overwritten.

### 1.8 Dismiss Action (Detailed)

When you click **Dismiss**:

1. Archive inbox item as `dismissed`
2. Set `inbox_items.resolved_at = now()`
3. Compute and store suppression key (see below)
4. Suppress underlying entity:
   - If Issue: set `issues.suppressed = true`, `issues.suppressed_at = now()`, `issues.suppressed_by = current_user`
   - If Signal: set `signals.dismissed = true`, `signals.dismissed_at = now()`, `signals.dismissed_by = current_user`
5. **Suppression behavior:**
   - Suppressed issues are excluded from health scoring
   - Suppressed issues do not resurface unless the same root cause triggers a new issue
   - Dismissal is logged for audit but does NOT create a new issue state

**Suppression Key (prevents identical re-proposals):**

When an inbox item is dismissed, compute a deterministic suppression key:

| Item Type | Suppression Key Formula |
|-----------|------------------------|
| Issue | `suppression_key("issue", {issue_type, client_id, engagement_id})` |
| Flagged Signal | `suppression_key("flagged_signal", {client_id, engagement_id, source, rule_triggered})` |
| Orphan | `suppression_key("orphan", {identifier_type, identifier_value})` |
| Ambiguous (before select) | `suppression_key("ambiguous", {signal_id})` |
| Ambiguous (after select, dismissed) | Use flagged_signal formula with resolved scoping |

**Flagged Signal Suppression Key Rationale:**

Suppression key is **scope-based** (not source_id-based):
- `client_id` + `engagement_id` (nullable) + `source` + `rule_triggered`
- Does NOT include `source_id`
- This means: dismissing a flagged signal suppresses future signals of the same pattern for that client/engagement
- Expiry (30 days) allows re-evaluation when detector behavior may have changed

**Suppression Key Algorithm:**

```python
def suppression_key(item_type: str, data: dict) -> str:
    """
    Compute deterministic suppression key.
    Algorithm: SHA-256
    Input: JSON canonical form, UTF-8, sorted keys
    """
    payload = {
        "v": "v1",  # key version for future-proofing
        "t": item_type,
        **data
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return "sk_" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]
```

**Null Engagement Fallback:**

For Issue suppression when `engagement_id IS NULL`:
1. If `brand_id` is present: include `brand_id` instead of `engagement_id`
2. Else: include `root_cause_fingerprint` (hash of evidence structure)

Where `root_cause_fingerprint = sha256(issue_type + sorted(evidence.keys()))`

Store in `inbox_suppression_rules`:
```sql
CREATE TABLE inbox_suppression_rules (
  id TEXT PRIMARY KEY,
  suppression_key TEXT NOT NULL UNIQUE,
  item_type TEXT NOT NULL,      -- 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous'
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,              -- NULL = permanent; computed per type below
  reason TEXT
);
```

**Suppression Expiry Defaults (by item type):**

| Item Type | Default Expiry | Rationale |
|-----------|----------------|-----------|
| Issue | 90 days | Matches regression watch window |
| Flagged Signal | 30 days | Detector noise may become meaningful; short expiry allows re-evaluation |
| Orphan | 180 days | Schema/project changes are infrequent |
| Ambiguous | 30 days | Candidate list changes as engagements are created |

On new inbox item proposal: if `suppression_key` exists in `inbox_suppression_rules` and not expired, do not create inbox item.

**Reversing Suppression:**

To unsuppress an issue or re-enable proposals:
- `DELETE FROM inbox_suppression_rules WHERE suppression_key = ?`
- Or: `POST /api/inbox/suppression/:id/revoke`

For issues specifically:
- `POST /api/issues/:id/unsuppress` — sets `issues.suppressed = false`, deletes corresponding suppression rule

**Suppression Source of Truth:**

`inbox_suppression_rules` is the **authoritative source** for suppression enforcement:
- On new inbox item proposal: check `inbox_suppression_rules` (not `inbox_items.suppression_key`)
- `inbox_items.suppression_key` is stored for audit only (preserves what key was used at dismiss time)
- Revoking suppression deletes from `inbox_suppression_rules`; does not modify historical `inbox_items`

**Suppression Expiry Enforcement:**

```sql
-- Check if suppressed (ignore expired rules)
SELECT 1 FROM inbox_suppression_rules
WHERE suppression_key = :key
  AND (expires_at IS NULL OR expires_at > now())
```

**Cleanup (optional):** A daily job may delete expired rules (`DELETE FROM inbox_suppression_rules WHERE expires_at < now()`). Revocation endpoint deletes immediately.

**Transaction Boundary (Dismiss Action):**

All dismiss operations must execute in a **single database transaction**:

```python
with db.transaction():
    # 1. Update inbox_items
    update_inbox_item(state='dismissed', ...)

    # 2. Update underlying entity
    if item.type == 'issue':
        update_issue(suppressed=True, ...)
    else:
        update_signal(dismissed=True, ...)

    # 3. Insert suppression rule
    insert_suppression_rule(...)

    # If any step fails, entire operation rolls back
```

**Suppression Audit:** No separate `suppression_events` table. Audit is via fields on `issues` (`suppressed_at`, `suppressed_by`) and `inbox_items` (`dismissed_at`, `dismissed_by`, `dismiss_reason`). This is sufficient for current requirements.

**Audit fields written:**

| Table | Field | Value |
|-------|-------|-------|
| `inbox_items` | `state` | `dismissed` |
| `inbox_items` | `resolved_at` | Timestamp |
| `inbox_items` | `dismissed_by` | UUID of user |
| `inbox_items` | `dismissed_at` | Timestamp |
| `inbox_items` | `dismiss_reason` | Optional note |
| `inbox_items` | `suppression_key` | Computed hash |
| `inbox_suppression_rules` | (new row) | Suppression entry |
| `issues` | `suppressed` | `true` (if underlying is issue) |
| `issues` | `suppressed_at` | Timestamp |
| `issues` | `suppressed_by` | UUID of user |
| `signals` | `dismissed` | `true` (if underlying is signal) |
| `signals` | `dismissed_at` | Timestamp |
| `signals` | `dismissed_by` | UUID of user |

### 1.9 Inbox Counts (Header)

```
Control Room
├── Needs Attention: 12       ← state = 'proposed'
│   ├── Critical: 2
│   ├── High: 5
│   ├── Medium: 3
│   └── Info: 2
├── Snoozed: 3                ← state = 'snoozed'
│   └── Returning soon: 1     ← snooze_until <= today + 1 day
└── Recently Actioned: 8      ← state IN ('linked_to_issue', 'dismissed') AND resolved_at >= today - 7 days
```

**Count definitions:**
- **Needs Attention:** `COUNT(*) WHERE state = 'proposed'`
- **Snoozed:** `COUNT(*) WHERE state = 'snoozed'`
- **Returning Soon:** `COUNT(*) WHERE state = 'snoozed' AND snooze_until <= now() + INTERVAL '1 day'`
- **Recently Actioned:** `COUNT(*) WHERE state IN ('linked_to_issue', 'dismissed') AND resolved_at >= window_start`

**Note:** `resolved_at` is set when inbox item transitions to any terminal state (`linked_to_issue` or `dismissed`).

**days=N Window Calculation (Canonical):**

All "last N days" queries use org-local midnight boundaries, NOT rolling 24-hour windows:

```python
def window_start(org_tz: str, days: int) -> datetime:
    """Returns UTC timestamp for midnight N days ago in org timezone."""
    local_today = datetime.now(ZoneInfo(org_tz)).date()
    local_start_date = local_today - timedelta(days=days)
    return local_midnight_utc(org_tz, local_start_date)
```

Applied to:
- Inbox header counts (`recently_actioned`)
- `GET /api/inbox/recent?days=N`
- Any endpoint using `days=N` parameter

**Recently Actioned Tab:**

The "Recently Actioned" section displays terminal items for audit/review. Terminal states are excluded from default `GET /api/inbox` but fetchable via:
- `GET /api/inbox/recent?days=7` — returns items actioned within N days (org-local boundaries)
- Items shown read-only (no actions available; already resolved)

### 1.10 Read vs Needs Attention

**Read is independent of state.** Marking an item as read does not change its actionability.

| Field | Purpose |
|-------|---------|
| `inbox_items.read_at` | Timestamp when user explicitly acknowledged item (null if unprocessed) |
| `inbox_items.state` | Lifecycle state (proposed/snoozed/etc.) |

**UI behavior:**
- Unprocessed items (`read_at IS NULL`) show bold styling
- UI label: "Unprocessed" (not "Unread") — reflects explicit acknowledgment, not view tracking
- "Mark as processed" sets `read_at = now()` but does NOT change state
- Items remain in "Needs Attention" until actioned (Tag/Assign/Snooze/Dismiss)

**Setting `read_at`:**
- Explicit: `POST /api/inbox/:id/mark_read` (API name preserved for compatibility)
- Bulk: `POST /api/inbox/mark_all_read` (marks all proposed items)
- Implicit: NOT set on view; requires explicit action

**Semantic Clarification:** `read_at` is an **explicit acknowledgment** that the user has seen and mentally processed the item, not a "viewed" timestamp. Clicking into an item to view evidence does NOT set `read_at`. This prevents items from disappearing from the "Unprocessed" filter just because they were glanced at.

---

## 2. Client Index Page

### 2.1 Page Structure

Three sections, displayed in this order:

| Section | Definition | Count Display |
|---------|------------|---------------|
| **Active** | Invoiced in last 90 days | "X Active Clients" |
| **Recently Active** | Invoiced 91–270 days ago | "X Recently Active" |
| **Cold** | No invoice in 270+ days | "X Cold" |

Each section is collapsible. Active expanded by default; others collapsed.

---

### 2.2 Active Client Card

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT NAME                                              [Tier] │
│ Health: ██████████░░ 78 (provisional)                          │
├─────────────────────────────────────────────────────────────────┤
│ ISSUED                              PAID                        │
│   Prior Yr:  AED 500,000              Prior Yr:  AED 420,000    │
│   YTD:       AED 125,000              YTD:       AED 95,000     │
├─────────────────────────────────────────────────────────────────┤
│ AR                                                              │
│   Outstanding: AED 130,000          Overdue: AED 45,000 (35%)   │
├─────────────────────────────────────────────────────────────────┤
│ ⚠ 2 open issues (high/critical)                                │
└─────────────────────────────────────────────────────────────────┘
```

**Note:** "Prior Yr" = last full calendar year (e.g., 2025 when current year is 2026). "YTD" = current calendar year to date. Both dynamically computed.

**Field order (fixed):**
1. Client name + tier badge
2. Health score bar (0-100, provisional label)
3. Issued totals: current year, YTD
4. Paid totals: current year, YTD
5. AR: Outstanding total, Overdue total + percentage
6. Open issues count (high/critical only)

**Interaction:** Click → Active Client Detail page (full drilldown)

---

### 2.3 Recently Active Client Card

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT NAME                                   [Recently Active] │
├─────────────────────────────────────────────────────────────────┤
│ ISSUED                              PAID                        │
│   Last 12m:  AED 180,000              Last 12m:  AED 180,000    │
│   Prev 12m:  AED 220,000              Prev 12m:  AED 220,000    │
├─────────────────────────────────────────────────────────────────┤
│ Historical: AED 850,000 issued / AED 850,000 paid               │
│ Last invoice: 2025-09-15                                        │
└─────────────────────────────────────────────────────────────────┘
```

**Field order (fixed):**
1. Client name + "Recently Active" badge
2. Last 12m / Prev 12m Issued
3. Last 12m / Prev 12m Paid
4. Historical totals (lifetime issued + paid)
5. Last invoice date

**Interaction:** Click → Recently Active Drilldown (limited)

---

### 2.4 Cold Client Card

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT NAME                                              [Cold] │
├─────────────────────────────────────────────────────────────────┤
│ Historical: AED 350,000 issued / AED 350,000 paid               │
│ Last invoice: 2024-02-10                                        │
└─────────────────────────────────────────────────────────────────┘
```

**Field order (fixed):**
1. Client name + "Cold" badge
2. Historical totals (lifetime issued + paid)
3. Last invoice date

**Interaction:** Not clickable. Greyed styling.

---

### 2.5 Sorting & Filtering

**Default sort:** AR Overdue (descending) within Active; Last invoice date (descending) within Recently Active/Cold.

**Available filters:**
- Tier (dropdown): `platinum`, `gold`, `silver`, `bronze`, `none`, all
- Has open issues (toggle) — includes states: surfaced, acknowledged, addressing, awaiting_resolution, regressed (excludes detected, snoozed)
- AR Overdue > 0 (toggle)

---

## 3. Active Client Detail Page

### 3.1 Header

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Index                                                 │
│                                                                 │
│ CLIENT NAME                                              [Tier] │
│ Health: ██████████░░ 78 (provisional)                          │
│                                                                 │
│ [Overview] [Engagements] [Financials] [Signals] [Team]          │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.2 Tab 1: Overview

**Purpose:** Executive snapshot. Key metrics + top issues requiring attention.

```
KEY METRICS
┌─────────────────────────────────────────────────────────────────┐
│ ISSUED                              PAID                        │
│   Prior Yr:  AED 500,000              Prior Yr:  AED 420,000    │
│   YTD:       AED 125,000              YTD:       AED 95,000     │
├─────────────────────────────────────────────────────────────────┤
│ AR Outstanding: AED 130,000         AR Overdue: AED 45,000      │
├─────────────────────────────────────────────────────────────────┤
│ Active engagements: 3               Open tasks: 24              │
│ Tasks overdue: 4                    Signals (30d): 12↑ 5→ 3↓    │
└─────────────────────────────────────────────────────────────────┘

TOP ISSUES (high/critical)
┌─────────────────────────────────────────────────────────────────┐
│ 💰 FINANCIAL — Invoice 45 days overdue                [critical]│
│    Issue State: surfaced                                        │
│    Evidence: INV-1234 · AED 35,000 · Due 2025-12-20             │
│    (open in Xero)                                               │
│    [Acknowledge] [Snooze 7d] [Resolve]                          │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ SCHEDULE — 3 tasks overdue on Brand A retainer        [high] │
│    Issue State: addressing (assigned to Sarah)                  │
│    Evidence: View in Asana ↗                                    │
│    "Q1 Deliverables Review" overdue 5d                          │
│    "Monthly Report" overdue 3d                                  │
│    "Asset Delivery" overdue 1d                                  │
│    [Resolve] [Escalate]                                         │
├─────────────────────────────────────────────────────────────────┤
│ 💬 COMMUNICATION — Negative sentiment detected           [high] │
│    Issue State: awaiting_resolution                             │
│    Evidence: Gmail thread ↗                                     │
│    "Client expressed frustration about timeline delays..."      │
│    [Acknowledge] [Resolve]                                      │
└─────────────────────────────────────────────────────────────────┘

RECENT POSITIVE SIGNALS
┌─────────────────────────────────────────────────────────────────┐
│ 🟢 Invoice paid on time — INV-1389 (AED 50,000)       yesterday │
│ 🟢 Task completed ahead of schedule — "Brand Guidelines"   2d  │
│ 🟢 Positive meeting sentiment — "Client happy with progress" 3d│
└─────────────────────────────────────────────────────────────────┘
```

**Rules:**
- Show max 5 high/critical issues, sorted by severity then age
- Show max 3 recent positive signals
- Each issue must display: type, severity, state, evidence (URL or fallback)
- Action buttons depend on current state

**Action Button Mapping (Client Detail Page ↔ Inbox):**

| Client Page Action | Equivalent Inbox Action | Effect |
|--------------------|------------------------|--------|
| Acknowledge | Tag & Watch | Transitions issue to `acknowledged`; starts watch loop |
| Snooze 7d | Snooze | Transitions issue to `snoozed` |
| Resolve | (issue transition) | Transitions issue to `resolved` |
| Escalate | (issue transition) | Transitions issue to `addressing` with escalation flag |

**Note:** "Acknowledge" on client detail page is identical to "Tag & Watch" from Inbox. Both transition the issue to `acknowledged` and start the watch loop. The label differs by context (issue already exists on client page; Inbox may create it).

---

### 3.3 Tab 2: Engagements

**Purpose:** All projects and retainers for this client, grouped by brand.

```
BRAND A
┌─────────────────────────────────────────────────────────────────┐
│ ACTIVE ENGAGEMENTS                                              │
├─────────────────────────────────────────────────────────────────┤
│ Monthly Retainer 2026                              [RETAINER]   │
│   State: active                                                 │
│   Tasks: 12 open · 3 overdue · 45 completed                     │
│   Health: ██████░░░░ 58                                         │
│   [View in Asana ↗]                                             │
├─────────────────────────────────────────────────────────────────┤
│ Q1 Campaign                                         [PROJECT]   │
│   State: active                                                 │
│   Tasks: 8 open · 0 overdue · 12 completed                      │
│   Health: █████████░ 92                                         │
│   [View in Asana ↗]                                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ COMPLETED (last 12 months)                                      │
├─────────────────────────────────────────────────────────────────┤
│ Holiday Campaign 2025                   [PROJECT] — Completed   │
│   Final: 0 open · 0 overdue · 28 completed                      │
│   Completed: 2025-12-20                                         │
├─────────────────────────────────────────────────────────────────┤
│ Monthly Retainer 2025                  [RETAINER] — Completed   │
│   Final: 0 open · 0 overdue · 156 completed                     │
│   Completed: 2025-12-31                                         │
└─────────────────────────────────────────────────────────────────┘

BRAND B
┌─────────────────────────────────────────────────────────────────┐
│ ACTIVE ENGAGEMENTS                                              │
├─────────────────────────────────────────────────────────────────┤
│ Social Media Management                            [RETAINER]   │
│   State: active                                                 │
│   Tasks: 5 open · 1 overdue · 22 completed                      │
│   Health: ███████░░░ 71                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Rules:**
- Group by brand
- Within each brand: Active first, then Completed (last 12m only)
- Each engagement shows: name, type badge, state, task counts, health score
- Engagement health derived from: task completion rate, overdue ratio

---

### 3.4 Tab 3: Financials

**Purpose:** Invoice history, AR aging, payment tracking.

```
SUMMARY
┌─────────────────────────────────────────────────────────────────┐
│ ISSUED                              PAID                        │
│   2025:      AED 500,000              2025:      AED 420,000    │
│   YTD:       AED 125,000              YTD:       AED 95,000     │
│   Lifetime:  AED 1,250,000            Lifetime:  AED 1,120,000  │
└─────────────────────────────────────────────────────────────────┘

AR AGING
┌─────────────────────────────────────────────────────────────────┐
│ Total Outstanding: AED 130,000                                  │
├─────────────────────────────────────────────────────────────────┤
│ Current (not due):     AED 85,000   ████████████████░░░░  65%   │
│ 1-30 days overdue:     AED 25,000   ████░░░░░░░░░░░░░░░░  19%   │
│ 31-60 days overdue:    AED 15,000   ███░░░░░░░░░░░░░░░░░  12%   │
│ 61-90 days overdue:    AED 5,000    █░░░░░░░░░░░░░░░░░░░   4%   │
│ 90+ days overdue:      AED 0        ░░░░░░░░░░░░░░░░░░░░   0%   │
└─────────────────────────────────────────────────────────────────┘

INVOICES
┌─────────────────────────────────────────────────────────────────┐
│ Invoice      Issue Date    Amount        Status        Aging    │
├─────────────────────────────────────────────────────────────────┤
│ INV-1456     2026-01-15    AED 45,000    SENT          current  │
│ INV-1423     2025-12-01    AED 35,000    OVERDUE       45d      │
│ INV-1398     2025-11-15    AED 50,000    PAID          —        │
│ INV-1367     2025-10-01    AED 40,000    PAID          —        │
│ INV-1334     2025-09-01    AED 30,000    PAID          —        │
│ ...                                                              │
└─────────────────────────────────────────────────────────────────┘
[Show more] — Pagination: 10 per page
```

**Rules:**
- Summary shows Issued/Paid for: current year, YTD, lifetime
- AR aging shows 5 buckets with visual bars
- Invoice table: sortable by date/amount/status, paginated
- Invoice row shows: number, issue date, amount, status, aging (if overdue)
- No deep link to Xero; show "open in Xero" as plain text (user copies invoice number)

---

### 3.5 Tab 4: Signals

**Purpose:** All signals (good/neutral/bad) from the last 30 days, with source attribution.

```
SIGNAL SUMMARY (Last 30 Days)
┌─────────────────────────────────────────────────────────────────┐
│ 🟢 Good: 12     🟡 Neutral: 8     🔴 Bad: 5                     │
│                                                                 │
│ By Source:                                                      │
│   Tasks: 8↑ 2→ 3↓    Email: 2↑ 3→ 1↓    Chat: 1↑ 2→ 0↓          │
│   Calendar: 0↑ 1→ 0↓  Meetings: 1↑ 0→ 1↓  Minutes: 0↑ 0→ 0↓     │
│   Xero: 1↑ 0→ 1↓                                                │
└─────────────────────────────────────────────────────────────────┘

SIGNALS
┌─────────────────────────────────────────────────────────────────┐
│ Filter: [All ▼] [Good ▼] [Neutral ▼] [Bad ▼]                    │
│ Source: [All ▼] [Tasks] [Email] [Chat] [Calendar] [Meetings]    │
│         [Minutes] [Xero]                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 🟢 GOOD — Task completed on time                      yesterday │
│    Source: Tasks · Brand A: Monthly Retainer                    │
│    "Q1 Brand Guidelines" completed 2d ahead of deadline         │
│    [View in Asana ↗]                                            │
├─────────────────────────────────────────────────────────────────┤
│ 🔴 BAD — Task overdue                                       2d  │
│    Source: Tasks · Brand A: Monthly Retainer                    │
│    "Monthly Report January" overdue by 3 days                   │
│    Assigned to: Sarah                                           │
│    [View in Asana ↗]                                            │
├─────────────────────────────────────────────────────────────────┤
│ 🟢 GOOD — Invoice paid on time                              3d  │
│    Source: Xero                                                 │
│    INV-1398 · AED 50,000 · Paid 2026-01-12                      │
├─────────────────────────────────────────────────────────────────┤
│ 🟡 NEUTRAL — Meeting scheduled                              3d  │
│    Source: Calendar                                             │
│    "Quarterly Review" scheduled for 2026-01-20                  │
│    Attendees: Sarah, Mike, Client Team                          │
├─────────────────────────────────────────────────────────────────┤
│ 🟢 GOOD — Positive meeting sentiment                        5d  │
│    Source: Minutes · Gemini                                     │
│    "Client expressed satisfaction with campaign performance"    │
│    Sentiment score: 0.85                                        │
│    [View Meeting Recording ↗] [View Transcript]                 │
├─────────────────────────────────────────────────────────────────┤
│ 🔴 BAD — Negative email sentiment                           7d  │
│    Source: Email                                                │
│    "We're disappointed with the turnaround time on revisions"   │
│    Thread: "Re: Q4 Campaign Assets"                             │
│    [View Thread ↗]                                              │
├─────────────────────────────────────────────────────────────────┤
│ 🟡 NEUTRAL — Chat activity                                  8d  │
│    Source: Chat                                                 │
│    12 messages exchanged in #brand-a-project                    │
│    Topics: asset delivery, timeline clarification               │
└─────────────────────────────────────────────────────────────────┘
[Load more] — Infinite scroll
```

**Rules:**
- Default filter: All signals, sorted by recency
- Each signal shows: sentiment, type, timestamp, source, excerpt/summary, link (if available)
- Meeting minutes signals must attribute to Gemini analysis
- Signals without URLs show excerpt only (no broken link affordance)

---

### 3.6 Tab 5: Team

**Purpose:** Internal team involvement, workload, and performance indicators.

```
TEAM INVOLVEMENT (Last 30 Days)
┌─────────────────────────────────────────────────────────────────┐
│ Team Member       Role              Hours*    Tasks    Overdue  │
├─────────────────────────────────────────────────────────────────┤
│ Sarah Johnson     Account Lead      48 hrs    28       2        │
│ Mike Chen         Designer          32 hrs    15       0        │
│ Alex Rivera       Developer         24 hrs    12       1        │
│ Jordan Lee        Copywriter        16 hrs    8        0        │
└─────────────────────────────────────────────────────────────────┘
* Hours estimated from task metadata (not time tracking)

WORKLOAD DISTRIBUTION
┌─────────────────────────────────────────────────────────────────┐
│ Sarah     ████████████████████░░░░  80% capacity                │
│ Mike      ██████████████░░░░░░░░░░  56% capacity                │
│ Alex      ████████████░░░░░░░░░░░░  48% capacity                │
│ Jordan    ████████░░░░░░░░░░░░░░░░  32% capacity                │
└─────────────────────────────────────────────────────────────────┘

TARDINESS (Tasks Overdue by Assignee — Last 90 Days)
┌─────────────────────────────────────────────────────────────────┐
│ Sarah Johnson:  4 tasks overdue (avg 3.2 days late)             │
│ Alex Rivera:    2 tasks overdue (avg 1.5 days late)             │
│ Mike Chen:      0 tasks overdue                                 │
│ Jordan Lee:     0 tasks overdue                                 │
└─────────────────────────────────────────────────────────────────┘

RECENT ACTIVITY
┌─────────────────────────────────────────────────────────────────┐
│ Sarah — Completed "Q1 Brand Guidelines"               yesterday │
│ Mike — Started "Homepage Redesign Mockups"                  1d  │
│ Sarah — Overdue "Monthly Report January"                    3d  │
│ Alex — Completed "API Integration"                          4d  │
└─────────────────────────────────────────────────────────────────┘
```

**Rules:**
- Hours are estimated from task metadata (story points, complexity tags, or estimate fields) — not time tracking
- Capacity is relative to team member's typical load (derived from historical average)
- Tardiness shows overdue count and average lateness
- Recent activity shows last 10 task state changes

---

## 4. Recently Active Client Drilldown

**Purpose:** Limited view for clients not actively invoiced but with recent history.

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Index                                                 │
│                                                                 │
│ CLIENT NAME                                   [Recently Active] │
└─────────────────────────────────────────────────────────────────┘

HISTORICAL TOTALS
┌─────────────────────────────────────────────────────────────────┐
│ Total Issued:  AED 850,000          Total Paid:  AED 850,000    │
│ Last invoice:  2025-09-15                                       │
│ Relationship:  2022-03-01 to 2025-09-15 (3.5 years)             │
└─────────────────────────────────────────────────────────────────┘

LAST 5 INVOICES
┌─────────────────────────────────────────────────────────────────┐
│ Invoice      Issue Date    Amount        Status                 │
├─────────────────────────────────────────────────────────────────┤
│ INV-1234     2025-09-15    AED 25,000    PAID                   │
│ INV-1189     2025-07-01    AED 30,000    PAID                   │
│ INV-1156     2025-05-15    AED 45,000    PAID                   │
│ INV-1098     2025-03-01    AED 50,000    PAID                   │
│ INV-1045     2025-01-15    AED 35,000    PAID                   │
└─────────────────────────────────────────────────────────────────┘

BRANDS
┌─────────────────────────────────────────────────────────────────┐
│ Brand A · Brand B                                               │
└─────────────────────────────────────────────────────────────────┘
```

**Relationship derivation:** Display as `{first_invoice_date} to {last_invoice_date} ({years} years)` where years = `floor((last - first) / 365.25 * 10) / 10`.

**Not shown:**
- ❌ Engagements tab
- ❌ Signals tab
- ❌ Team tab
- ❌ Open issues
- ❌ Health score

---

## 5. Cold Clients

**Not clickable.** Card on index page only.

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT NAME                                              [Cold] │
├─────────────────────────────────────────────────────────────────┤
│ Historical: AED 350,000 issued / AED 350,000 paid               │
│ Last invoice: 2024-02-10                                        │
└─────────────────────────────────────────────────────────────────┘
```

**Styling:** Greyed out. Cursor: default (not pointer).

**Access via Deep Links / Notifications:**

Cold clients are not navigable from the index, but snapshots remain accessible via:
- Direct URL: `/clients/:id/snapshot?issue_id=<uuid>`
- Inbox item links (if an issue surfaces for a cold client during detector run)
- Notification links

This ensures issues flagged against cold clients (e.g., from stale data cleanup) can still be actioned without re-enabling the full client detail page.

---

## 6. Canonical Data + Logic Contract

### 6.1 Client Status Logic

```
Active:          MAX(invoices.issue_date) >= today - 90 days
Recently Active: MAX(invoices.issue_date) >= today - 270 days AND MAX(invoices.issue_date) < today - 90 days
Cold:            MAX(invoices.issue_date) < today - 270 days OR no invoices
```

Status is computed, not stored. Recomputed on each query.

**Boundary Conditions (explicit):**

| Last Invoice Date | Status |
|-------------------|--------|
| Exactly 90 days ago (today - 90) | **Active** (inclusive: `>=`) |
| 91 days ago | Recently Active |
| Exactly 270 days ago (today - 270) | **Recently Active** (inclusive: `>=`, exclusive: `<` for 90-day boundary) |
| 271 days ago | Cold |
| No invoices ever | Cold |

**No invoices fallback:** Clients without invoices are classified as `cold`.

---

### 6.2 Finance Metrics

**Invoice Status Values (canonical):**

| Status | API Value | Definition |
|--------|-----------|------------|
| Draft | `draft` | Not yet sent (excluded from all metrics) |
| Sent | `sent` | Sent, not yet due |
| Overdue | `overdue` | Past due date, unpaid |
| Paid | `paid` | Fully paid |
| Voided | `voided` | Cancelled (excluded from issued metrics) |

---

**Issued (issuance-based):**

| Metric | Formula |
|--------|---------|
| Issued 2025 | `SUM(amount) WHERE issue_date IN 2025 AND status != 'voided'` |
| Issued YTD | `SUM(amount) WHERE issue_date >= year_start AND status != 'voided'` |
| Issued Last 12m | `SUM(amount) WHERE issue_date >= today - 365 AND status != 'voided'` |
| Issued Prev 12m | `SUM(amount) WHERE issue_date BETWEEN today - 730 AND today - 366 AND status != 'voided'` |
| Issued Lifetime | `SUM(amount) WHERE status != 'voided'` |

**Paid (cash-based):**

| Metric | Formula |
|--------|---------|
| Paid 2025 | `SUM(amount) WHERE payment_date IN 2025 AND status = 'paid'` |
| Paid YTD | `SUM(amount) WHERE payment_date >= year_start AND status = 'paid'` |
| Paid Last 12m | `SUM(amount) WHERE payment_date >= today - 365 AND status = 'paid'` |
| Paid Prev 12m | `SUM(amount) WHERE payment_date BETWEEN today - 730 AND today - 366 AND status = 'paid'` |
| Paid Lifetime | `SUM(amount) WHERE status = 'paid'` |

**AR (outstanding):**

| Metric | Formula |
|--------|---------|
| AR_outstanding | `SUM(amount) WHERE status IN ('sent', 'overdue')` |
| AR_overdue | `SUM(amount) WHERE status = 'overdue'` |
| AR by bucket | `SUM(amount) WHERE status = 'overdue' GROUP BY aging_bucket` |

**Note:** `AR_outstanding` is the canonical name for total unpaid. In formulas, `AR_total = AR_outstanding`.

---

**AR Aging Buckets (canonical):**

| Bucket | API Value | Formula |
|--------|-----------|---------|
| Current (not due) | `current` | `due_date > today AND status = 'sent'` |
| 1-30 days overdue | `1_30` | `status = 'overdue' AND days_overdue BETWEEN 1 AND 30` |
| 31-60 days overdue | `31_60` | `status = 'overdue' AND days_overdue BETWEEN 31 AND 60` |
| 61-90 days overdue | `61_90` | `status = 'overdue' AND days_overdue BETWEEN 61 AND 90` |
| 90+ days overdue | `90_plus` | `status = 'overdue' AND days_overdue > 90` |

**Data Quality Edge Cases:**

| Condition | Handling |
|-----------|----------|
| `status = 'sent'` AND `due_date <= today` | Treat as overdue for aging; flag as `flagged_signal` with rule `invoice_status_inconsistent` |
| `status = 'overdue'` AND `due_date IS NULL` | Display in "90+" bucket; flag as data quality issue |
| `days_overdue` calculation | `MAX(0, today - due_date)` — negative values clamped to 0 |

---

**Partial payment simplification (v1):**

v1 treats invoices as fully paid or fully unpaid. No partial payment tracking.

| Field | Value |
|-------|-------|
| `amount` | Original invoice amount |
| `amount_paid` | = `amount` if `status = 'paid'`, else 0 |
| `amount_due` | = `amount` if `status IN ('sent', 'overdue')`, else 0 |
| `payment_date` | Date invoice status changed to PAID (not individual payment dates) |

---

### 6.3 Task Linking

**Invariant:**
```
tasks.engagement_id = engagements.id  (internal UUID)
tasks.engagement_id IS NOT engagements.asana_project_id
```

**Note:** In this context, "project" refers to an Asana project; the database entity is `engagements`.

**Linking rules:**
1. Fetch Asana task to get project membership GIDs
2. Match GIDs against `engagements.asana_project_id` in DB
3. Exactly 1 match → link (`tasks.engagement_id = matched engagement UUID`)
4. 0 matches → orphan (add to fix queue)
5. Multiple matches → ambiguous (add to fix queue, never pick first)

**Hard rule — no name/substring matching for tasks:**
- ❌ Match by name/substring
- ❌ Use legacy `tasks.project` field
- ❌ Auto-create engagements
- ❌ Pick first when multiple match

**Contrast with Engagement Resolver (6.8):** Engagement Resolver MAY use name matching to *propose* links with low confidence. Task Linking MUST NOT use name matching at all.

**Client derivation:**
```
Task's client = tasks.engagement_id → engagements.client_id
```
Always derived via join. Never stored on task.

---

### 6.4 Evidence Rules

**Surfaced issues must have:**
- `source_url` (deep link to source system), **OR**
- Deterministic fallback proof (e.g., invoice number + amount + due date + aging)

**Invoice issue fallback:**
```
Evidence:
  Invoice: INV-1234
  Amount: AED 45,000
  Due: 2025-12-15 (45 days overdue)
  (open in Xero)
```
No arrow/link affordance if URL unavailable.

**Task issue evidence:**
```
Evidence:
  View in Asana ↗
  https://app.asana.com/0/{project_gid}/{task_gid}
```

**Email/Chat evidence:**
```
Evidence:
  View Thread ↗
  Excerpt: "We're disappointed with the turnaround..."
```

**Meeting minutes evidence:**
```
Evidence:
  Source: Minutes · Gemini
  Excerpt: "Client expressed concern about..."
  Sentiment score: -0.65
  [View Recording ↗] [View Transcript]
```

---

**Minimum Evidence by Inbox Item Type:**

| Item Type | Required Evidence | Example |
|-----------|------------------|---------|
| **Issue** | URL or deterministic fallback proof | Invoice: INV-1234, AED 35,000, 45d overdue |
| **Flagged Signal** | Excerpt + source + timestamp + triggering rule | "Meeting cancelled 2h before start" · Calendar · 2026-01-15T10:00 · Rule: `meeting_cancelled_short_notice` |
| **Orphan** | Raw identifier + linkage failure reason | Asana GID: 1234567890 · "No matching engagement in DB" |
| **Ambiguous** | Candidate list with match reasons | Candidates: [Project A (invoice_reference_parse, 85%), Project B (email_subject_parse, 60%)] |

---

**Detector Rules (canonical):**

| Rule ID | Signal Source | Trigger Condition |
|---------|---------------|-------------------|
| `meeting_cancelled_short_notice` | calendar | Meeting cancelled < 24h before start |
| `email_unanswered_48h` | gmail | Email from client unanswered for 48+ hours |
| `task_overdue` | asana | Task past due_date |
| `sentiment_negative` | gmail, gchat, minutes | Sentiment score < -0.3 |
| `escalation_keyword` | gchat | Contains: "urgent", "escalate", "problem" |
| `invoice_overdue` | xero | Invoice past due_date |
| `invoice_status_inconsistent` | xero | `status = 'sent'` AND `due_date <= today` |

**Financial Issue Aggregation Threshold:**

`financial_issue_threshold = 1` — A financial issue is created as soon as ONE qualifying overdue invoice exists.

**Invoice Anomaly Precedence (Decision C enforcement):**

When processing invoices in a detector run:
1. If invoice qualifies for financial issue (overdue) → create/update financial issue
2. If a financial issue exists for the invoice → do NOT create `invoice_status_inconsistent` flagged_signal
3. If NO financial issue exists AND `status='sent'` AND `due_date <= today` → create `invoice_status_inconsistent` flagged_signal

This prevents duplicate proposals for the same invoice.

---

**Flagged Signal evidence structure:**
```json
{
  "excerpt": "Quarterly Review cancelled 2h before start",
  "source": "calendar",
  "source_id": "event_abc123",
  "timestamp": "2026-01-15T10:00:00Z",
  "rule_triggered": "meeting_cancelled_short_notice",
  "rule_params": { "threshold_hours": 24, "actual_hours": 2 }
}
```

**Orphan evidence structure:**
```json
{
  "raw_identifier": { "type": "asana_gid", "value": "1234567890" },
  "linkage_failure": "no_matching_engagement",
  "attempted_matches": [],
  "source_signal": { "id": "signal_xyz", "type": "task_created" }
}
```

**Ambiguous evidence structure:**
```json
{
  "candidates": [
    { "id": "uuid1", "name": "Project A", "match_type": "invoice_reference_parse", "confidence": 0.85 },
    { "id": "uuid2", "name": "Project B", "match_type": "email_subject_parse", "confidence": 0.60 }
  ],
  "source_signal": { "id": "signal_xyz" },
  "requires_user_selection": true
}
```

**Valid `match_type` values (per 6.8 Engagement Resolver):**

| Match Type | Confidence Range | Description |
|------------|------------------|-------------|
| `asana_project_gid` | ≥0.95 (High) | Exact GID match |
| `invoice_reference_parse` | 0.70-0.94 (Medium) | Project name parsed from invoice description |
| `meeting_title_parse` | 0.40-0.69 (Low) | Project name parsed from meeting title/body |
| `email_subject_parse` | 0.40-0.69 (Low) | Project pattern parsed from email thread subject |
| `name_substring` | 0.40-0.69 (Low) | Substring match on engagement/project name |

---

### 6.5 Issue Lifecycle

```
          ┌─────────────────────────────────────────────────────┐
          │                    ISSUE LIFECYCLE                   │
          └─────────────────────────────────────────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │   detected   │ ← signals aggregated
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │   surfaced   │ ← proposed to user with context/proof
                            └──────┬───────┘
                                   │
                          user action required
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            ┌──────────────┐ ┌──────────┐ ┌──────────────┐
            │ acknowledged │ │ snoozed  │ │  (suppress)  │ ← suppressed flag, no state change
            └──────┬───────┘ └────┬─────┘ └──────────────┘
                   │              │
                   │              │ timer expires
                   │              ▼
                   │        ┌──────────────┐
                   │        │   surfaced   │ (returns)
                   │        └──────────────┘
                   ▼
            ┌──────────────┐
            │  addressing  │ ← assigned, work in progress
            └──────┬───────┘
                   │
                   ▼
            ┌────────────────────┐
            │ awaiting_resolution│ ← waiting for confirmation / context
            └──────┬─────────────┘
                   │
                   ▼
            ┌──────────────┐
            │   resolved   │ ← issue handled
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │  regression  │ ← 90-day watch period
            │    watch     │
            └──────┬───────┘
                   │
          ┌────────┴────────┐
          ▼                  ▼
   ┌──────────────┐   ┌──────────────┐
   │    closed    │   │  regressed   │ → back to surfaced
   └──────────────┘   └──────────────┘
```

**States (10 total):**

| # | State | API Value | Definition |
|---|-------|-----------|------------|
| 1 | `detected` | `detected` | Signals aggregated, issue identified |
| 2 | `surfaced` | `surfaced` | Proposed to user with context/proof |
| 3 | `snoozed` | `snoozed` | User deferred action; returns to surfaced when timer expires |
| 4 | `acknowledged` | `acknowledged` | User tagged/confirmed |
| 5 | `addressing` | `addressing` | Work in progress |
| 6 | `awaiting_resolution` | `awaiting_resolution` | Waiting for confirmation (renamed from "monitoring" to avoid collision with watch loop) |
| 7 | `resolved` | `resolved` | Issue handled |
| 8 | `regression_watch` | `regression_watch` | 90-day watch period |
| 9 | `closed` | `closed` | Fully resolved, no regression |
| 10 | `regressed` | `regressed` | Issue recurred, back to surfaced |

**Note:** State numbers indicate enumeration order, not lifecycle sequence. See diagram for actual transitions.

**Open states (UI display):** `detected`, `surfaced`, `snoozed`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`

**Closed states (UI display):** `resolved`, `regression_watch`, `closed`

**Health-counted states (penalty calculation):** `surfaced`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`

(Excludes `detected` because not yet visible to user; excludes `snoozed` because user deferred action)

**Snoozed issues:**

Issues can be snoozed directly (from client detail page, not just inbox). When snoozed:

| Field | Value |
|-------|-------|
| `issues.state` | `snoozed` |
| `issues.snoozed_until` | Timestamp when snooze expires |
| `issues.snoozed_by` | UUID of user who snoozed |
| `issues.snoozed_at` | Timestamp of snooze action |
| `issues.snooze_reason` | Optional note |

When `snoozed_until` passes, issue transitions back to `surfaced`.

**Snoozed issues are:**
- ❌ Excluded from health scoring
- ❌ Excluded from open issues counts (by default)
- ✅ Included in `/api/clients/:id/issues?state=snoozed` or `?include_snoozed=true`

**Issue Snooze ↔ Inbox Item Behavior:**

When an issue is snoozed directly from the client detail page (not via inbox):

1. If an active inbox item exists for this issue (`underlying_issue_id = issue.id` AND `state IN ('proposed', 'snoozed')`):
   - Transition inbox item to `linked_to_issue`
   - Set `inbox_items.resolved_at = now()`
   - Set `inbox_items.resolved_issue_id = issue.id`
   - Rationale: Client page action is the "proposal resolution" — user addressed it directly

2. No active inbox item exists:
   - No inbox action needed; issue snooze proceeds normally

This prevents contradictory UX where issue is snoozed (hidden) but inbox item remains in "Needs Attention".

**Suppressed issues:**

Issues with `suppressed = true` are excluded from:
- Health scoring
- Open issues counts
- Inbox surfacing

Suppression does not change the issue state — it's a parallel flag.

Default API behavior: `suppressed = false`. Override with `?include_suppressed=true`.

---

**Issue Transition Audit Trail (Required):**

All issue state transitions must be logged to `issue_transitions`:

```sql
CREATE TABLE issue_transitions (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL REFERENCES issues(id),
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL,
  transition_reason TEXT NOT NULL,   -- 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation'
  trigger_signal_id TEXT,            -- nullable, references signals(id) if signal-triggered
  trigger_rule TEXT,                 -- e.g., 'snooze_expired', '90d_regression_cleared'
  actor TEXT NOT NULL,               -- 'system' or user_id
  actor_note TEXT,                   -- optional user-provided note
  transitioned_at TEXT NOT NULL      -- ISO timestamp
);

CREATE INDEX idx_issue_transitions_issue ON issue_transitions(issue_id);
CREATE INDEX idx_issue_transitions_timestamp ON issue_transitions(transitioned_at);
```

**Snooze Timer Execution:**

Snooze expiry is executed by a **scheduled job** (runs hourly):

1. Query: `SELECT * FROM issues WHERE state = 'snoozed' AND snoozed_until <= now()`
2. For each expired issue:
   - Update `issues.state = 'surfaced'`
   - Clear snooze fields: `snoozed_until = NULL`, `snoozed_by = NULL`, `snoozed_at = NULL`
   - Insert transition row:
     ```sql
     INSERT INTO issue_transitions (
       id, issue_id, previous_state, new_state,
       transition_reason, trigger_rule, actor, transitioned_at
     ) VALUES (
       uuid(), issue.id, 'snoozed', 'surfaced',
       'system_timer', 'snooze_expired', 'system', now()
     );
     ```

**Example transition entries:**

| issue_id | previous_state | new_state | transition_reason | trigger_rule | actor |
|----------|----------------|-----------|-------------------|--------------|-------|
| uuid1 | detected | surfaced | system_aggregation | threshold_reached | system |
| uuid1 | surfaced | snoozed | user | NULL | user_abc |
| uuid1 | snoozed | surfaced | system_timer | snooze_expired | system |
| uuid1 | surfaced | acknowledged | user | NULL | user_abc |
| uuid2 | regression_watch | closed | system_timer | 90d_regression_cleared | system |
| uuid3 | regression_watch | regressed | system_signal | signal_recurrence | system |

---

### 6.6 Health Score Formula

**Health-counted states (for penalty):**

| State | Counts Toward Health Penalty | Rationale |
|-------|------------------------------|-----------|
| `detected` | ❌ No | Not yet surfaced to user |
| `snoozed` | ❌ No | User deferred action |
| `surfaced` | ✅ Yes | Awaiting action |
| `acknowledged` | ✅ Yes | Tagged but not resolved |
| `addressing` | ✅ Yes | Work in progress |
| `awaiting_resolution` | ✅ Yes | Still tracking |
| `resolved` | ❌ No | Handled |
| `regression_watch` | ❌ No | In grace period |
| `closed` | ❌ No | Fully closed |
| `regressed` | ✅ Yes | Problem recurred |

---

**Client Health (v1 — provisional):**

```python
def client_health(client):
    AR_outstanding = sum(invoices where status in ('sent', 'overdue'))
    AR_overdue = sum(invoices where status = 'overdue')

    # Safe ratio calculation
    if AR_outstanding == 0:
        overdue_ratio = 0
    else:
        overdue_ratio = min(1.0, AR_overdue / AR_outstanding)

    AR_penalty = floor(min(40, overdue_ratio * 60))

    # Issue penalty (only high/critical, only health-counted states)
    open_issues = count(issues where
        severity in ('high', 'critical') AND
        state in ('surfaced', 'acknowledged', 'addressing', 'awaiting_resolution', 'regressed') AND
        suppressed = false
    )
    Issue_penalty = min(30, open_issues * 10)

    return max(0, 100 - AR_penalty - Issue_penalty)
```

**Invariants:**
- All values are integers
- `overdue_ratio` is clamped to [0, 1]
- Divide-by-zero handled explicitly
- Suppressed issues excluded
- Only `high` and `critical` severity issues affect health; `medium`, `low`, `info` do not

**Why "provisional":** Task-based signals not yet factored in (requires task linking completion). Once tasks are linked, v2 formula adds:
```python
Task_penalty = floor(min(20, overdue_task_ratio * 30))
Signal_bonus = floor(min(10, positive_signal_ratio * 15))
```

---

**Engagement Health (v1):**

```python
def engagement_health(engagement):
    asana_project_id = engagement.asana_project_id

    # Canonical task counts (one definition, one name)
    open_tasks_in_source = count(
        tasks in Asana project
        WHERE NOT completed AND NOT archived AND parent IS NULL
    )
    linked_open_tasks = count(
        DB tasks WHERE engagement_id = engagement.id AND NOT completed
    )

    # Gating check 1: must have open tasks in source project
    if open_tasks_in_source == 0:
        return None, "no_tasks"

    # Gating check 2: require sufficient task linking coverage
    linked_pct = linked_open_tasks / open_tasks_in_source
    if linked_pct < 0.90:
        return None, "task_linking_incomplete"

    # Health calculation uses linked open tasks
    tasks_total = linked_open_tasks
    tasks_overdue = count(overdue tasks WHERE engagement_id = engagement.id AND NOT completed)

    # Safe ratio calculation
    overdue_ratio = min(1.0, tasks_overdue / tasks_total)
    Overdue_penalty = floor(min(50, overdue_ratio * 80))

    # Completion lag (uses completed linked tasks)
    # Exclude tasks where days_late is null (no due_date)
    avg_days_late = average(
        days_late for completed tasks
        WHERE engagement_id = engagement.id AND days_late IS NOT NULL
    )  # 0 if all on time or no completed tasks
    Completion_lag = floor(min(30, avg_days_late * 5))

    return max(0, 100 - Overdue_penalty - Completion_lag), None
```

**Canonical Task Definitions:**

| Term | Definition |
|------|------------|
| `open_tasks_in_source` | Count of open, not archived, top-level tasks in Asana project |
| `linked_open_tasks` | Count of DB tasks linked to engagement where task is open |
| `linked_pct` | `linked_open_tasks / open_tasks_in_source` |

**Invariants:**
- All values are integers
- Ratios clamped to [0, 1]
- Returns `(None, gating_reason)` if gating conditions not met
- `avg_days_late` excludes tasks where `days_late IS NULL` (no due_date)

---

**Thresholds:**

| Score | Label | Color |
|-------|-------|-------|
| 0-39 | Poor | Red |
| 40-69 | Fair | Amber |
| 70-100 | Good | Green |
| N/A | N/A | Grey |

---

### 6.7 Engagement Lifecycle

**Engagement Types (canonical):**

| Type | API Value | Definition |
|------|-----------|------------|
| Project | `project` | Time-bound deliverable with defined scope |
| Retainer | `retainer` | Ongoing service agreement, typically monthly |

---

**State Machine:**

```
                            ┌──────────────────────────────────────────┐
                            │         ENGAGEMENT LIFECYCLE              │
                            └──────────────────────────────────────────┘

    ┌───────────┐
    │  planned  │ ← Created from Asana/invoice/meeting minutes
    └─────┬─────┘
          │ first task started OR kickoff meeting occurred
          ▼
    ┌───────────┐
    │  active   │ ← Work in progress
    └─────┬─────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│ blocked │ │ paused  │ ← Manual or signal-triggered
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           │ unblocked / resumed
           ▼
    ┌───────────┐
    │  active   │
    └─────┬─────┘
          │ final deliverables in progress
          ▼
    ┌────────────┐
    │ delivering │ ← Final tasks being completed
    └─────┬──────┘
          │ all tasks completed OR delivery confirmation
          ▼
    ┌───────────┐
    │ delivered │ ← Awaiting client confirmation
    └─────┬─────┘
          │ invoice paid OR explicit sign-off OR 30d timeout
          ▼
    ┌───────────┐
    │ completed │ ← Archived, counts toward history
    └───────────┘
```

**State Definitions (7 total):**

| State | API Value | Definition | Trigger to Enter |
|-------|-----------|------------|------------------|
| `planned` | `planned` | Created but no work started | Engagement created |
| `active` | `active` | Work in progress | First task started OR kickoff meeting |
| `blocked` | `blocked` | Cannot proceed (external dependency) | Manual flag OR "blocked" keyword in signals |
| `paused` | `paused` | Intentionally paused (client request) | Manual flag OR pause signal |
| `delivering` | `delivering` | Final phase, wrapping up | ≥80% tasks completed AND remaining open tasks have Asana tag "final-deliverable" or are in section named "Final" |
| `delivered` | `delivered` | Work complete, awaiting confirmation | All tasks completed OR delivery email/meeting signal |
| `completed` | `completed` | Fully closed | Invoice paid OR explicit sign-off OR 30d after delivered |

**Heuristic Triggers (v1 — Best-Effort, Non-Test-Critical):**

| Trigger | Signal Source | Effect |
|---------|---------------|--------|
| Task started | Asana | `planned` → `active` |
| Kickoff meeting | Calendar/Minutes | `planned` → `active` |
| "Blocked" keyword | Email/Chat/Asana | → `blocked` |
| "On hold" / "Paused" | Email/Chat | → `paused` |
| 80%+ tasks complete | Asana | → `delivering` |
| "Final delivery" email | Gmail | → `delivered` |
| "Approved" in minutes | Gemini | → `delivered` |
| Invoice paid | Xero | → `completed` |
| 30d after delivered | Timer | → `completed` |

**Heuristic Behavior Notes:**
- These triggers are pattern-based and may have false positives/negatives
- Debounce: require condition for 2 consecutive syncs before transitioning
- Confidence thresholds apply (pattern match score > 0.7)
- Users can always manually override via `POST /api/engagements/:id/transition`
- Not recommended for automated testing; test manual transitions instead

---

**Transition Audit Trail (Required):**

All state transitions must be logged to `engagement_transitions`:

```sql
CREATE TABLE engagement_transitions (
  id TEXT PRIMARY KEY,
  engagement_id TEXT NOT NULL REFERENCES engagements(id),
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL,
  transition_reason TEXT NOT NULL,  -- 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation'
  trigger_signal_id TEXT,           -- nullable, references signals(id) if signal-triggered
  trigger_rule TEXT,                -- e.g., 'tasks_80pct_complete', '30d_timeout'
  actor TEXT NOT NULL,              -- 'system' or user_id
  actor_note TEXT,                  -- optional user-provided note
  transitioned_at TEXT NOT NULL     -- ISO timestamp
);
```

**Example entries:**

| engagement_id | previous_state | new_state | transition_reason | trigger_rule | actor |
|---------------|----------------|-----------|-------------------|--------------|-------|
| uuid1 | planned | active | system_signal | task_started | system |
| uuid1 | active | delivering | system_threshold | tasks_80pct_complete | system |
| uuid1 | delivering | delivered | system_signal | delivery_email_detected | system |
| uuid1 | delivered | completed | system_timer | 30d_timeout | system |
| uuid2 | active | paused | user | NULL | user_abc |

---

### 6.8 Engagement Creation & Linking

**Hard Rule: No Implicit Cross-Client Linking**

If client cannot be determined deterministically, the signal goes to Inbox as orphan/ambiguous. Never auto-link a signal to an engagement belonging to a different client than the signal's apparent source.

**Hard Rule: Name Matching Only for Engagement Resolver (not Task Linking)**

Name/substring matching is allowed ONLY in the Engagement Resolver to propose low-confidence candidates. It is NEVER allowed for Task Linking (see 6.3).

---

**Engagement Resolver (priority order):**

| Priority | Source | Match Logic | Confidence | Auto-Link? |
|----------|--------|-------------|------------|------------|
| 1 | Asana Project | `asana_project_gid` → `engagements.asana_project_id` | ≥0.95 (High) | ✅ Yes |
| 2 | Invoice Reference | Parse invoice description for project/retainer name | 0.70-0.94 (Medium) | ❌ No — propose in Inbox |
| 3 | Meeting Title | Parse meeting title/body for project name | 0.40-0.69 (Low) | ❌ No — suggest candidates only |
| 4 | Email Thread | Parse thread subject for project/retainer pattern | 0.40-0.69 (Low) | ❌ No — suggest candidates only |

**Confidence Thresholds and Actions:**

| Confidence | Range | Action |
|------------|-------|--------|
| **High** | ≥0.95 | Auto-link (no user action needed) |
| **Medium** | 0.70-0.94 | Propose in Inbox with "Link to Engagement" action |
| **Low** | 0.40-0.69 | Show as "Suggested candidates" — user must explicitly select |
| **None** | <0.40 | Orphan — no candidates shown |

**Resolution Outcomes:**

| Outcome | Condition | Action |
|---------|-----------|--------|
| **Linked** | Exactly 1 match with confidence ≥0.95 | Auto-associate signal with engagement |
| **Proposed** | 1+ matches with confidence 0.70-0.94 | Inbox item with "Link to Engagement" action |
| **Suggested** | 1+ matches with confidence 0.40-0.69 | Inbox item with candidate list (user must select) |
| **Orphan** | 0 matches OR all <0.40 | Inbox item (`orphan`) |
| **Ambiguous** | Multiple matches ≥0.70 | Inbox item (`ambiguous`) — must select |

---

**Engagement Creation Sources:**

| Source | Creates Engagement When | Type | Requires Confirmation |
|--------|------------------------|------|----------------------|
| Asana | New project created with client tag | Project or Retainer | ❌ No (auto-create) |
| Invoice | New invoice references unknown project name | Inferred | ✅ Yes |
| Meeting | Kickoff meeting with project name pattern | Inferred | ✅ Yes |
| Manual | User creates via Control Room | Confirmed | ❌ No |

---

**Fix Queue Types:**

| Type | Trigger | Resolution Options | Maps to Inbox Type |
|------|---------|-------------------|-------------------|
| `engagement_orphan` | Signal references engagement not in DB | Create new / Link existing / Dismiss | `orphan` |
| `engagement_ambiguous` | Signal could match multiple engagements | Select primary / Merge duplicates | `ambiguous` |
| `engagement_unlinked_client` | Engagement exists but no client assigned | Link to client / Mark internal | (surfaced as issue) |

---

### 6.9 Recently Active Exclusions (Intentional)

**Confirmed:** Recently Active client drilldown excludes:
- ❌ Open issues
- ❌ Signals
- ❌ Health score
- ❌ Team involvement

**Rationale:** Recently Active clients show history only. Any out-of-norm items requiring attention appear in **Control Room → Inbox**, regardless of client status. This ensures:
1. Recently Active drilldown stays simple (historical reference)
2. Urgent items are never hidden (Inbox catches all surfaced issues)
3. No duplicate attention surfaces

---

**Inbox Overrides Segment Clickability:**

When you click a client name from an Inbox item, you always get a usable view — even if the client is Cold.

| Client Status | Normal Index Behavior | From Inbox Item |
|---------------|----------------------|-----------------|
| Active | Full drilldown | Full drilldown |
| Recently Active | Limited drilldown | Limited drilldown + issue context panel |
| Cold | Not clickable | **Client Snapshot view** (read-only) |

**Client Snapshot View (Cold clients from Inbox):**

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT NAME                                     [Cold] [Snapshot]│
├─────────────────────────────────────────────────────────────────┤
│ Historical: AED 350,000 issued / AED 350,000 paid               │
│ Last invoice: 2024-02-10                                        │
│ Relationship: 2021-06-01 to 2024-02-10 (2.7 years)              │
├─────────────────────────────────────────────────────────────────┤
│ CONTEXT FOR THIS ISSUE                                          │
│ ────────────────────────────────────────────────────────────────│
│ 💰 Invoice 45 days overdue (the issue you clicked from)         │
│    INV-1234 · AED 35,000 · Due 2025-12-20                       │
│    [Tag & Watch] [Dismiss]                                      │
├─────────────────────────────────────────────────────────────────┤
│ RELATED SIGNALS (last 5 linked to this issue or client, 90d)   │
│ (none)                                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Related Signals selection rule:**
- Signals linked to the same issue, OR
- Signals linked to the same client within last 90 days
- Max 5, sorted by recency

This view is read-only except for issue actions. It provides enough context to decide on the issue without navigating away.

---

### 6.10 Xero Linking (Canonical Rule)

**Xero does not provide public deep links.** Authenticated URLs require user login and are not reliably stable.

**Canonical behavior (everywhere):**
- Display: `INV-1234 (open in Xero)` — plain text, no arrow, no link
- Interaction: User copies invoice number manually
- Never render `↗` or `href` for Xero references

**Contrast with other sources:**

| Source | Link Available | Display |
|--------|----------------|---------|
| Asana | ✅ Yes | `View in Asana ↗` (clickable) |
| Gmail | ✅ Yes | `View Thread ↗` (clickable) |
| Google Chat | ✅ Yes | `View in Chat ↗` (clickable) |
| Calendar | ✅ Yes | `View Event ↗` (clickable) |
| Meet Recording | ✅ Yes | `View Recording ↗` (clickable) |
| Xero | ❌ No | `INV-1234 (open in Xero)` (plain text) |

---

### 6.11 Signal Source Mapping (UI ↔ API)

| UI Label | API `source` Value | Signal Types Included |
|----------|-------------------|-----------------------|
| Tasks | `asana` | task_completed_*, task_overdue, task_started |
| Email | `gmail` | email_sentiment_*, email_unanswered |
| Chat | `gchat` | chat_activity, chat_escalation |
| Calendar | `calendar` | meeting_scheduled, meeting_cancelled |
| Meetings | `meet` | meeting_completed |
| Minutes | `minutes` | transcript_sentiment_*, action_items_identified |
| Xero | `xero` | invoice_paid_on_time, invoice_overdue, invoice_paid_late |

**Note:** UI "Meetings" refers to Google Meet events (source=`meet`). Calendar events (scheduling) use source=`calendar`. Meeting Minutes analysis (Gemini) uses source=`minutes`.

---

### 6.12 Signals Taxonomy

**17 example signals across sources:**

| # | Source | Signal Type | Sentiment | Maps to Issue Type |
|---|--------|-------------|-----------|-------------------|
| 1 | asana | task_completed_on_time | 🟢 Good | — |
| 2 | asana | task_completed_late | 🔴 Bad | schedule_delivery |
| 3 | asana | task_overdue | 🔴 Bad | schedule_delivery |
| 4 | gmail | email_sentiment_positive | 🟢 Good | — |
| 5 | gmail | email_sentiment_negative | 🔴 Bad | communication |
| 6 | gmail | email_unanswered_48h | 🟡 Neutral → 🔴 Bad | communication |
| 7 | gchat | escalation_keyword_detected | 🔴 Bad | risk |
| 8 | gchat | chat_activity_normal | 🟡 Neutral | — |
| 9 | calendar | meeting_scheduled | 🟡 Neutral | — |
| 10 | calendar | meeting_cancelled | 🟡 Neutral → 🔴 Bad | communication |
| 11 | meet | meeting_completed | 🟡 Neutral | — |
| 12 | minutes | transcript_sentiment_positive | 🟢 Good | — |
| 13 | minutes | transcript_sentiment_negative | 🔴 Bad | communication, risk |
| 14 | minutes | action_items_identified | 🟡 Neutral | — |
| 15 | xero | invoice_paid_on_time | 🟢 Good | — |
| 16 | xero | invoice_overdue | 🔴 Bad | financial |
| 17 | xero | invoice_paid_late | 🟡 Neutral | — |

**Issue type mapping:**

| Issue Type | API Value | Triggering Signals |
|------------|-----------|-------------------|
| Schedule / Delivery | `schedule_delivery` | Task overdue, task completed late (threshold: ≥3 signals) |
| Communication | `communication` | Negative email/chat sentiment, unanswered emails, cancelled meetings |
| Financial | `financial` | Invoice overdue (any count triggers) |
| Risk | `risk` | Escalation keywords, negative meeting minutes, multiple bad signals |
| Quality | `quality` | Revision requests, rework signals (future) |
| Opportunity | `opportunity` | Positive sentiment clusters, expansion signals (future) |

---

### 6.13 Inbox Items Data Model

**Canonical schema for `inbox_items` table:**

```sql
CREATE TABLE inbox_items (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                     -- 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous'
  state TEXT NOT NULL DEFAULT 'proposed', -- 'proposed' | 'snoozed' | 'dismissed' | 'linked_to_issue'
  severity TEXT NOT NULL,                 -- 'critical' | 'high' | 'medium' | 'low' | 'info'

  -- Timestamps
  proposed_at TEXT NOT NULL,              -- when item first surfaced
  read_at TEXT,                           -- when user explicitly acknowledged item (null if unprocessed); NOT set on view
  resolved_at TEXT,                       -- when terminal state reached (null if pending)

  -- Snooze (populated when state = 'snoozed')
  snooze_until TEXT,                      -- ISO timestamp when snooze expires
  snoozed_by TEXT REFERENCES users(id),   -- user_id who snoozed
  snoozed_at TEXT,                        -- when snooze was set
  snooze_reason TEXT,                     -- optional note

  -- Dismissal (populated when state = 'dismissed')
  dismissed_by TEXT REFERENCES users(id), -- user_id who dismissed
  dismissed_at TEXT,                      -- when dismissed
  dismiss_reason TEXT,                    -- optional note
  suppression_key TEXT,                   -- hash to prevent re-proposal

  -- Underlying entity (exactly one of these is set)
  underlying_issue_id TEXT REFERENCES issues(id),
  underlying_signal_id TEXT REFERENCES signals(id),

  -- Resolution (populated when state = 'linked_to_issue')
  resolved_issue_id TEXT REFERENCES issues(id),  -- issue created/linked on tag/assign

  -- Scoping (nullable per type)
  client_id TEXT REFERENCES clients(id),
  brand_id TEXT REFERENCES brands(id),
  engagement_id TEXT REFERENCES engagements(id),

  -- Metadata
  title TEXT NOT NULL,
  evidence JSON NOT NULL,                 -- structured evidence per 6.4
  evidence_version TEXT NOT NULL DEFAULT 'v1',  -- schema version for evidence structure
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_inbox_items_state ON inbox_items(state);
CREATE INDEX idx_inbox_items_type ON inbox_items(type);
CREATE INDEX idx_inbox_items_client ON inbox_items(client_id);
CREATE INDEX idx_inbox_items_proposed ON inbox_items(proposed_at);
CREATE INDEX idx_inbox_items_suppression ON inbox_items(suppression_key);

-- Integrity constraints
ALTER TABLE inbox_items ADD CONSTRAINT chk_underlying_exclusive
  CHECK ((underlying_issue_id IS NOT NULL) != (underlying_signal_id IS NOT NULL));

-- Type ↔ underlying mapping constraints
ALTER TABLE inbox_items ADD CONSTRAINT chk_type_issue_mapping
  CHECK (type != 'issue' OR (underlying_issue_id IS NOT NULL AND underlying_signal_id IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_type_signal_mapping
  CHECK (type NOT IN ('flagged_signal', 'orphan', 'ambiguous') OR (underlying_signal_id IS NOT NULL AND underlying_issue_id IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_snooze_requires_until
  CHECK (state != 'snoozed' OR snooze_until IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_dismissed_requires_key
  CHECK (state != 'dismissed' OR suppression_key IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_terminal_requires_resolved
  CHECK (state NOT IN ('dismissed', 'linked_to_issue') OR resolved_at IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_linked_requires_issue
  CHECK (state != 'linked_to_issue' OR resolved_issue_id IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_dismissed_requires_audit
  CHECK (state != 'dismissed' OR (dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL));

-- Dedupe: at most one active inbox item per underlying entity
CREATE UNIQUE INDEX idx_inbox_items_unique_active_issue
  ON inbox_items (underlying_issue_id)
  WHERE underlying_issue_id IS NOT NULL AND state IN ('proposed', 'snoozed');

CREATE UNIQUE INDEX idx_inbox_items_unique_active_signal
  ON inbox_items (underlying_signal_id)
  WHERE underlying_signal_id IS NOT NULL AND state IN ('proposed', 'snoozed');
```

**Field constraints:**

| Field | Condition | Constraint |
|-------|-----------|------------|
| `snooze_until` | Required when `state = 'snoozed'` | ISO timestamp, must be future |
| `suppression_key` | Required when `state = 'dismissed'` | Hash per 1.8 formula |
| `resolved_at` | Required when `state IN ('dismissed', 'linked_to_issue')` | ISO timestamp |
| `underlying_issue_id` | Set when `type = 'issue'` | Exactly one of underlying_* set |
| `underlying_signal_id` | Set when `type IN ('flagged_signal', 'orphan', 'ambiguous')` | Exactly one of underlying_* set |

**Timestamps:**
- `created_at = proposed_at` on initial creation
- `updated_at` changes on any field modification
- `proposed_at` remains constant

**Note on snooze_until future enforcement:** DB CHECK constraint cannot validate "future" when using TEXT timestamps. Enforce at application layer: reject snooze requests where `snooze_until <= now()`.

**Scoping Consistency (App-Layer Constraint):**

For `type = 'issue'` inbox items:
- `client_id`, `brand_id`, `engagement_id` MUST equal the underlying issue's scoping fields
- Enforced at creation time; not a DB constraint (would require triggers)

For signal-based inbox items:
- Scoping reflects current signal scoping after any resolution (e.g., after "select" on ambiguous)

---

### 6.14 Issues Schema (Canonical)

```sql
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                     -- 'financial' | 'schedule_delivery' | 'communication' | 'risk'
  state TEXT NOT NULL DEFAULT 'detected', -- 10 states per 6.5
  severity TEXT NOT NULL,                 -- 'critical' | 'high' | 'medium' | 'low' | 'info'

  -- Scoping
  client_id TEXT NOT NULL REFERENCES clients(id),
  brand_id TEXT REFERENCES brands(id),
  engagement_id TEXT REFERENCES engagements(id),

  -- Core fields
  title TEXT NOT NULL,
  evidence JSON NOT NULL,
  evidence_version TEXT NOT NULL DEFAULT 'v1',

  -- Tagging (set on Tag or Assign)
  tagged_by_user_id TEXT REFERENCES users(id),
  tagged_at TEXT,                         -- first user confirmation

  -- Assignment (set on Assign)
  assigned_to TEXT REFERENCES users(id),
  assigned_at TEXT,
  assigned_by TEXT REFERENCES users(id),

  -- Snooze (when state = 'snoozed')
  snoozed_until TEXT,
  snoozed_by TEXT REFERENCES users(id),
  snoozed_at TEXT,
  snooze_reason TEXT,

  -- Suppression (parallel flag, not a state)
  suppressed BOOLEAN NOT NULL DEFAULT FALSE,
  suppressed_at TEXT,
  suppressed_by TEXT REFERENCES users(id),

  -- Escalation (parallel flag, not a state)
  escalated BOOLEAN NOT NULL DEFAULT FALSE,
  escalated_at TEXT,
  escalated_by TEXT REFERENCES users(id),

  -- Timestamps
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_issues_client ON issues(client_id);
CREATE INDEX idx_issues_state ON issues(state);
CREATE INDEX idx_issues_type ON issues(type);
CREATE INDEX idx_issues_severity ON issues(severity);
```

**tagged_* preservation rule:** If issue is already tagged (`tagged_by_user_id IS NOT NULL`) and then assigned, do NOT overwrite `tagged_by_user_id` or `tagged_at`. Preserve first user confirmation. Only set `assigned_*` fields.

**Severity Derivation (v1 heuristics):**

| Issue Type | Severity | Condition |
|------------|----------|-----------|
| financial | critical | Any invoice 45+ days overdue OR total overdue > AED 100k |
| financial | high | Any invoice 30-44 days overdue OR total overdue > AED 50k |
| financial | medium | Any invoice 15-29 days overdue |
| financial | low | Any invoice 1-14 days overdue |
| schedule_delivery | critical | 5+ tasks overdue by 7+ days |
| schedule_delivery | high | 3+ tasks overdue OR any task 5+ days overdue |
| schedule_delivery | medium | 1-2 tasks overdue by 1-4 days |
| communication | high | 3+ negative signals in 7 days OR escalation keyword |
| communication | medium | 2 negative signals in 7 days |
| communication | low | 1 negative signal |
| risk | varies | Manual assignment or detector-specific rules |

---

### 6.15 Signals Schema (Canonical)

```sql
CREATE TABLE signals (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,                   -- 'asana' | 'gmail' | 'gchat' | 'calendar' | 'meet' | 'minutes' | 'xero'
  source_id TEXT NOT NULL,                -- ID within source system

  -- Classification
  sentiment TEXT NOT NULL,                -- 'good' | 'neutral' | 'bad'
  signal_type TEXT,                       -- detector-specific type (e.g., 'task_overdue', 'escalation_keyword')
  rule_triggered TEXT,                    -- detector rule ID if flagged

  -- Scoping (derived or explicit)
  client_id TEXT REFERENCES clients(id),
  brand_id TEXT REFERENCES brands(id),
  engagement_id TEXT REFERENCES engagements(id),

  -- Content
  summary TEXT NOT NULL,                  -- human-readable summary
  evidence JSON NOT NULL,                 -- structured per evidence schema
  analysis_provider TEXT,                 -- 'gemini' for minutes; null for others

  -- Dismissal (if dismissed without becoming issue)
  dismissed BOOLEAN NOT NULL DEFAULT FALSE,
  dismissed_at TEXT,
  dismissed_by TEXT REFERENCES users(id),

  -- Timestamps
  observed_at TEXT NOT NULL,              -- when event occurred in source system
  ingested_at TEXT NOT NULL,              -- when signal was created in our system
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_signals_source ON signals(source);
CREATE INDEX idx_signals_client ON signals(client_id);
CREATE INDEX idx_signals_sentiment ON signals(sentiment);
CREATE INDEX idx_signals_observed ON signals(observed_at);
CREATE UNIQUE INDEX idx_signals_source_unique ON signals(source, source_id);
```

---

### 6.16 Evidence Meta-Schema (Canonical)

All evidence fields (issues, signals, inbox_items) follow this standardized envelope:

```json
{
  "version": "v1",
  "kind": "invoice|asana_task|gmail_thread|calendar_event|minutes_analysis|gchat_message|xero_contact",
  "url": "https://...",                    // nullable (null for minutes, xero)
  "display_text": "INV-1234 · AED 35,000", // always present
  "source_system": "xero",                 // source identifier
  "source_id": "inv_abc123",               // unique ID in source
  "payload": {
    // Kind-specific fields
  }
}
```

**Kind-specific payload examples:**

| Kind | Payload Fields |
|------|----------------|
| `invoice` | `number`, `amount`, `currency`, `due_date`, `days_overdue`, `status` |
| `asana_task` | `task_gid`, `name`, `assignee`, `due_date`, `days_overdue`, `project_name` |
| `gmail_thread` | `thread_id`, `subject`, `sender`, `snippet`, `received_at` |
| `calendar_event` | `event_id`, `title`, `start_time`, `cancelled`, `rescheduled` |
| `minutes_analysis` | `meeting_id`, `meeting_title`, `meeting_platform`, `analysis_provider`, `key_points`, `sentiment_summary`, `recording_url` (nullable), `transcript_url` (nullable) |
| `gchat_message` | `space_id`, `message_id`, `sender`, `snippet`, `keywords_detected` |

**UI Link Rendering Rules:**

| source_system | Render Link? | Notes |
|---------------|--------------|-------|
| `asana` | ✅ Yes, if `url` present | Deep link to task |
| `gmail` | ✅ Yes, if `url` present | Opens thread |
| `gchat` | ✅ Yes, if `url` present | Opens message |
| `calendar` | ✅ Yes, if `url` present | Opens event |
| `xero` | ❌ **Never** | Even if `url` is non-null, do not render `↗` or clickable link. Xero has no stable deep links. Display as plain text. User copies invoice number. |
| `minutes` | ⚠️ Conditional | `evidence.url` is always null; render "View Recording ↗" if `payload.recording_url` exists; render "View Transcript ↗" if `payload.transcript_url` exists |
| `meet` | ❌ No | Recordings may not be accessible |

---

### 6.17 Tasks Source Definition (for Engagement Health)

`tasks_in_source` (more accurately: `open_tasks_in_source`) for engagement health gating is defined as:

```python
def open_tasks_in_source(asana_project_id):
    """Count open (incomplete) top-level tasks in source project."""
    return count(
        tasks in Asana project
        WHERE NOT completed          # exclude completed tasks
        AND NOT archived             # exclude archived tasks
        AND parent IS NULL           # exclude subtasks (count only top-level)
    )
```

**Note:** This counts **open tasks only**. For engagements that are mostly complete, `open_tasks_in_source` may be low or 0, causing gating failure. This is intentional: health scoring is meaningful only when there's active work.

**Completed task handling:** Completed tasks are not counted in `open_tasks_in_source` but ARE used in:
- `tasks_completed` count for progress display
- `avg_days_late` for completion lag calculation

**days_late calculation:**

```python
def days_late(due_date: date, completed_at: datetime, org_tz: str) -> int:
    """Tasks without due_date are excluded from lag calculation."""
    if due_date is None:
        return None  # Exclude from average
    due_local = due_date
    completed_local = completed_at.astimezone(ZoneInfo(org_tz)).date()
    return max(0, (completed_local - due_local).days)
```

**Sync strategy:**
- Tasks are synced from Asana on a regular schedule (default: every 15 minutes)
- `open_tasks_in_source` is computed at sync time and cached per engagement
- Stale data (>1 hour since last sync) triggers a warning in UI

---

### 6.18 Tier Values (Canonical)

| Tier | API Value | Definition |
|------|-----------|------------|
| Platinum | `platinum` | Top-tier client |
| Gold | `gold` | High-value client |
| Silver | `silver` | Standard client |
| Bronze | `bronze` | Entry-level client |
| None | `none` | Unassigned (default) |

Stored as `clients.tier` (nullable TEXT, defaults to `none`).

---

## 7. Minimum API Endpoints

### 7.1 Client Index

```
GET /api/clients
  ?status=active|recently_active|cold|all
  &tier=platinum|gold|silver|bronze|none
  &has_issues=true|false
  &has_overdue_ar=true|false
  &sort=ar_overdue|last_invoice|name
  &order=asc|desc
  &page=1
  &limit=20

Response:
{
  "active": [
    {
      "id": "uuid",
      "name": "Acme Corp",
      "tier": "gold",
      "status": "active",
      "health_score": 78,
      "health_label": "provisional",
      "issued_ytd": 125000,
      "issued_year": 500000,
      "paid_ytd": 95000,
      "paid_year": 420000,
      "ar_outstanding": 130000,
      "ar_overdue": 45000,
      "ar_overdue_pct": 35,
      "open_issues_high_critical": 2,
      "last_invoice_date": "2026-01-15",
      "first_invoice_date": "2022-03-01"
    }
  ],
  "recently_active": [...],
  "cold": [...],
  "counts": {
    "active": 24,
    "recently_active": 18,
    "cold": 45
  }
}
```

---

### 7.2 Active Client Detail

```
GET /api/clients/:id
  ?include=overview,engagements,financials,signals,team

Response:
{
  "id": "uuid",
  "name": "Client Name",
  "tier": "gold",
  "status": "active",
  "health_score": 78,
  "health_label": "provisional",
  "brands": [...],
  "overview": {
    "top_issues": [...],
    "recent_positive_signals": [...]
  }
}
```

**Include Policy (Canonical):**

- Base fields always returned: `id`, `name`, `status`, `tier`
- `?include=overview,engagements,...` returns only requested sections
- `top_issues` and `recent_positive_signals` are part of `overview` section (not root level)
- No `?include=` param: returns union shape with null for excluded sections (based on status)
- Forbidden section for status: returns 403

---

### 7.3 Client Snapshot (Cold clients from Inbox)

```
GET /api/clients/:id/snapshot
  ?inbox_item_id=<uuid>     // Active inbox item
  OR
  ?issue_id=<uuid>          // Tracked issue (even if inbox item archived)

Response:
{
  "id": "uuid",
  "name": "Client Name",
  "status": "cold",
  "issued_lifetime": 350000,
  "paid_lifetime": 350000,
  "last_invoice_date": "2024-02-10",
  "first_invoice_date": "2021-06-01",
  "context": {
    "source": "inbox_item" | "issue",
    "inbox_item": {           // Present if source = inbox_item
      "id": "uuid",
      "type": "issue",
      "title": "Invoice 45 days overdue",
      "evidence": {...},
      "actions": ["tag", "dismiss"]
    },
    "issue": {                // Present if source = issue OR inbox linked to issue
      "id": "uuid",
      "type": "financial",
      "title": "Invoice 45 days overdue",
      "state": "surfaced",
      "evidence": {...}
    }
  },
  "related_signals": [
    // Max 5, linked to issue or client, last 90 days
  ]
}
```

**Parameter precedence:** If both provided, `inbox_item_id` takes precedence. At least one required.

**Action values:** API values (`tag`, `dismiss`, etc.); UI renders as "Tag & Watch", "Dismiss", etc.

---

### 7.4 Engagements

```
GET /api/clients/:id/engagements
  ?state=planned|active|blocked|paused|delivering|delivered|completed|all_active|all
  &brand_id=<uuid>

Response:
{
  "brands": [
    {
      "id": "uuid",
      "name": "Brand A",
      "engagements": [
        {
          "id": "uuid",
          "name": "Monthly Retainer 2026",
          "type": "retainer",
          "state": "active",
          "tasks_open": 12,
          "tasks_overdue": 3,
          "tasks_completed": 45,
          "health_score": 58,
          "asana_url": "https://app.asana.com/..."
        }
      ]
    }
  ]
}
```

**State filters:**
- `all_active`: includes planned, active, blocked, paused, delivering, delivered
- `all`: includes all states including completed

---

### 7.5 Financials

```
GET /api/clients/:id/financials

Response:
{
  "finance_calc_version": "v1",   // Calculation version for audit
  "prior_year": 2025,             // Which year "prior_year" refers to
  "summary": {
    "issued_prior_year": 500000,  // Renamed from issued_year
    "issued_ytd": 125000,
    "issued_lifetime": 1250000,
    "paid_prior_year": 420000,    // Renamed from paid_year
    "paid_ytd": 95000,
    "paid_lifetime": 1120000
  },
  "ar_aging": {
    "total_outstanding": 130000,
    "buckets": [
      { "bucket": "current", "amount": 85000, "pct": 65 },
      { "bucket": "1_30", "amount": 25000, "pct": 19 },
      { "bucket": "31_60", "amount": 15000, "pct": 12 },
      { "bucket": "61_90", "amount": 5000, "pct": 4 },
      { "bucket": "90_plus", "amount": 0, "pct": 0 }
    ]
  }
}

GET /api/clients/:id/invoices
  ?status=draft|sent|overdue|paid|voided|all
  &sort=issue_date|amount|status
  &order=asc|desc
  &page=1
  &limit=10

Response:
{
  "invoices": [
    {
      "id": "uuid",
      "number": "INV-1456",
      "issue_date": "2026-01-15",
      "due_date": "2026-02-14",
      "amount": 45000,
      "status": "sent",
      "days_overdue": null,             // null if not overdue; null if due_date missing
      "aging_bucket": "current",      // Server-computed: current|1_30|31_60|61_90|90_plus
      "status_inconsistent": false    // true if sent but due_date <= today
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 10
}
```

**Invoice Aging Computation (Deterministic):**

| status | Condition | days_overdue | aging_bucket | status_inconsistent |
|--------|-----------|--------------|--------------|---------------------|
| `overdue` | due_date not null | `max(0, today - due_date)` | Computed from days_overdue | false |
| `overdue` | due_date null | null | `90_plus` (fallback) | false |
| `sent` | due_date > today | null | `current` | false |
| `sent` | due_date <= today | `max(0, today - due_date)` | Computed from days_overdue | **true** |
| `sent` | due_date null | null | null | false |
| `paid`/`voided`/`draft` | any | null | null | false |

**Key:** `status` field is never mutated; it reflects source system (Xero) value. `status_inconsistent=true` signals a data quality issue.

---

### 7.6 Issues

```
GET /api/clients/:id/issues
  ?state=detected|surfaced|snoozed|acknowledged|addressing|awaiting_resolution|resolved|regression_watch|closed|regressed|all_open|all_closed|all
  &severity=critical|high|medium|low|info
  &type=financial|schedule_delivery|communication|risk
  &include_suppressed=false     // Default: false (exclude suppressed)
  &include_snoozed=false        // Default: false (exclude snoozed from all_open)
  &sort=severity|created_at|updated_at   // Default: severity desc, created_at desc, id asc
  &order=desc
  &limit=10

Response:
{
  "issues": [
    {
      "id": "uuid",
      "type": "financial",
      "severity": "critical",
      "state": "surfaced",
      "title": "Invoice 45 days overdue",
      "evidence": {...},
      "created_at": "2026-01-10T10:00:00Z",
      "available_actions": ["acknowledge", "snooze", "resolve"]  // State-dependent
    }
  ],
  "counts": {...}
}
```

**available_actions by state:**

| Issue State | Available Actions |
|-------------|-------------------|
| `surfaced` | `["acknowledge", "snooze", "resolve"]` |
| `acknowledged` | `["assign", "snooze", "resolve"]` |
| `addressing` | `["snooze", "resolve", "escalate"]` |
| `awaiting_resolution` | `["resolve", "escalate"]` |
| `snoozed` | `["unsnooze"]` |
| `resolved` | `[]` (read-only during regression watch) |
| `regression_watch` | `[]` |
| `closed` | `[]` |
| `regressed` | `["acknowledge", "snooze", "resolve"]` (same as surfaced) |

```
```

**State filters:**
- `all_open`: surfaced, snoozed (if include_snoozed), acknowledged, addressing, awaiting_resolution, regressed
  - **Note:** `detected` is excluded from `all_open` by default (not yet visible to user)
  - Use `?state=detected` explicitly to query pre-surfaced issues (internal/admin use)
- `all_closed`: resolved, regression_watch, closed
- `all`: all states

**Default behavior:**
- `suppressed = true` issues are excluded unless `include_suppressed=true`
- `state = snoozed` issues are excluded from `all_open` unless `include_snoozed=true`
- To fetch only snoozed: `?state=snoozed`

```
POST /api/issues/:id/transition
{
  "action": "acknowledge" | "snooze" | "resolve" | "escalate" | "assign" | "mark_awaiting" | "unsnooze",
  "snooze_days": 7,           // Required if action = snooze
  "assigned_to": "uuid",      // Required if action = assign
  "note": "..."
}

Response:
{
  "success": true,
  "previous_state": "surfaced",
  "new_state": "acknowledged",
  "issue_id": "uuid"
}
```

**Action Definitions:**

| Action | Effect | Required Fields |
|--------|--------|-----------------|
| `acknowledge` | → `acknowledged` | — |
| `snooze` | → `snoozed` | `snooze_days` |
| `unsnooze` | `snoozed` → `surfaced` | — |
| `assign` | → `addressing`, sets assigned_* | `assigned_to` |
| `mark_awaiting` | → `awaiting_resolution` | — |
| `resolve` | → `resolved` (enters regression watch) | — |
| `escalate` | Increases severity AND/OR sets escalated flag | — |

**Escalate Action:**

Escalation means:
1. Set `issues.escalated = true`
2. Set `issues.escalated_at = now()`
3. Set `issues.escalated_by = current_user`
4. Optionally increase severity by one level (if not already critical)
5. State remains unchanged (escalation is orthogonal to state)

**Transition: resolved → regression_watch:**

This transition happens immediately upon resolve:
- `resolve` action sets `state = 'resolved'`
- System immediately transitions to `regression_watch` with `transition_reason = 'system_timer'` and `trigger_rule = 'enter_regression_watch'`
- 90-day timer starts

**System-Only Transitions:**

| Transition | Trigger |
|------------|---------|
| `detected` → `surfaced` | Aggregation threshold reached |
| `snoozed` → `surfaced` | Timer expired |
| `resolved` → `regression_watch` | Immediate on resolve |
| `regression_watch` → `closed` | 90 days with no recurrence |
| `regression_watch` → `regressed` | Recurrence signal detected |

**Regression Resurfacing (Deterministic):**

When an issue transitions `regression_watch → regressed`:

1. System transitions issue to `state = 'regressed'`
2. System creates a new inbox item with:
   - `type = 'issue'`
   - `state = 'proposed'`
   - `underlying_issue_id = issue.id`
   - Same scoping (client_id, brand_id, engagement_id)
   - Fresh `proposed_at = now()`

This is allowed because:
- Prior inbox item for this issue is terminal (`linked_to_issue` from original Tag/Assign)
- Unique index applies only to active states (`proposed`, `snoozed`)
- User needs to re-evaluate the regressed issue

POST /api/issues/:id/unsuppress
{}

Response:
{
  "success": true,
  "suppressed": false
}

Idempotent: calling unsuppress on already-unsuppressed issue returns success.

**Suppression via Issue Endpoint:**

Suppression is only available via inbox dismiss action. There is no direct `POST /api/issues/:id/suppress` endpoint. This ensures all suppressions flow through the inbox proposal system.
```

---

### 7.7 Signals

```
GET /api/clients/:id/signals
  ?sentiment=good|neutral|bad|all
  &source=asana|gmail|gchat|calendar|meet|minutes|xero
  &days=30
  &page=1
  &limit=20

Response:
{
  "summary": {
    "good": 12,
    "neutral": 8,
    "bad": 5,
    "by_source": {
      "asana": { "good": 8, "neutral": 2, "bad": 3 },
      "gmail": { "good": 2, "neutral": 3, "bad": 1 },
      "gchat": { "good": 1, "neutral": 2, "bad": 0 },
      "calendar": { "good": 0, "neutral": 1, "bad": 0 },
      "meet": { "good": 1, "neutral": 0, "bad": 1 },
      "minutes": { "good": 0, "neutral": 0, "bad": 0 },
      "xero": { "good": 1, "neutral": 0, "bad": 1 }
    }
  },
  "signals": [
    {
      "id": "uuid",
      "source": "minutes",
      "source_id": "meet_abc123",
      "sentiment": "bad",
      "summary": "Client expressed frustration about timeline",
      "analysis_provider": "gemini",    // Present for minutes signals
      "created_at": "2026-01-14T10:00:00Z",
      "evidence": {
        "url": null,                    // No direct link for minutes
        "display_text": "Q1 Review Meeting · 2026-01-14",
        "source_system": "minutes",     // Always matches signals.source
        "source_id": "meet_abc123",
        "payload": {
          "meeting_platform": "meet",   // Platform-specific in payload
          "meet_event_id": "abc123"
        }
      }
    }
  ],
  "total": 25,
  "page": 1
}
```

**Signal Evidence Structure (canonical per source):**

| Field | Type | Description |
|-------|------|-------------|
| `url` | string \| null | Direct link to source (null for minutes, xero) |
| `display_text` | string | Always present; human-readable label |
| `source_system` | string | Source identifier (asana, gmail, etc.) |
| `source_id` | string | Unique ID within source system |

**Minutes-specific fields:**
- `analysis_provider`: "gemini" (or future providers)
- `meeting_id`: Reference to meet event
- `transcript_excerpt`: Relevant snippet (if available)

```
```

---

### 7.8 Team

```
GET /api/clients/:id/team
  ?days=30

Response:
{
  "involvement": [
    {
      "user_id": "uuid",
      "name": "Sarah Johnson",
      "role": "Account Lead",
      "hours_estimated": 48,
      "tasks_count": 28,
      "tasks_overdue": 2
    },
    {
      "user_id": "uuid",
      "name": "Mike Chen",
      "role": "Designer",
      "hours_estimated": 32,
      "tasks_count": 15,
      "tasks_overdue": 0
    }
  ],
  "workload": [
    {
      "user_id": "uuid",
      "name": "Sarah",
      "capacity_pct": 80
    },
    {
      "user_id": "uuid",
      "name": "Mike",
      "capacity_pct": 56
    }
  ],
  "tardiness": [
    {
      "user_id": "uuid",
      "name": "Sarah Johnson",
      "tasks_overdue_90d": 4,
      "avg_days_late": 3.2
    },
    {
      "user_id": "uuid",
      "name": "Alex Rivera",
      "tasks_overdue_90d": 2,
      "avg_days_late": 1.5
    }
  ],
  "recent_activity": [
    {
      "user_id": "uuid",
      "user_name": "Sarah",
      "action": "completed",
      "task_name": "Q1 Brand Guidelines",
      "timestamp": "2026-01-14T10:00:00Z"
    },
    {
      "user_id": "uuid",
      "user_name": "Mike",
      "action": "started",
      "task_name": "Homepage Redesign Mockups",
      "timestamp": "2026-01-13T14:30:00Z"
    }
  ]
}
```

---

### 7.9 Recently Active Drilldown

```
GET /api/clients/:id
  (same endpoint, returns limited data based on status)

Response (when status = recently_active):
{
  "id": "uuid",
  "name": "Client Name",
  "status": "recently_active",
  "issued_lifetime": 850000,
  "paid_lifetime": 850000,
  "last_invoice_date": "2025-09-15",
  "first_invoice_date": "2022-03-01",
  "brands": ["Brand A", "Brand B"],
  "last_invoices": [...],  // max 5

  // Excluded for recently_active (null or omitted):
  "health_score": null,
  "top_issues": null,
  "recent_positive_signals": null,
  "overview": null,
  "engagements": null,
  "signals": null,
  "team": null
}
```

**Response Shape Policy:**

`GET /api/clients/:id` always returns the union shape. Excluded sections are `null` (not omitted) for type safety:

| Status | Included | Null/Excluded |
|--------|----------|---------------|
| `active` | All sections | None |
| `recently_active` | id, name, status, financials (lifetime), brands, last_invoices | health, issues, signals, team, engagements |
| `cold` | id, name, status, financials (lifetime) | All operational sections |

**Explicit Include Behavior:**

- Default request (no `?include=`): Returns union shape with `null` for excluded sections
- `?include=health,signals`: Returns only requested sections (if allowed) **plus** always-present base fields
- `?include=<forbidden_section>`: Returns `403 Forbidden` with error body (no union payload)
- `?include=<empty>` or `?include=<unknown>`: Returns `400 Bad Request`

**Always-present fields** (regardless of `?include=`):
- `id`, `name`, `status`, `tier` (core identity)

**top_issues and recent_positive_signals:** These appear in overview section. If `?include=` does not request `overview`, they are excluded (include is strict for sections).

```json
// 403 response for forbidden include
{
  "error": "forbidden_section",
  "message": "Cannot include 'signals' for recently_active client",
  "allowed_includes": ["id", "name", "status", "financials", "brands", "last_invoices"]
}
```

---

### 7.10 Control Room Inbox

```
GET /api/inbox
  ?type=issue|flagged_signal|orphan|ambiguous|all
  &severity=critical|high|medium|low|info
  &state=proposed|snoozed         // Note: 'all' removed; terminal states only via /recent
  &client_id=<uuid>
  &unread_only=true|false
  &sort=severity|age|client
  &order=desc                     // Default: desc
  &page=1
  &limit=20

GET /api/inbox/recent
  ?days=7                         // Fetch recently actioned items (terminal states)
  &state=linked_to_issue|dismissed  // Optional: filter by terminal state
  &type=issue|flagged_signal|orphan|ambiguous
  &severity=critical|high|medium|low|info
  &client_id=<uuid>
  &sort=resolved_at               // Default: resolved_at desc
  &order=desc
  &page=1
  &limit=20

Response (for /api/inbox/recent):
{
  "items": [
    {
      "id": "uuid",
      "type": "issue",
      "issue_category": "financial",    // Renamed from issue_type to avoid confusion with inbox item type
      "severity": "critical",
      "state": "linked_to_issue",       // terminal state
      "proposed_at": "2026-01-10T10:00:00Z",
      "resolved_at": "2026-01-13T14:30:00Z",
      "title": "Invoice 45 days overdue",
      "client": {...},
      "resolved_issue_id": "uuid",      // for linked_to_issue
      "dismissed_by": null,             // for dismissed
      "dismiss_reason": null,           // for dismissed
      "actions": []                     // read-only, no actions
    }
  ],
  "total": 8,
  "page": 1
}

Response (for /api/inbox):
{
  "counts": {
    "needs_attention": 12,          // state = 'proposed'
    "snoozed": 3,                   // state = 'snoozed'
    "snoozed_returning_soon": 1,    // snooze_until <= now() + 1 day
    "recently_actioned": 8,         // terminal actions (linked_to_issue, dismissed) last 7 days
    "unread": 5,                    // read_at is null
    "by_severity": {...},
    "by_type": {...}
  },
  "items": [
    {
      "id": "uuid",
      "type": "issue",              // issue|flagged_signal|orphan|ambiguous
      "issue_category": "financial", // present only when type = "issue"; values: financial|schedule_delivery|communication|risk
      "severity": "critical",
      "state": "proposed",          // proposed|snoozed only; terminal states not returned
      "read_at": null,              // null if unprocessed
      "proposed_at": "2026-01-13T10:00:00Z",
      "title": "Invoice 45 days overdue",
      "client": {
        "id": "uuid",
        "name": "Acme Corp",
        "status": "active"
      },
      "brand": {
        "id": "uuid",               // nullable
        "name": "Brand A"
      },
      "engagement": {
        "id": "uuid",               // nullable
        "name": "Monthly Retainer 2026"
      },
      "evidence": {...},
      "actions": ["tag", "assign", "snooze", "dismiss"]
    }
  ]
}
```

**Actions by type:**
- `issue`: `["tag", "assign", "snooze", "dismiss"]`
- `flagged_signal`: `["tag", "assign", "snooze", "dismiss"]`
- `orphan`: `["link", "create", "dismiss"]`
- `ambiguous`: `["select", "dismiss"]` (after select: `["tag", "assign", "snooze", "dismiss"]`)

**issue_category field:** Present only when `type = "issue"`. Derived via join to `issues.type` (not stored in `inbox_items`). Values: `financial`, `schedule_delivery`, `communication`, `risk`.

**Note on naming:** `type` refers to inbox item type; `issue_category` refers to the underlying issue's category. This avoids ambiguity.

**Sorting Defaults:**

| Sort Key | Order | Description |
|----------|-------|-------------|
| `severity` | Descending | critical > high > medium > low > info |
| `age` | Ascending | Oldest first (`proposed_at` ASC) |
| `client` | Ascending | Alphabetical by client name |

Default sort: `severity` descending, then `age` ascending, then `id` ascending (oldest critical items first; deterministic tie-breaker).

```sql
ORDER BY severity_weight DESC, proposed_at ASC, id ASC
```

```
POST /api/inbox/:id/action
{
  "action": "tag" | "assign" | "snooze" | "dismiss" | "link" | "create" | "select",
  "assign_to": "uuid",
  "snooze_days": 7,
  "link_engagement_id": "uuid",
  "select_candidate_id": "uuid",
  "note": "optional context"
}

Response (varies by action):
{
  "success": true,
  "issue_id": "uuid",                    // Created or linked issue (if applicable)
  "inbox_item_state": "linked_to_issue", // New state
  "resolved_at": "2026-01-15T14:30:00Z"
}
```

**Response Fields per Action:**

| Action | inbox_item_state | issue_id | Additional Fields |
|--------|------------------|----------|-------------------|
| `tag` | `linked_to_issue` | Created/linked issue UUID | — |
| `assign` | `linked_to_issue` | Created/linked issue UUID | — |
| `snooze` | `snoozed` | null | `snooze_until` |
| `dismiss` | `dismissed` | null | `suppression_key` |
| `link` | `proposed` (now actionable) | null | `actions`, `engagement_id`, `client_id`, `brand_id` |
| `create` | `proposed` (unchanged) | null | `draft_engagement`, `next_step_url` |
| `select` | `proposed` (now actionable) | null | `actions`, `engagement_id`, `client_id`, `brand_id` |

**Post-Link/Select Behavior:**

After successful `link` or `select` action:
- Inbox item remains same `id` and `state='proposed'`
- Item `type` remains unchanged (orphan stays orphan, ambiguous stays ambiguous)
- Item becomes fully actionable with updated actions: `["tag", "assign", "snooze", "dismiss"]`
- Response includes updated scoping: `client_id`, `brand_id`, `engagement_id`
- Server response MUST include `actions` array with the updated available actions

**Action Payload Validation:**

| Action | Required Fields | Optional | Reject if Present |
|--------|-----------------|----------|-------------------|
| `tag` | — | `note` | `assign_to`, `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `assign` | `assign_to` | `note` | `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `snooze` | `snooze_days` | `note` | `assign_to`, `link_engagement_id`, `select_candidate_id` |
| `dismiss` | — | `note` | `assign_to`, `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `link` | `link_engagement_id` | `note` | `assign_to`, `snooze_days`, `select_candidate_id` |
| `create` | — | `note` | all optional fields |

**Create Action (Two-Step Flow):**

The `create` action for orphan items initiates engagement creation but does not complete it:

1. `POST /api/inbox/:id/action` with `action='create'`
2. Response includes:
   - `draft_engagement`: Pre-populated fields inferred from signal (client, brand, suggested name)
   - `next_step_url`: URL to engagement creation form with draft pre-filled
3. User completes form and submits
4. `POST /api/engagements` creates the engagement
5. System auto-links the orphan signal to the new engagement
6. Inbox item becomes actionable (Tag/Assign available)

Inbox item remains `proposed` throughout. The `draft_engagement` is a convenience, not a DB entity.

| `select` | `select_candidate_id` | `note` | `assign_to`, `snooze_days`, `link_engagement_id` |

Return `400 Bad Request` if required fields missing or unexpected fields present.

```

GET /api/inbox/counts
  ?group_by=client|type|severity

Response:
{
  "needs_attention": 12,
  "snoozed": 3,
  "snoozed_returning_soon": 1,
  "recently_actioned": 8,
  "by_severity": {...},
  "by_type": { "issue": 7, "flagged_signal": 3, "orphan": 1, "ambiguous": 1 },
  "by_client": [...]
}

POST /api/inbox/bulk_action
{
  "item_ids": ["uuid1", "uuid2", "uuid3"],
  "action": "snooze" | "dismiss",
  "snooze_days": 7,
  "note": "Bulk action reason"
}

Response:
{
  "success": true,
  "processed": 3,
  "failed": 0,
  "errors": []
}
```

**Note:** Bulk actions support only `snooze` and `dismiss`. Bulk `tag` and `assign` require individual issue context.

```
POST /api/inbox/:id/mark_read
{}

Response:
{
  "success": true,
  "read_at": "2026-01-15T14:30:00Z"
}

POST /api/inbox/mark_all_read
{}

Response:
{
  "success": true,
  "marked_count": 12
}

GET /api/clients/search
  ?q=acme
  &status=active|recently_active|cold|all
  &limit=10

Response:
{
  "results": [...],
  "total": 1
}

GET /api/inbox/search
  ?q=invoice
  &type=issue|flagged_signal|orphan|all
  &limit=20

Response:
{
  "results": [...],
  "total": 3
}
```

---

### 7.11 Engagements (Lifecycle)

```
GET /api/engagements/:id

Response:
{
  "id": "uuid",
  "name": "Monthly Retainer 2026",
  "type": "retainer",
  "state": "active",
  "state_changed_at": "2026-01-01T00:00:00Z",
  "client_id": "uuid",
  "brand_id": "uuid",
  "tasks_summary": {
    "open": 12,
    "overdue": 3,
    "completed": 45
  },
  "health_score": 58,            // or null if gating fails
  "health_gating_reason": null,  // or "task_linking_incomplete" or "no_tasks"
  "asana_project_id": "1234567890",
  "asana_url": "https://app.asana.com/..."
}

POST /api/engagements/:id/transition
{
  "state": "planned" | "active" | "blocked" | "paused" | "delivering" | "delivered" | "completed",
  "reason": "optional note"
}

Response:
{
  "success": true,
  "previous_state": "active",
  "new_state": "paused",
  "transitioned_at": "2026-01-15T14:30:00Z"
}
```

---

## Approval Checklist

### Control Room Inbox
- [ ] Global surface for proposed items (issues, flagged signals, orphans, ambiguous)
- [ ] Inbox item lifecycle: proposed → snoozed/dismissed/linked_to_issue (no `tagged` state)
- [ ] "Tag & Watch" (not "Tag & Monitor") creates/links issue, starts watch loop behavior
- [ ] Assign action sets assignee, transitions issue to addressing
- [ ] Snooze hides for N days, resurfaces automatically (hourly job for both issues and inbox items)
- [ ] Dismiss suppresses underlying entity + stores suppression_key to prevent re-proposal
- [ ] Shows items across all clients (not filtered by client status)
- [ ] Minimum evidence defined per item type (Issue/Flagged Signal/Orphan/Ambiguous)
- [ ] Inbox overrides segment clickability (Cold clients get Snapshot view via 7.3)
- [ ] Read is independent of state (read_at field, set only via mark_read)
- [ ] Counts: needs_attention, snoozed, snoozed_returning_soon, recently_actioned (7 days)
- [ ] `resolved_at` set on all terminal transitions
- [ ] Select Primary flow defined for Ambiguous items

### Client Index
- [ ] Three sections: Active, Recently Active, Cold
- [ ] Active cards: Issued + Paid (current year, YTD), AR (Outstanding + Overdue), Issues count
- [ ] Recently Active cards: Last/Prev 12m Issued + Paid, Historical totals, Last invoice date
- [ ] Cold cards: Historical totals only, not clickable
- [ ] No standalone "Revenue" label anywhere
- [ ] Tier values defined: platinum, gold, silver, bronze, none

### Active Client Detail
- [ ] 5 tabs: Overview, Engagements, Financials, Signals, Team
- [ ] Overview: Key metrics + top issues with evidence + recent positive signals
- [ ] Engagements: Grouped by brand, active first, completed (12m) second; State not Status
- [ ] Financials: Issued/Paid summary + AR aging + invoice table; Invoice status values defined
- [ ] Signals: 30d view, filterable by sentiment + source (7 sources), includes meeting minutes and xero
- [ ] Team: Involvement, workload, tardiness, recent activity

### Recently Active Drilldown
- [ ] Historical totals only
- [ ] Last 5 invoices
- [ ] No engagements/signals/team

### Cold Clients
- [ ] Not clickable from index
- [ ] Card shows historical totals only
- [ ] Snapshot view available from Inbox (7.3)

### Data Contracts
- [ ] Client status computed from MAX(issue_date); no invoices = cold
- [ ] Finance: Issued = issue_date based, Paid = payment_date based, AR = status based
- [ ] AR_outstanding = AR_total in formulas; AR aging buckets defined
- [ ] Partial payments: v1 treats as fully paid/unpaid
- [ ] Task linking: via engagement_id only, no name matching (6.3)
- [ ] Engagement resolver: may use name matching for low-confidence proposals (6.8)
- [ ] Evidence: URL or deterministic fallback; detector rules defined
- [ ] Issue lifecycle: 10 states (includes `snoozed`), uses `awaiting_resolution` (not "monitoring")
- [ ] Suppressed issues excluded from health/counts
- [ ] Signals: good/neutral/bad, 7 sources (asana, gmail, gchat, calendar, meet, minutes, xero)
- [ ] Timestamp format: ISO 8601

### Health Score
- [ ] Client health formula defined (AR penalty + Issue penalty)
- [ ] Engagement health formula defined (Overdue penalty + Completion lag)
- [ ] "Provisional" label until task linking complete
- [ ] Thresholds: 0-39 Poor, 40-69 Fair, 70-100 Good
- [ ] Health-counted states: surfaced, acknowledged, addressing, awaiting_resolution, regressed (snoozed excluded)
- [ ] Rounding: floor() to integer for all penalties
- [ ] Safe clamps: ratios clamped to [0,1], divide-by-zero handled
- [ ] Engagement health gating: show N/A if <90% tasks linked

### Engagement Lifecycle
- [ ] State machine: planned → active → delivering → delivered → completed (+ blocked, paused)
- [ ] Engagement types defined: project, retainer
- [ ] Heuristic triggers from signals/tasks/calendar/email/minutes
- [ ] Manual override actions available
- [ ] Audit trail required for all transitions (`engagement_transitions` table)
- [ ] Timer-based transitions logged with `actor='system'`, `transition_reason='system_timer'`
- [ ] Transition reason enum aligned: user, system_timer, system_signal, system_threshold, system_aggregation

### Engagement Creation & Linking
- [ ] Resolver priority: Asana > Invoice > Meeting > Email
- [ ] Confidence thresholds: High (≥0.95) auto-link, Medium (0.70-0.94) propose, Low (0.40-0.69) suggest only
- [ ] Hard rule: no implicit cross-client linking
- [ ] Hard rule: name matching only for Engagement Resolver, never for Task Linking
- [ ] Orphan/Ambiguous → Inbox with candidate list
- [ ] New candidates proposed for confirmation

### Xero Linking
- [ ] No deep links (not available)
- [ ] Display: "INV-1234 (open in Xero)" — plain text, no arrow
- [ ] Consistent everywhere (no mixed behavior)

### Recently Active Exclusions
- [ ] Confirmed intentional: no issues/signals/health in drilldown
- [ ] Out-of-norm items appear in Control Room Inbox instead

### Issue Lifecycle Audit
- [ ] `issue_transitions` table defined with required fields
- [ ] Snooze timer execution: hourly job, not query-time computed
- [ ] All issue state transitions logged with actor ('system' or user_id)
- [ ] Transition reasons: 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation'

### Inbox Items Schema
- [ ] `inbox_items` canonical schema defined (6.13)
- [ ] All required fields: id, type, state, severity, proposed_at, resolved_at, snooze_until, suppression_key
- [ ] Exactly one of underlying_issue_id / underlying_signal_id set
- [ ] Field constraints documented (snooze_until required when snoozed, etc.)
- [ ] evidence field is JSON (not TEXT)

### API
- [ ] All endpoints defined (including Inbox, Engagement lifecycle, Client Snapshot)
- [ ] Pagination on lists
- [ ] Filtering on index/signals/issues/inbox
- [ ] Inbox type param: `issue|flagged_signal|orphan|ambiguous|all`
- [ ] Inbox state param: `proposed|snoozed|all` (archived states not fetchable)
- [ ] Inbox state value in responses: `linked_to_issue` (not `linked`)
- [ ] Issues include `include_suppressed` and `include_snoozed` params
- [ ] Issues state param includes all 10 states plus `all_open|all_closed|all`
- [ ] Issues severity param includes `info`
- [ ] Signals source param includes `xero`
- [ ] Engagements state param includes all 7 states plus `all_active|all`
- [ ] Engagement transition allows all states including `planned` and `active`
- [ ] Search endpoints: `/api/clients/search`, `/api/inbox/search`
- [ ] Bulk actions: `/api/inbox/bulk_action`
- [ ] Inbox counts: `/api/inbox/counts` with `snoozed_returning_soon`
- [ ] Mark as read: `/api/inbox/:id/mark_read`
- [ ] Client snapshot: `/api/clients/:id/snapshot` accepts `inbox_item_id` OR `issue_id`
- [ ] Full response schemas provided for client index, team endpoint

---

## Validation Checklist (Engineer Reference)

1. No endpoint uses `surfaced` for inbox_items.state (only for issues.state)
2. `type=flagged_signal` appears consistently in API query params, response `type` field, and UI filter
3. Issue state `monitoring` does not appear anywhere — replaced by `awaiting_resolution`
4. "Watch loop" is always described as behavior, never as a state
5. `issues.dismissed` state does not exist — use `issues.suppressed` flag instead
6. Inbox action `dismiss` never creates a new issue state; sets suppression_key
7. "Tag & Watch" used in UI, never "Tag & Monitor"
8. Health formula uses `min(1.0, ratio)` clamp and handles divide-by-zero
9. Engagement health checks `tasks_total == 0` BEFORE `linked_pct` check
10. Engagement health returns `null` (not 0) when gating fails
11. Task linking section explicitly forbids name matching (6.3)
12. Engagement resolver section explicitly allows name matching for low-confidence (6.8)
13. Ambiguous type defined as "Engagement Resolver" not "Task linker" (1.3)
14. `AR_total = AR_outstanding` in all health formulas
15. Cold client snapshot endpoint (7.3) accepts `inbox_item_id` OR `issue_id`
16. Related signals selection rule: linked to issue OR same client within 90d, max 5
17. Inbox counts use `recently_actioned` (not `recently_tagged`) with 7-day window
18. `read_at` is independent of `state` in inbox_items; set only via mark_read endpoint
19. `inbox_items.resolved_at` set on ALL terminal transitions (linked_to_issue, dismissed)
20. No `tagged` state exists in inbox lifecycle — only `linked_to_issue`
21. API uses `linked_to_issue` consistently, never abbreviates to `linked`
22. Issues API includes `include_suppressed` and `include_snoozed` params
23. Issue `snoozed` state has fields: `snoozed_until`, `snoozed_by`, `snoozed_at`, `snooze_reason`
24. Signal source mapping table (6.11) defines UI label ↔ API source values for all 7 sources
25. `inbox_suppression_rules` table prevents re-proposal of dismissed items
26. All section numbers are sequential (no duplicates, no gaps)
27. Glossary (Section 0) defines all key terms including Engagement Resolver, Tier, Severity
28. `inbox_items` schema defined in 6.13 with all required fields
29. `issue_transitions` table logs all issue state changes with actor/reason
30. Snooze timer execution specified as hourly job for both issues and inbox items
31. Ambiguous evidence `match_type` values align with 6.8 Engagement Resolver methods
32. API counts use `recently_actioned` (not `recently_tagged`) consistently
33. Engagement states use "State" label (not "Status") throughout UI and API
34. Engagement types defined: `project`, `retainer`
35. Invoice status values defined: `draft`, `sent`, `overdue`, `paid`, `voided`
36. AR aging buckets defined with formulas
37. Tier values defined: `platinum`, `gold`, `silver`, `bronze`, `none`
38. Detector rules enumerated with IDs and trigger conditions
39. Timestamp format specified as ISO 8601
40. Transition reason enum unified across issue_transitions and engagement_transitions
41. `GET /api/inbox/recent` endpoint exists for fetching terminal items
42. `POST /api/inbox/mark_all_read` endpoint exists for bulk read
43. `POST /api/issues/:id/unsuppress` endpoint exists for reversing suppression
44. Suppression expiry defaults defined per item type (Issue: 90d, Flagged Signal: 30d, Orphan: 180d, Ambiguous: 30d)
45. Client status boundary conditions explicitly documented (90d inclusive, 270d inclusive)
46. AR aging edge cases documented (sent+past due, null due_date)
47. Engagement health uses source project task count for linking coverage
48. Action payload validation rules defined per action type
49. Sorting defaults defined (severity desc, age asc)
50. DB CHECK constraints defined for inbox_items integrity
51. Dedupe unique indexes defined for active inbox items per underlying entity
52. `evidence_version` field defined in inbox_items schema
53. Canonical severity ordering defined (critical=5, high=4, medium=3, low=2, info=1)
54. Single-user scope explicitly stated (read/snooze/dismiss are global)
55. Canonical "today" timezone defined (org timezone, local midnight boundaries)
56. `analysis_provider` field defined for minutes signals
57. Signal evidence structure defined (url, display_text, source_system, source_id)
58. Issue snooze ↔ inbox item behavior defined (client page snooze archives inbox item)
59. Assign action sets tagged_by_user_id (same audit trail as tag)
60. `available_actions` returned in issues API response
61. Invoices response includes `aging_bucket` and `status_inconsistent`
62. 403 behavior for forbidden includes explicitly defined (no union payload on error)
63. Year labels in UI use "Prior Yr" and "YTD" (not static year number)
64. Terminal inbox states fetchable via `/api/inbox/recent` (not default `/api/inbox`)
65. Issues schema (6.14) defines all required fields including tagged_*, assigned_*, snoozed_*, suppressed_*
66. Signals schema (6.15) defines all required fields including dismissed_*, analysis_provider
67. Evidence meta-schema (6.16) defines canonical envelope (version, kind, url, display_text, source_system, source_id, payload)
68. Tasks source definition (6.17) for engagement health explicitly excludes completed/archived/subtasks
69. Severity derivation rules defined per issue type (6.14)
70. Strategic design decisions documented (0.2): inbox snooze = reminder snooze, evidence schema standardized, invoice anomaly precedence
71. Suppression source of truth is `inbox_suppression_rules` (not `inbox_items.suppression_key`)
72. read_at semantics: explicit acknowledgment, not view tracking; UI label "Unprocessed"
73. issue_type in inbox response is derived via join (not stored in inbox_items)
74. state param in GET /api/inbox does not include 'all' (only proposed|snoozed)
75. Sorting tie-breaker defined (severity_weight DESC, proposed_at ASC, id ASC)
76. Action response fields defined per action type
77. CHECK constraint for linked_to_issue requires resolved_issue_id
78. CHECK constraint for dismissed requires dismissed_at and dismissed_by
79. /api/inbox/recent response shape defined
80. ?include= behavior: strict for sections; always-present base fields defined
81. Timestamp format is exactly 24 chars with regex validation at app layer
82. TEXT timestamps: DB enforces nullability only; time ordering validated at app layer
83. Single-org multi-user team with org-global shared state (not "single-user")
84. org.timezone required; local_midnight_utc() helper defined
85. finance_calc_version included in financial API responses
86. UI label mapping table (0.3) maps API states to display labels
87. "Unprocessed" UI label for read_at; mark_read endpoint preserved for compatibility
88. issue_category (not issue_type) used in inbox responses to avoid ambiguity
89. Suppression key algorithm: SHA-256, JSON canonical form, key version v1
90. Transaction boundary defined for dismiss action (atomic all-or-nothing)
91. Suppression expiry enforcement query and cleanup job defined
92. /api/inbox/recent supports filtering, sorting, pagination
93. Assign action respects tagged_* preservation (only sets if null)
94. escalate action defined with escalated, escalated_at, escalated_by fields
95. resolved → regression_watch transition is immediate on resolve
96. System-only transitions documented (detected→surfaced, etc.)
97. Create action is two-step flow with draft_engagement
98. Xero link rendering rule: never render link even if url present
99. open_tasks_in_source definition clarified (excludes completed)
100. days_late calculation defined with org-local timezone
101. Engagement lifecycle triggers marked as best-effort, non-test-critical
102. Scoping consistency rule: inbox item scoping must match underlying entity
103. Default sort defined for issues endpoint (severity desc, created_at desc, id asc)
104. POST /api/issues/:id/unsuppress response shape and idempotency defined

---

## Required Test Cases

The following test cases must pass before release:

### Suppression & Dismissal
1. **Dismiss suppression expiry:** Dismiss a flagged_signal with `(source, source_id, rule_triggered)`. Verify same signal does not resurface before expiry (30 days). Verify it CAN resurface after expiry.
2. **Issue suppression:** Suppress an issue via inbox dismiss. Verify `suppressed = true`, excluded from health penalty, excluded from open counts, excluded from inbox.
3. **Unsuppress:** Call `POST /api/issues/:id/unsuppress`. Verify issue reappears in counts and health scoring.

### Snooze Behavior
4. **Snooze expiry boundary:** Snooze an inbox item with `snooze_until` exactly equal to job run time. Verify it resurfaces exactly once (not duplicated).
5. **Issue snooze expiry:** Snooze an issue. Verify `issue_transitions` logs `snoozed → surfaced` with `transition_reason = 'system_timer'`.

### Ambiguous Flow
6. **Ambiguous → Select:** Create ambiguous inbox item. Call `select` action. Verify item becomes actionable with `["tag", "assign", "snooze", "dismiss"]` without changing type.

### Health Scoring
7. **Suppressed excluded:** Issue with `suppressed = true` and `state = surfaced` must NOT appear in health penalty calculation.
8. **Snoozed excluded:** Issue with `state = snoozed` must NOT appear in health penalty calculation.

### Client Status Boundaries
9. **Exactly 90 days:** Client with last invoice exactly 90 days ago is `active`.
10. **Exactly 270 days:** Client with last invoice exactly 270 days ago is `recently_active`.
11. **No invoices:** Client with zero invoices is `cold`.

### Xero Linking
12. **No Xero href:** Verify UI never renders `↗` or clickable link for Xero evidence in any context (inbox, client detail, snapshot).

### Engagement Health Gating
13. **No tasks:** Engagement with `tasks_in_source = 0` returns `(null, "no_tasks")`.
14. **Low linking:** Engagement with `linked_pct < 0.90` returns `(null, "task_linking_incomplete")`.
15. **Coverage source:** Verify `linked_pct` is computed as `tasks_linked / tasks_in_source` (source project total), not `tasks_linked / tasks_in_db`.

### Data Integrity
16. **Constraint: underlying exclusive:** Attempt to set both `underlying_issue_id` and `underlying_signal_id`. Expect constraint violation.
17. **Constraint: snooze requires until:** Attempt to set `state = 'snoozed'` with `snooze_until = NULL`. Expect constraint violation.
18. **Constraint: dismiss requires key:** Attempt to set `state = 'dismissed'` with `suppression_key = NULL`. Expect constraint violation.

### API Validation
19. **Action payload rejection:** Call `POST /api/inbox/:id/action` with `action = 'tag'` and `assign_to` present. Expect `400 Bad Request`.
20. **Required field missing:** Call `POST /api/inbox/:id/action` with `action = 'assign'` and no `assign_to`. Expect `400 Bad Request`.

### Dedupe / Uniqueness
21. **No duplicate active inbox items:** Create two signals that would surface the same issue. Verify only one active inbox item exists (dedupe index prevents duplicates).
22. **Terminal allows new:** After dismissing an inbox item, a new inbox item for the same underlying entity can be created (if suppression expires).

### Snooze / Issue Interaction
23. **Issue snooze archives inbox item:** Snooze an issue from client detail page while a proposed inbox item exists. Verify inbox item transitions to `linked_to_issue` (not left in proposed).
24. **Inbox snooze independent of issue:** Snooze an inbox item. Verify underlying issue state is NOT changed (issue remains surfaced while inbox item is snoozed).

### AR Edge Cases
25. **Sent but past due:** Invoice with `status='sent'` and `due_date <= today`. Verify:
    - `aging_bucket = '1_30'` (or appropriate bucket)
    - `status_inconsistent = true`
    - A `flagged_signal` with rule `invoice_status_inconsistent` is created
26. **No double-create:** Same invoice does NOT create both a financial issue AND a flagged_signal simultaneously (define precedence: issue takes priority once threshold reached).

### Multi-user Scope (v1 single-user)
27. **Global suppression:** User dismisses inbox item. Verify suppression applies globally (no other user can see re-proposals until expiry).
28. **Global read state:** Mark item as read. Verify `read_at` affects all users (single global read_at field).

### Assign Action Audit
29. **Assign sets tagged_by:** Call assign action. Verify `issues.tagged_by_user_id` and `issues.tagged_at` are set (not just assigned_to/assigned_at).

### available_actions
30. **Actions match state:** For each issue state, verify `available_actions` in API response matches the documented mapping.

### Suppression Source of Truth
31. **Enforcement uses rules table:** On new inbox item proposal, verify suppression check queries `inbox_suppression_rules` (not `inbox_items.suppression_key`).
32. **Audit key preserved:** After revoking suppression via `inbox_suppression_rules`, verify historical `inbox_items.suppression_key` is unchanged.

### Suppression Key Collision
33. **Entropy check:** Two different items should not compute same suppression_key. Use strong hash (SHA-256) with sufficient input entropy.
34. **Dismiss reason persists:** Dismiss with note; verify note appears in `/api/inbox/recent` response and in `inbox_suppression_rules.reason`.

### Select Then Dismiss
35. **Ambiguous selected then dismissed:** Select primary on ambiguous item, then dismiss. Verify suppression key uses updated formula (based on resolved signal, not original ambiguous hash).

### Regression Resurfacing
36. **New inbox item on regression:** Issue transitions `resolved → regression_watch → regressed`. Verify a new inbox item is created (dedupe allows since prior inbox item is terminal).

### Timezone Boundaries
37. **Dubai midnight conversion:** Invoice due date "2026-02-07" in UTC. Verify client status boundary uses Asia/Dubai midnight (test at 2026-02-06T20:00:00Z and 2026-02-07T19:59:59Z).

### Tagged Preservation
38. **Assign after tag preserves tagged_by:** Issue is tagged (tagged_by set). Later assigned. Verify `tagged_by_user_id` and `tagged_at` are NOT overwritten.

### Constraint Violations
39. **Constraint: linked requires issue:** Attempt `state = 'linked_to_issue'` with `resolved_issue_id = NULL`. Expect constraint violation.
40. **Constraint: dismissed requires audit:** Attempt `state = 'dismissed'` with `dismissed_by = NULL`. Expect constraint violation.

---

*End of specification.*
