# Client UI Specification — Time OS

*Executable spec for implementation — 2026-02-08*

**Status:** v2.9

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
| **Open Actionable Issues** | Issues in health-counted states: `surfaced`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`. Excludes `detected`, `snoozed`. Used for health penalty and "open issues" counts. |
| **Open All Issues** | All non-closed issues: includes `detected`, `surfaced`, `snoozed`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`. Excludes `regression_watch`, `closed`. Used for total issue inventory. |

---

## 0.1 Global Conventions

**Timestamp Format:**

All timestamp fields stored as TEXT use **Canonical UTC timestamp string (24-char)**:
- **Storage:** Always UTC with `Z` suffix: `YYYY-MM-DDTHH:MM:SS.sssZ`
- **Format:** Exactly 24 characters: `YYYY-MM-DDTHH:MM:SS.sssZ`
- **Ingestion:** Accept offsets (`±HH:MM`) at API boundary, normalize to UTC on write via a **single normalization library choke point**
- **Validation:** App-layer regex: `/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/`

**Accepted Input Formats (Normalization):**

The normalization library MUST accept these formats at ingestion and convert to canonical 24-char:

| Input Format | Example | Normalized Output |
|--------------|---------|-------------------|
| No milliseconds | `2026-02-08T14:30:00Z` | `2026-02-08T14:30:00.000Z` |
| 1-digit ms | `2026-02-08T14:30:00.1Z` | `2026-02-08T14:30:00.100Z` |
| 2-digit ms | `2026-02-08T14:30:00.12Z` | `2026-02-08T14:30:00.120Z` |
| 3-digit ms | `2026-02-08T14:30:00.123Z` | `2026-02-08T14:30:00.123Z` |
| Positive offset | `2026-02-08T18:30:00+04:00` | `2026-02-08T14:30:00.000Z` |
| Negative offset | `2026-02-08T09:30:00-05:00` | `2026-02-08T14:30:00.000Z` |
| Microseconds (truncate) | `2026-02-08T14:30:00.123456Z` | `2026-02-08T14:30:00.123Z` |

**Reject at ingestion:** Unparseable strings, dates without times, times without dates.

**Storage Test Vectors (Post-Normalization):**

| Stored Value | Valid | Notes |
|--------------|-------|-------|
| `2026-02-08T14:30:00.000Z` | ✅ | Zero milliseconds padded |
| `2026-02-08T14:30:00.010Z` | ✅ | 10ms padded to 3 digits |
| `2026-02-08T14:30:00.999Z` | ✅ | Max milliseconds |
| `2026-02-08T14:30:00Z` | ❌ | Missing milliseconds (normalization failed) |
| `2026-02-08T14:30:00.0Z` | ❌ | 1-digit milliseconds |
| `2026-02-08T14:30:00.00Z` | ❌ | 2-digit milliseconds |
| `2026-02-08T14:30:00.0001Z` | ❌ | 4-digit (microseconds) |
| `2026-02-08T14:30:00.000+04:00` | ❌ | Offset instead of Z |

**DB Constraint Limitations:** TEXT timestamps cannot enforce temporal ordering (e.g., "future") in SQL. DB CHECK constraints enforce only nullability and terminal invariants. All time ordering validation is app-layer.

**Lexicographic Comparison Validity:** TEXT timestamp comparisons using `<=`, `>=`, `<`, `>` are valid and order-preserving because the canonical UTC ISO format (`YYYY-MM-DDTHH:MM:SS.sssZ`) is **fixed-width (24 characters)** with zero-padded components. Lexicographic ordering equals chronological ordering. This is a critical invariant — if any timestamp violates the format, comparisons break.

**⚠️ Timestamp Format Migration Risk:**
- TEXT timestamps with strict regex create migration pain if format changes
- If upstream lib emits `...Z` without milliseconds, ingestion fails
- **Mitigation:** Enforce format at API boundary only; normalize on write
- **Future consideration:** Store as INTEGER epoch (ms) in DB; present as canonical text via computed property

**JSON Fields:**

All `evidence` and structured data fields use JSON (or JSONB where supported). Application layer validates structure per schema definitions.

**Calculation Versioning:**

Financial calculations carry a version marker for historical comparisons:
- Current: `finance_calc_version = 'v1'`
- v1: No partial payments; invoices fully paid or fully unpaid
- **API exposure:** Include `finance_calc_version` in financial summary responses

**Currency Handling:**

MVP is single-currency (org has base currency):
- **Required:** `org.base_currency` setting (default: `AED`)
- All invoice amounts are in base currency
- Invoices with non-base currency are flagged at ingestion (create DQ flagged_signal)
- AR sums/issued/paid aggregates are valid only because all amounts are same currency

Future multi-currency support would require:
- `amount_base`, `fx_rate`, `fx_date` fields on invoices
- Normalization at ingestion time
- Historical rate lookups for accurate aggregates

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
- **MVP Constraint:** `org.timezone` MUST be a non-DST timezone (e.g., Asia/Dubai, Asia/Kolkata, UTC). DST zones (e.g., America/New_York, Europe/London) are **rejected at org creation** — not validated lazily.
- Date boundaries computed at local midnight (00:00:00 in org timezone)
- Stored as UTC after conversion
- **"today" computed at:** Request time, using org timezone
- **Per-Request Invariant:** Compute `today_local = get_today_local(org_tz)` **once** at the start of each request and pass it to all subcomputations (client status, aging, windows, snooze). This prevents drift across midnight boundaries within a single request.

**DST Zone Rejection (Hard Rule):**

```python
# At org creation / timezone update
DST_FREE_ZONES = {'Asia/Dubai', 'Asia/Kolkata', 'UTC', ...}  # explicit allowlist

def validate_org_timezone(tz: str) -> bool:
    """Reject DST zones at config time. Do not defer to runtime."""
    if tz not in DST_FREE_ZONES:
        raise ValueError(f"Timezone {tz} not supported (DST zones disallowed in v1)")
    return True
```

Do NOT include DST handling complexity in `local_midnight_utc()` — it is unreachable code if DST zones are rejected at config time.

```python
def local_midnight_utc(org_tz: str, date: date) -> datetime:
    """
    Returns UTC timestamp for midnight of given date in org timezone.

    Assumes org_tz is DST-free (enforced at org creation).
    For DST-free zones: Always safe, no ambiguous/non-existent times.
    """
    tz = ZoneInfo(org_tz)
    naive_midnight = datetime.combine(date, time.min)
    local_midnight = naive_midnight.replace(tzinfo=tz)
    return local_midnight.astimezone(UTC)
```

Example: "today" on 2026-02-07 in Asia/Dubai = 2026-02-06T20:00:00.000Z to 2026-02-07T19:59:59.999Z.

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

def utc_now_iso_ms_z() -> str:
    """Returns current UTC time in canonical 24-char format."""
    now = datetime.now(UTC)
    return now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

def snooze_until(org_tz: str, days: int) -> datetime:
    """Returns snooze expiry as local midnight of (today + N days)."""
    today_local = datetime.now(ZoneInfo(org_tz)).date()
    target_date = today_local + timedelta(days=days)
    return local_midnight_utc(org_tz, target_date)

def is_past_due(due_date: date, today_local: date) -> bool:
    """
    Canonical "overdue" boundary check.

    Returns True if due_date is BEFORE today (strictly less than).
    due_date == today is NOT past due; overdue starts the day AFTER due_date.

    Use this for all overdue/aging logic to ensure consistent boundaries.
    """
    return due_date < today_local

def get_today_local(org_tz: str) -> date:
    """Returns today's date in org timezone."""
    return datetime.now(ZoneInfo(org_tz)).date()
```

**Boundary Invariant:** All date comparisons use `is_past_due()` or equivalent `<` logic. Never use `<=` for overdue checks. Reference this helper when implementing invoice aging, status_inconsistent flags, or any "past due" logic.

**DB Write Discipline:**
- **Timestamps:** DB writes NEVER call `now()` or `CURRENT_TIMESTAMP` directly. All timestamp writes use `utc_now_iso_ms_z()` from app-layer time library. This ensures consistent 24-char format with exactly 3-digit milliseconds.
- **IDs:** DB-side UUID generation (e.g., `uuid()`, `gen_random_uuid()`) IS allowed. IDs do not require app-layer control because format consistency is not a concern.
- **Rationale:** Timestamps need app-layer control for format consistency; IDs are opaque and format-agnostic.

**SQL Snippet Convention:** When spec shows `uuid()` in SQL examples, this represents either DB-side or app-side UUID generation — implementation may choose. When spec shows `:now_iso`, this MUST be app-side `utc_now_iso_ms_z()` passed as parameter.

**Time Library Usage (Required):**

All timestamp and date boundary operations MUST use time library functions. Direct calls are forbidden:

| Forbidden | Required Alternative |
|-----------|---------------------|
| `now()` in SQL | Pass `:now_iso` from `utc_now_iso_ms_z()` |
| `CURRENT_TIMESTAMP` in SQL | Pass `:now_iso` from `utc_now_iso_ms_z()` |
| `Date.now()` in JS/TS | Use time library wrapper |
| `datetime.now()` in Python | Use `utc_now_iso_ms_z()` or `get_today_local(org_tz)` |
| Client device timezone | Always use `org.timezone` |
| Rolling 24-hour windows | Use `local_midnight_utc()` for day boundaries |

**Timestamp Format Enforcement (Defense in Depth):**

1. **App-layer validation (required):** All timestamp writes pass through parse+roundtrip validator:
   ```python
   def validate_timestamp(ts: str) -> bool:
       """
       Parse+roundtrip validator — the REAL gate.
       Regex/GLOB only checks shape; this checks semantics.
       """
       if len(ts) != 24:
           return False
       try:
           # Parse the string
           dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
           # Roundtrip: format back to canonical
           canonical = dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'
           # Must match exactly
           return ts == canonical
       except ValueError:
           return False

   # Examples:
   # validate_timestamp('2026-02-08T14:30:00.000Z') → True
   # validate_timestamp('2026-99-99T99:99:99.999Z') → False (valid shape, invalid date)
   # validate_timestamp('2026-02-08T14:30:00Z') → False (missing ms)
   ```
2. **DB-layer constraint (shape-only defense):**
   ```sql
   -- GLOB/regex catches shape errors only; parse+roundtrip catches semantic errors
   -- SQLite: CHECK constraint with GLOB pattern
   ALTER TABLE issues ADD CONSTRAINT chk_created_at_format
     CHECK (created_at GLOB '????-??-??T??:??:??.???Z');

   -- PostgreSQL: CHECK constraint with regex
   ALTER TABLE issues ADD CONSTRAINT chk_created_at_format
     CHECK (created_at ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$');
   ```
   **Note:** DB constraints catch shape errors (wrong length, missing Z) but cannot catch invalid dates (month=99). App-layer parse+roundtrip is the authoritative validator.
3. **Runtime canary (required):** On service startup, validate ALL timestamp columns across ALL tables using `validate_timestamp()` (not just length check):
   ```python
   TIMESTAMP_COLUMNS = {
       'inbox_items': ['proposed_at', 'last_refreshed_at', 'read_at', 'resolved_at',
                       'snooze_until', 'snoozed_at', 'dismissed_at', 'created_at', 'updated_at',
                       'resurfaced_at'],
       'issues': ['created_at', 'updated_at', 'tagged_at', 'assigned_at', 'snoozed_until',
                  'snoozed_at', 'suppressed_at', 'escalated_at', 'resolved_at',
                  'regression_watch_until', 'closed_at'],
       'signals': ['observed_at', 'ingested_at', 'dismissed_at', 'created_at', 'updated_at'],
       'issue_transitions': ['transitioned_at'],
       'engagement_transitions': ['transitioned_at'],
       'inbox_suppression_rules': ['created_at', 'expires_at'],
   }

   def validate_all_timestamps():
       """
       Full semantic validation on startup — catches shape, value, AND ordering errors.
       Length check alone misses invalid dates like 2026-99-99T00:00:00.000Z.
       """
       violations = []
       for table, columns in TIMESTAMP_COLUMNS.items():
           for col in columns:
               rows = query(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
               for row in rows:
                   if not validate_timestamp(row[col]):
                       violations.append((table, col, row.id, row[col], 'invalid_format'))

       # Ordering validation (cross-field invariants)
       ordering_violations = validate_timestamp_ordering()
       violations.extend(ordering_violations)

       if violations:
           alert(f"CRITICAL: {len(violations)} timestamp violations detected")
           for table, col, id, val, reason in violations[:10]:  # Log first 10
               log(f"  {table}.{col} id={id}: '{val}' ({reason})")
           return False
       return True

   def validate_timestamp_ordering() -> list:
       """
       Validate cross-field timestamp ordering invariants.
       These invariants ensure lexicographic comparisons work correctly.
       """
       violations = []

       # Inbox items: resurfaced_at >= proposed_at (if set)
       rows = query("""
           SELECT id, proposed_at, resurfaced_at FROM inbox_items
           WHERE resurfaced_at IS NOT NULL AND resurfaced_at < proposed_at
       """)
       for row in rows:
           violations.append(('inbox_items', 'resurfaced_at', row.id, row.resurfaced_at, 'resurfaced_before_proposed'))

       # All tables: updated_at >= created_at
       for table in ['inbox_items', 'issues', 'signals', 'engagements']:
           rows = query(f"""
               SELECT id, created_at, updated_at FROM {table}
               WHERE updated_at < created_at
           """)
           for row in rows:
               violations.append((table, 'updated_at', row.id, row.updated_at, 'updated_before_created'))

       # Issues: resolved_at >= created_at (if set)
       rows = query("""
           SELECT id, created_at, resolved_at FROM issues
           WHERE resolved_at IS NOT NULL AND resolved_at < created_at
       """)
       for row in rows:
           violations.append(('issues', 'resolved_at', row.id, row.resolved_at, 'resolved_before_created'))

       return violations
   ```

   **Why full validation:** Length check (`length(col) != 24`) catches format errors but misses semantic invalids like `2026-99-99T00:00:00.000Z` (valid shape, invalid date). The parse+roundtrip in `validate_timestamp()` catches both.

   **TIMESTAMP_COLUMNS Drift Prevention (Migration Checklist):**
   - **Invariant:** All columns ending with `_at` or `_until` MUST be registered in `TIMESTAMP_COLUMNS`
   - **CI check:** Add a test that compares schema introspection against `TIMESTAMP_COLUMNS` registry
   - **Migration checklist item:** "If adding/removing timestamp column, update TIMESTAMP_COLUMNS"
   - **Failure mode:** Unregistered timestamp columns will not be validated by startup canary

4. **Repair command (admin-only):** Provide a CLI command to find and fix malformed timestamps:
   ```bash
   timeos db:repair-timestamps --dry-run  # Report violations
   timeos db:repair-timestamps --fix      # Attempt normalization; quarantine unfixable rows
   ```
   Unfixable rows (unparseable) should be moved to `_quarantine` tables for manual review.

**Failure mode:** One malformed timestamp breaks lexicographic ordering, causing snooze expiry, window queries, and date comparisons to silently return wrong results.

**Field Naming Conventions (Date vs Timestamp):**

| Suffix | Format | Example | Validation |
|--------|--------|---------|------------|
| `*_date` | `YYYY-MM-DD` (10 chars) | `due_date`, `issue_date` | `/^\d{4}-\d{2}-\d{2}$/` |
| `*_at` | `YYYY-MM-DDTHH:MM:SS.sssZ` (24 chars) | `created_at`, `resolved_at` | `/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/` |
| `*_until` | `YYYY-MM-DDTHH:MM:SS.sssZ` (24 chars) | `snooze_until`, `expires_at` | Same as `*_at` |

**Snooze Field Naming (Hard Invariant):**

Snooze fields differ by table to prevent confusion:

| Table | Timestamp Field | Actor Fields |
|-------|-----------------|--------------|
| `inbox_items` | `snooze_until` | `snoozed_at`, `snoozed_by`, `snooze_reason` |
| `issues` | `snoozed_until` | `snoozed_at`, `snoozed_by`, `snooze_reason` |

- Inbox uses `snooze_until` (noun-form: "the snooze until")
- Issues uses `snoozed_until` (verb-form: "snoozed until")
- All other snooze fields use past tense: `snoozed_at`, `snoozed_by`
- **Enforcement:** Grep codebase for field name typos during CI/PR checks

- `*_date` fields are org-local dates (compared using local midnight boundaries)
- `*_at` and `*_until` fields are UTC timestamps (always include `.sss` milliseconds)
- App-layer validators enforce format before DB write

**Invoice Due Date Interpretation:**
- Xero `due_date` is a date without timezone (e.g., `2026-02-15`)
- Interpreted as org-local date for all comparisons
- "Today" is computed in org timezone (e.g., Asia/Dubai)
- Invoice becomes overdue starting the day **after** `due_date` in org timezone
- Test: `due_date = today` → NOT overdue; `due_date = yesterday` → overdue

**Invoice Date Arithmetic (Canonical):**

All invoice overdue calculations MUST use these exact formulas:

```python
def compute_invoice_overdue(invoice, org_tz: str):
    """Canonical invoice overdue calculation. Never use now() or rolling windows."""
    today_local = get_today_local(org_tz)  # org-local date
    due_date = invoice.due_date            # date object, not datetime

    if due_date is None:
        return None, None  # (days_overdue, is_overdue) both unknown

    if is_past_due(due_date, today_local):  # due_date < today_local
        days_overdue = (today_local - due_date).days  # date arithmetic, always positive
        return days_overdue, True
    else:
        return 0, False  # Not overdue; days_overdue=0 (not null)
```

**Invariants:**
- `today_local` is always `get_today_local(org_tz)`, never `datetime.now().date()`
- `days_overdue` uses date subtraction (`.days`), not timedelta division

**days_overdue Semantics (Hard Invariant):**
- `days_overdue = null` → `due_date` is missing (cannot compute)
- `days_overdue = 0` → invoice is NOT overdue (due today or future)
- `days_overdue > 0` → invoice IS overdue by N days
- **Never use null for "not overdue"** — use 0
- Bucket logic relies on `days_overdue BETWEEN ...` which requires numeric
- API responses: always return integer or null (never "not applicable" strings)
- `is_past_due()` uses `<`, never `<=`
- Do NOT use rolling 24-hour windows

---

## 0.2 Strategic Design Decisions

**Decision A: Two Snooze Concepts (Deterministic Distinction)**

There are exactly two snooze operations with different semantics:

| Snooze Type | API Endpoint | Target | Health Impact |
|-------------|--------------|--------|---------------|
| **Inbox snooze** | `POST /api/inbox/:id/action { action:"snooze" }` | Reminder only | ❌ Unchanged |
| **Issue snooze** | `POST /api/issues/:id/transition { action:"snooze" }` | Problem itself | ✅ Removed |

**Hard Rule — Copy Derives from Endpoint, Not Screen:**
- UI copy MUST be determined by which API endpoint the action calls
- NEVER infer from "where user clicked" (Inbox screen vs Client Page)
- Same button in different locations may call different endpoints → show different copy

**Decision A.1: Exact Required UI Copy**

**Inbox snooze modal (when calling `/api/inbox/:id/action`):**
```
"Snoozing hides this reminder. The issue remains open and affects health score. Health unchanged."
```

**Issue snooze modal (when calling `/api/issues/:id/transition`):**
```
"Health impact removed while snoozed. Issue will resurface after [date]."
```

**Snooze Timing Precision:** With hourly expiry jobs, items resurface within ~1 hour of target. Say "after [date]" not "at midnight on [date]".

**Decision A.2: Client Page Badge (Required)**

When an issue appears in Top Issues but its inbox reminder is snoozed:
- **Query:** `SELECT snooze_until FROM inbox_items WHERE underlying_issue_id = :issue_id AND state = 'snoozed'`
- **If row exists:** Show badge on issue card: `"Reminder snoozed until [date]"`
- **Render always:** Badge appears even if issue is surfaced/addressing/etc.
- **Purpose:** Prevents "snooze didn't work" confusion

**Decision A.3: Inbox Card Must Show Both States (type=issue)**

For inbox items where `type = 'issue'`, the card MUST display:
```
Inbox State: proposed          ← from inbox_items.state
Issue State: addressing        ← from issues.state (via join)
```

This prevents users from confusing the proposal lifecycle with the issue lifecycle.

**Decision A.4: Auto-Archive Inbox on Issue Transition**

When an issue transitions to a state that makes the inbox reminder moot, auto-archive the inbox item:

| Issue Transition | Inbox Item Action |
|------------------|-------------------|
| Issue → `snoozed` | `inbox_item.state = 'linked_to_issue'`, `resolution_reason = 'issue_snoozed_directly'` |
| Issue → `regression_watch` | `inbox_item.state = 'linked_to_issue'`, `resolution_reason = 'issue_resolved_directly'` |
| Issue → `closed` | `inbox_item.state = 'linked_to_issue'`, `resolution_reason = 'issue_closed_directly'` |

**Implementation:**
```python
def on_issue_transition(issue, new_state):
    if new_state in ('snoozed', 'regression_watch', 'closed'):
        inbox_item = query("SELECT * FROM inbox_items WHERE underlying_issue_id = ? AND state IN ('proposed', 'snoozed')", issue.id)
        if inbox_item:
            update_inbox_item(
                id=inbox_item.id,
                state='linked_to_issue',
                resolved_at=utc_now_iso_ms_z(),
                resolved_issue_id=issue.id,
                resolution_reason=f'issue_{new_state}_directly'
            )
```

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
| `resolved` | *(conceptual only — never persisted, never returned; see §6.5)* | — |
| `regression_watch` | "Resolved (watching)" | Closed |
| `closed` | "Closed" | Closed |
| `regressed` | "Regressed" | Open |

**Never use "watch loop" as a state label in UI.** "Watch loop" is background behavior only.

**read_at / Unprocessed:**
- UI label: "Unprocessed" (not "Unread")
- API endpoint: `/mark_read` (preserved for compatibility)
- Meaning: User has explicitly acknowledged seeing the item
- Simpler migrations when evidence evolves

---

## 0.4 Centralized Button Label → API Action Mapping

**Hard Rule:** Button labels MUST map from this table. No ad-hoc labels.

**Inbox Actions (target: inbox_item):**

| Button Label | API Call | Action Value | Effect |
|--------------|----------|--------------|--------|
| "Tag & Watch" | `POST /api/inbox/:id/action` | `tag` | Terminalize inbox → `linked_to_issue`, issue → `acknowledged` |
| "Assign" | `POST /api/inbox/:id/action` | `assign` | Terminalize inbox → `linked_to_issue`, issue → `addressing` |
| "Snooze 7d" | `POST /api/inbox/:id/action` | `snooze` | `state = 'snoozed'`, set `snooze_until` (server-computed) |
| "Dismiss" | `POST /api/inbox/:id/action` | `dismiss` | `state = 'dismissed'`, suppress underlying |
| "Link to Engagement" | `POST /api/inbox/:id/action` | `link` | Resolve orphan, type → `flagged_signal` |
| "Create Engagement" | `POST /api/inbox/:id/action` | `create` | Start engagement creation flow |
| "Select" | `POST /api/inbox/:id/action` | `select` | Resolve ambiguous, type → `flagged_signal` |

**Client Page Issue Actions (target: issue):**

| Button Label | API Call | Action Value | Effect |
|--------------|----------|--------------|--------|
| "Acknowledge" | `POST /api/issues/:id/transition` | `acknowledge` | Issue → `acknowledged`, auto-archive inbox |
| "Assign" | `POST /api/issues/:id/transition` | `assign` | Issue → `addressing`, auto-archive inbox |
| "Snooze 7d" | `POST /api/issues/:id/transition` | `snooze` | Issue → `snoozed`, health removed, auto-archive inbox |
| "Mark Addressing" | `POST /api/issues/:id/transition` | `addressing` | Issue → `addressing` |
| "Awaiting Resolution" | `POST /api/issues/:id/transition` | `await` | Issue → `awaiting_resolution` |
| "Resolve" | `POST /api/issues/:id/transition` | `resolve` | Issue → `regression_watch`, auto-archive inbox |

**Semantic Equivalence Note:**
- "Tag & Watch" (Inbox) ≈ "Acknowledge" (Client Page) — both confirm user attention
- Labels differ by context; underlying semantics are similar
- Frontend MUST use this table as single source of truth for label→action mapping

**Decision C: Invoice Anomaly Precedence**

When an invoice qualifies for both a financial issue AND a flagged_signal (e.g., overdue AND status-inconsistent):
- **Issue takes precedence** once aggregation threshold is reached
- Do NOT create a flagged_signal for the same invoice+rule in the same detector run
- Exception: `invoice_status_inconsistent` flagged_signal is created ONLY if no financial issue exists for that invoice

**Explicit Codification:**
- **Financial issue creation:** Only triggers when Xero `status = 'overdue'` (source-system value)
- **Sent + past due (status_inconsistent):** Does NOT create a financial issue; creates a DQ flagged_signal only
- **Aging buckets:** Treat `sent + past due` as overdue FOR DISPLAY purposes only
- **status is never mutated:** The `status` field reflects source-system value; overdue-ness is computed via `days_overdue`/`status_inconsistent` fields

**Decision D: Scoping Precedence (Canonical)**

When computing suppression keys, aggregation keys, or any scope-based logic, use this precedence:

1. **engagement_id** (most specific) — if present, use it
2. **brand_id** (fallback) — if engagement_id is null but brand_id exists
3. **client_id + root_cause_fingerprint** — if both engagement_id and brand_id are null

```python
def get_scoping_key(entity) -> dict:
    """Canonical scoping precedence for suppression/aggregation."""
    if entity.engagement_id:
        return {'engagement_id': entity.engagement_id}
    elif entity.brand_id:
        return {'brand_id': entity.brand_id}
    else:
        return {'client_id': entity.client_id, 'fingerprint': entity.root_cause_fingerprint}
```

This applies to: suppression keys, issue aggregation, coupling discovery, report scoping.

**Decision E: Inbox Severity — Live Max (Not Snapshot)**

Inbox items denormalize `severity` from the underlying issue at upsert time, but issues can escalate (manual or system). To prevent drift:

- **Read-time rule:** `display_severity = MAX(inbox_items.severity, issues.severity)`
- **Why not update inbox_items.severity?** Audit trail — preserve original proposal severity
- **Sort uses display_severity:** Control Room sorts by `display_severity`, not stored `inbox_items.severity`
- **API response:** Include both `severity` (snapshot) and `display_severity` (computed max)

```json
{
  "id": "...",
  "type": "issue",
  "severity": "medium",           // snapshot at proposal time (audit)
  "display_severity": "high",     // MAX(inbox, issue) — use for display/sort
  ...
}
```

**Decision F: Org-Global Read State Rules**

`read_at` is org-global (one user's mark affects all). Codified rules:

| Action | Who Can Perform | Scope |
|--------|-----------------|-------|
| `mark_read` (single) | Any authenticated org member | Item must be non-terminal |
| `mark_all_read` | Any authenticated org member | **Proposed only** (excludes snoozed) |

**mark_all_read scope:** Only marks `state = 'proposed'` items. Snoozed items are excluded because they're intentionally deferred and will resurface later.

```sql
-- mark_all_read implementation
UPDATE inbox_items SET read_at = :now_iso, updated_at = :now_iso
WHERE state = 'proposed' AND read_at IS NULL;
```

**Decision G: UI Copy Blacklist (Forbidden Terms)**

To prevent user confusion, these terms MUST NEVER appear in the UI:

| Forbidden Term | Required Alternative | Rationale |
|----------------|---------------------|-----------|
| "Read" / "Unread" | "Processed" / "Unprocessed" | Avoids confusion with email semantics |
| "Watch loop" | (do not mention) | Internal behavior, not user-facing |
| "Resolved" (for issues) | "Resolved (watching)" | State is `regression_watch`, not `resolved` |
| "Monitoring" | "Awaiting resolution" | Deprecated term |

**CI Test:** Add a string search test that fails if forbidden terms appear in UI copy.

**Decision H: Snooze Button Component Invariant**

Any Snooze button in the UI MUST be instantiated with explicit target:

```typescript
interface SnoozeButtonProps {
  target_type: 'inbox' | 'issue';
  target_id: string;
  // Copy and payload are derived from target_type, not screen location
}

// Usage
<SnoozeButton target_type="inbox" target_id={inboxItem.id} />  // Inbox snooze copy
<SnoozeButton target_type="issue" target_id={issue.id} />      // Issue snooze copy
```

- **Hard rule:** Never derive snooze semantics from "which screen the user is on"
- Component determines copy and API endpoint from `target_type`
- Prevents mismatched copy when same issue appears in multiple contexts
```

**Hard Rule:** `invoice.status` is source-of-truth from Xero. Never mutate it. All overdue calculations derive from `days_overdue` and `status_inconsistent`.

**Financial Issue Evidence Invariant:**
- `evidence.payload.status` = source status from Xero (e.g., "sent", "overdue")
- `evidence.payload.status_inconsistent` = boolean flag if status doesn't match days_overdue reality
- UI can display "Overdue (status: sent)" to show the discrepancy; don't hide it

This prevents duplicate proposals and conflicting actions.

---

## 0.5 Attention Age (Canonical)

**Definition:** `attention_age_start_at` = the timestamp when this item last required attention.

```python
def attention_age_start_at(item) -> str:
    """Canonical attention age timestamp for sorting and display."""
    return item.resurfaced_at or item.proposed_at
```

**Usage:**
- "Age" sort on Inbox and Issues lists uses `attention_age_start_at` descending (oldest = needs attention longest)
- Display label "Proposed Xd ago" uses `attention_age_start_at` (not always `proposed_at`)
- If item resurfaced from snooze, age resets from resurface time
- API response SHOULD include `attention_age_start_at` for frontend consistency

**Invariant:** `attention_age_start_at` is NEVER null (`proposed_at` is always set on creation).

---

## 1. Control Room — Inbox (Proposals)

### 1.1 Purpose

The Inbox is the **global intake surface** for items requiring your attention. The system sifts signals from other people's meetings, tasks, chats, calendar, and email—then proposes out-of-norm items here with context and proof.

This is where the watch loop begins.

### 1.2 Inbox Structure

```
CONTROL ROOM — INBOX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Needs Attention: 12]  [Snoozed: 3]  [Recently Actioned: 8]   ← TABS (state filter)

Filter: [All ▼] [Issues ▼] [Flagged Signals ▼] [Orphans ▼] [Ambiguous ▼]  ← TYPE filter
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

**UX Rule: Show Issue State on Inbox Cards**

When an inbox item wraps an existing issue (`type = 'issue'`), display **both** states inline:
- Inbox State: `proposed` / `snoozed`
- Issue State: `surfaced` / `acknowledged` / `addressing` / etc.

Example card line: `Inbox State: proposed · Issue State: addressing (assigned to Sarah)`

This prevents users from confusing the proposal state with the issue lifecycle state.

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
| `dismissed` | `dismissed` | User dismissed; logged for audit | Yes | Excluded from default list; fetchable via `/recent` |
| `linked_to_issue` | `linked_to_issue` | Item resolved into tracked issue | Yes | Excluded from default list; fetchable via `/recent` |

**Note:** There is no separate `tagged` state. All "Tag & Watch" actions result in `linked_to_issue` (issue is created or linked, inbox item archived).

**Tabs vs Filters (UI Semantics):**
- **Tabs** control which items to show by state:
  - "Needs Attention" → `state=proposed`
  - "Snoozed" → `state=snoozed`
  - "Recently Actioned" → `/api/inbox/recent` (terminal states)
- **Type Filter** (dropdown) controls which inbox item types to show: all, issues, flagged_signals, orphans, ambiguous
- **"All" in type filter** does NOT map to `state=all` (which is invalid); it means "all types within current tab"

**Inbox State Transition Table (Allowed Edges):**

| From State | To State | Trigger | Actor |
|------------|----------|---------|-------|
| `proposed` | `snoozed` | User snooze action | user |
| `proposed` | `dismissed` | User dismiss action | user |
| `proposed` | `linked_to_issue` | User tag/assign action | user |
| `snoozed` | `proposed` | Snooze timer expiry | system |
| `snoozed` | `dismissed` | User dismiss action (from Snoozed tab) | user |
| `snoozed` | `linked_to_issue` | User tag/assign action (from Snoozed tab) | user |

**Invalid transitions (reject with 409):**
- `dismissed` → any (terminal)
- `linked_to_issue` → any (terminal)
- `proposed` → `proposed` (no-op)
- `snoozed` → `snoozed` (use update snooze endpoint instead)

```python
INBOX_TRANSITIONS = {
    'proposed': {'snoozed', 'dismissed', 'linked_to_issue'},
    'snoozed': {'proposed', 'dismissed', 'linked_to_issue'},
    'dismissed': set(),  # terminal
    'linked_to_issue': set(),  # terminal
}

def validate_inbox_transition(from_state: str, to_state: str) -> bool:
    return to_state in INBOX_TRANSITIONS.get(from_state, set())
```

**Terminal State Behavior:**
- Default `GET /api/inbox` excludes terminal states (dismissed, linked_to_issue)
- `GET /api/inbox/recent?days=N` fetches terminal items actioned within N days (for audit/review)
- Terminal items in `/recent` are read-only; `read_at` is not affected by viewing them

---

**Terminal State Transitions (Atomic Writes):**

When transitioning to terminal states (`dismissed`, `linked_to_issue`), all fields must be set atomically in a single transaction to satisfy CHECK constraints:

```sql
-- Example: dismiss action (all timestamps passed from app layer)
UPDATE inbox_items SET
  state = 'dismissed',
  resolved_at = :now_iso,        -- utc_now_iso_ms_z()
  updated_at = :now_iso,
  dismissed_by = :user_id,
  dismissed_at = :now_iso,
  dismiss_reason = :note,
  suppression_key = :computed_key
WHERE id = :item_id;
```

Never set `state` first then timestamps — this violates `chk_terminal_requires_resolved`.

---

**Inbox Item Snooze Timer Execution:**

**Snooze Duration Semantics:**
- "Snooze N days" = until local midnight of `(today + N days)` in org timezone
- Aligns with "days=N uses org-local day boundaries" convention
- Example: Snooze 7d on 2026-02-08 at 3pm Dubai:
  - Local target: 2026-02-15 00:00:00 Dubai (midnight of today+7)
  - **Stored value (inbox):** `inbox_items.snooze_until = 2026-02-14T20:00:00.000Z` (UTC, canonical format)
  - **Stored value (issue):** `issues.snoozed_until = 2026-02-14T20:00:00.000Z` (UTC, canonical format)
- Use `snooze_until(org_tz, days)` from time library (see §0.1)

**Midnight Edge Case:**
- "today" is always computed using `org.timezone`, never client device timezone
- Request at 2026-02-08T23:59:00 Dubai → today = 2026-02-08 (Dubai)
- Request at 2026-02-08T20:01:00 UTC (= 2026-02-09T00:01:00 Dubai) → today = 2026-02-09 (Dubai)
- API must resolve org timezone before computing snooze_until

**Snooze Expiry is Inclusive:**
- Condition: `snooze_until <= :now_iso`
- At the instant `now >= snooze_until`, item resurfaces
- If `snooze_until = 2026-02-15T00:00:00.000Z` and job runs at `2026-02-15T00:00:00.000Z`, item resurfaces

**Server-Side Snooze Computation (Required):**
- Server MUST compute `snooze_until` from `snooze_days` param
- Client-provided `snooze_until` is IGNORED (prevents timezone bugs)
- Store `snooze_days` optionally for audit/debugging
- Use `snooze_until(org_tz, snooze_days)` helper exclusively

Snooze expiry for inbox items is executed by a **scheduled job** (runs hourly, same job as issue snooze):

1. Query: `SELECT * FROM inbox_items WHERE state = 'snoozed' AND snooze_until <= :now_iso`
2. For each expired item:
   - Update `inbox_items.state = 'proposed'`
   - **Set `inbox_items.resurfaced_at = :now_iso`** — marks resurface time for unprocessed calculation
   - Clear snooze fields: `snooze_until = NULL`, `snoozed_by = NULL`, `snoozed_at = NULL`, `snooze_reason = NULL`
   - Update `inbox_items.updated_at = :now_iso`
   - **Do NOT clear `read_at`** — preserves audit trail that team previously acknowledged the item

**Note:** `:now_iso` is always `utc_now_iso_ms_z()` from app layer. Never use DB-side `now()`.

**Returning by Tomorrow Count (Precision Note):**
- Count uses `snooze_until < local_midnight_utc(org_tz, today + 2 days)` (before end of tomorrow)
- Snooze expiry job runs hourly, so actual resurface may be up to ~1 hour after `snooze_until`
- **UI label:** "Returning by tomorrow" (expected, not guaranteed exact time)

**read_at on Snooze Expiry:**
- `read_at` is NOT cleared when snooze expires and item resurfaces
- Rationale: "read" means "team has acknowledged seeing it at least once"
- Resurfaced items may have non-null `read_at` — this is intentional

**resurfaced_at (Required Field):**
- Set when snooze expires and item transitions back to `proposed`
- **Unprocessed definition:** `read_at IS NULL OR read_at < resurfaced_at`
- This allows UI to correctly show items as "unprocessed again" after resurface without clearing `read_at`

```python
def is_unprocessed(inbox_item) -> bool:
    """Canonical unprocessed check — accounts for resurface."""
    if inbox_item.read_at is None:
        return True
    if inbox_item.resurfaced_at and inbox_item.read_at < inbox_item.resurfaced_at:
        return True
    return False
```

**resurfaced_at Invariants (Hard Rules):**
- `resurfaced_at` can ONLY be set by the snooze expiry job (system timer `snoozed → proposed`)
- Manual unsnooze does NOT set `resurfaced_at` (item was never truly "hidden then revealed")
- If set, MUST satisfy: `resurfaced_at >= proposed_at`
- `resurfaced_at` is monotonically increasing: once set, only increases on subsequent resurfaces
- Newly created items have `resurfaced_at = NULL`

```sql
-- DB constraint (partial — full enforcement requires app layer)
ALTER TABLE inbox_items ADD CONSTRAINT chk_resurfaced_after_proposed
  CHECK (resurfaced_at IS NULL OR resurfaced_at >= proposed_at);
```

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
| **Snooze** | `snooze` | Any | Hides inbox item for N days (until local midnight of today + N), resurfaces as `proposed` |
| **Dismiss** | `dismiss` | Any | Archives inbox item, suppresses underlying entity (see 1.5) |
| **Link to Engagement** | `link` | Orphan, Ambiguous | Associates signal with existing engagement, resolves orphan/ambiguous |
| **Create Engagement** | `create` | Orphan | Opens engagement creation flow, then links signal |
| **Select Primary** | `select` | Ambiguous | User picks one candidate; system resolves ambiguity; item becomes actionable via Tag/Assign |

**Action Naming: Inbox vs Issue API (with UI Labels)**

| Inbox Action | Issue Action | UI Label (Inbox) | UI Label (Client Page) | Effect |
|--------------|--------------|------------------|------------------------|--------|
| `tag` | `acknowledge` | "Tag & Watch" | "Acknowledge" | Transitions issue to `acknowledged` state |
| `assign` | `assign` | "Assign" | "Assign" | Transitions issue to `addressing` state |
| `snooze` | `snooze` | "Snooze 7d" | "Snooze" | (Inbox snooze ≠ issue snooze semantics) |
| `dismiss` | *(N/A)* | "Dismiss" | — | Sets `issues.suppressed = true` |
| `link` | *(N/A)* | "Link to Engagement" | — | Orphan resolution |
| `create` | *(N/A)* | "Create Engagement" | — | Orphan resolution |
| `select` | *(N/A)* | "Select Primary" | — | Ambiguous resolution |

**Implementation:** Frontend MUST use this table for button labels. API responses include action names only; frontend maps to labels. Centralizing here prevents label drift.

**Select Primary Flow:**
1. User views candidate list in Ambiguous inbox item
2. User selects one engagement
3. System links signal to selected engagement
4. Inbox item `type` converts from `ambiguous` → `flagged_signal` (now fully resolved and actionable)
5. Available actions change to: `[Tag & Watch] [Assign] [Snooze 7d] [Dismiss]`

**Rationale for type conversion:** After engagement selection, the item is semantically identical to a flagged_signal (single signal with resolved engagement). Converting the type simplifies suppression key logic and action handling — no special "post-select ambiguous" branches needed.

### 1.7 Tag & Watch Action (Detailed)

When you click **Tag & Watch**:

1. If Flagged Signal: create new issue from signal
2. If Issue: use existing issue
3. Set `issues.tagged_by_user_id = current_user`
4. Set `issues.tagged_at = utc_now_iso_ms_z()`
5. Transition issue to `acknowledged` state
6. **Watch loop begins** (background behavior, not a state):
   - System gathers additional context from related signals
   - Adds new evidence as it arrives
   - Alerts if situation escalates
   - Continues until issue reaches `regression_watch` or `closed` (post-resolve lifecycle)
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
5. Set `issues.assigned_at = utc_now_iso_ms_z()`
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

**Recommended audit trail UI copy:** "Assigned (and acknowledged)" or "Assigned; watch loop started" to clarify that assign implicitly acknowledges.

**Assign Semantics:**
- Assign implies acknowledgment — the `tagged_*` fields represent acknowledgment even when state goes directly to `addressing`
- User saw and acted on the issue; no separate "acknowledged" state needed
- This is intentional: "Assign" is a stronger commitment than "Acknowledge"

**Transition Log for Assign:**

Log a **single transition** for audit clarity:
- `surfaced → addressing` (actor: user, transition_reason: 'user')
- Do NOT log two transitions (surfaced → acknowledged → addressing)
- The `tagged_*` fields capture the acknowledgment moment; the state machine shows direct path to addressing

### 1.8 Dismiss Action (Detailed)

When you click **Dismiss**:

1. Archive inbox item as `dismissed`
2. Set `inbox_items.resolved_at = utc_now_iso_ms_z()`
3. Compute and store suppression key (see below)
4. Suppress underlying entity:
   - If Issue: set `issues.suppressed = true`, `issues.suppressed_at = utc_now_iso_ms_z()`, `issues.suppressed_by = current_user`
   - If Signal: set `signals.dismissed = true`, `signals.dismissed_at = utc_now_iso_ms_z()`, `signals.dismissed_by = current_user`
5. **Suppression behavior:**
   - Suppressed issues are excluded from health scoring
   - Suppressed issues do not resurface unless the same root cause triggers a new issue
   - Dismissal is logged for audit but does NOT create a new issue state

**Required UI microcopy (per inbox item type):**
- **Issue:** "Dismiss hides repeat proposals for 90 days. This does not resolve the issue."
- **Flagged Signal:** "Dismiss hides similar proposals for 30 days."
- **Orphan:** "Dismiss hides this orphan for 180 days."
- **Ambiguous:** "Dismiss hides this ambiguous match for 30 days."

**UI Test Requirement:** Dismiss modal tests MUST verify exact copy is shown. For issues, copy must include "does not resolve" AND "hides" to prevent user confusion.

**Suppression Key (prevents identical re-proposals):**

When an inbox item is dismissed, compute a deterministic suppression key based on **current** type at dismissal time:

| Item Type | Suppression Key Formula | When Used |
|-----------|------------------------|-----------|
| Issue | `suppression_key("issue", {issue_type, client_id, engagement_id})` | Always |
| Flagged Signal | `suppression_key("flagged_signal", {client_id, engagement_id, source, rule_triggered})` | Native flagged_signal OR post-link orphan OR post-select ambiguous |
| Orphan | `suppression_key("orphan", {identifier_type, identifier_value})` | Unresolved orphan dismissed without linking |
| Ambiguous | `suppression_key("ambiguous", {signal_id})` | Unresolved ambiguous dismissed without selecting |

**Note on Link/Select Type Conversion:** After `link` (orphan) or `select` (ambiguous), the inbox item type converts to `flagged_signal` (see §7.10 Post-Link/Select Behavior). Subsequent dismissal uses the Flagged Signal formula. Orphan/Ambiguous formulas only apply when dismissing **before** resolution.

**Flagged Signal Suppression Key Rationale:**

Suppression key is **scope-based** (not source_id-based):
- `client_id` + `engagement_id` (nullable) + `source` + `rule_triggered` + `rule_scope` (optional)
- Does NOT include `source_id` by default
- This means: dismissing a flagged signal suppresses future signals of the same pattern for that client/engagement
- Expiry (30 days) allows re-evaluation when detector behavior may have changed

**Optional rule_scope (prevents over-suppression):**

Some rules are instance-specific and should not suppress unrelated instances:

| Rule | rule_scope Value | Effect |
|------|------------------|--------|
| `email_unanswered_48h` | `thread_id` | Dismissing one unanswered thread doesn't suppress other threads |
| `task_overdue` | `asana_project_id` | Dismissing one project's overdue doesn't suppress other projects |
| `meeting_cancelled_short_notice` | `event_id` | Each cancelled meeting is independent |
| (default) | `null` | Pattern-based suppression across all instances |

```python
def flagged_signal_suppression_data(signal, rule_scope_value=None):
    data = {
        'client_id': signal.client_id,
        'engagement_id': signal.engagement_id,
        'source': signal.source,
        'rule_triggered': signal.rule_triggered,
    }
    if rule_scope_value:
        data['rule_scope'] = rule_scope_value  # e.g., thread_id value
    return data
```

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

**Canonical Suppression Key Utility (Required):**

All suppression key computation MUST route through a single utility function. Ad-hoc hashing is forbidden.

```python
def compute_suppression_key(item: InboxItem) -> str:
    """
    Single entry point for all suppression key computation.
    Never compute suppression keys inline — always call this function.
    """
    match item.type:
        case 'issue':
            data = {'issue_type': item.issue.type, 'client_id': item.client_id, 'engagement_id': item.engagement_id}
        case 'flagged_signal':
            data = {'client_id': item.client_id, 'engagement_id': item.engagement_id, 'source': item.signal.source, 'rule_triggered': item.signal.rule_triggered}
        case 'orphan':
            data = {'identifier_type': item.evidence['payload']['raw_identifier']['type'], 'identifier_value': item.evidence['payload']['raw_identifier']['value']}
        case 'ambiguous':
            if item.engagement_id:  # post-select
                pattern = item.signal.rule_triggered or item.signal.signal_type
                data = {'client_id': item.client_id, 'engagement_id': item.engagement_id, 'source': item.signal.source, 'pattern': pattern}
            else:  # pre-select
                data = {'signal_id': item.underlying_signal_id}
    return suppression_key(item.type, data)
```

**Null Engagement Fallback:**

For Issue suppression when `engagement_id IS NULL`:
1. If `brand_id` is present: include `brand_id` instead of `engagement_id`
2. Else: include `root_cause_fingerprint` (hash of evidence structure)

**Hard Requirement:** If `issues.engagement_id IS NULL AND issues.brand_id IS NULL`, then `issues.root_cause_fingerprint` MUST be non-null. Without this, dismiss cannot produce a stable suppression key.

```sql
-- DB constraint to enforce
ALTER TABLE issues ADD CONSTRAINT chk_root_cause_required
  CHECK (
    engagement_id IS NOT NULL
    OR brand_id IS NOT NULL
    OR root_cause_fingerprint IS NOT NULL
  );
```

**root_cause_fingerprint Computation:**

```python
def compute_root_cause_fingerprint(issue) -> str:
    """Deterministic fingerprint for issues without engagement/brand scoping."""
    payload = {
        "issue_type": issue.type,
        "evidence": issue.evidence["payload"]  # includes values, not just keys
    }
    # Canonical JSON: sorted keys, no whitespace
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return "rcf_" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]
```

This avoids collisions across issues with same structure but different content (e.g., different invoice numbers, project GIDs).

Store in `inbox_suppression_rules`:
```sql
CREATE TABLE inbox_suppression_rules (
  id TEXT PRIMARY KEY,
  suppression_key TEXT NOT NULL UNIQUE,
  item_type TEXT NOT NULL,      -- 'issue' | 'flagged_signal' | 'orphan' | 'ambiguous'
  issue_id TEXT REFERENCES issues(id),  -- Set when item_type='issue'; enables deterministic auto-unsuppress
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,              -- NULL = permanent; computed per type below
  reason TEXT
);

-- Primary enforcement index (used by check_suppression)
CREATE INDEX idx_suppression_rules_key_expires ON inbox_suppression_rules(suppression_key, expires_at);
CREATE INDEX idx_suppression_rules_expires ON inbox_suppression_rules(expires_at) WHERE expires_at IS NOT NULL;  -- For cleanup job
CREATE INDEX idx_suppression_rules_issue ON inbox_suppression_rules(issue_id) WHERE issue_id IS NOT NULL;  -- For auto-unsuppress job
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

**Suppression Source of Truth (Authoritative Precedence):**

`inbox_suppression_rules` is the **authoritative source** for suppression enforcement:
- On new inbox item proposal: check `inbox_suppression_rules` (not `inbox_items.suppression_key`)
- `inbox_items.suppression_key` is stored for audit only (preserves what key was used at dismiss time)
- Revoking suppression deletes from `inbox_suppression_rules`; does not modify historical `inbox_items`

**Split-Brain Prevention (Hard Rules):**
- `issues.suppressed` is a **derived flag**, reconciled hourly from rules
- For enforcement: always query `inbox_suppression_rules`
- For health/filtering: use `issues.suppressed` flag (acceptable staleness up to 1 hour)
- **Edge case handling:**
  - Rule exists, `issues.suppressed = false` → next job run will set to true (transient inconsistency OK)
  - Rule expired, `issues.suppressed = true` → next job run will set to false (transient inconsistency OK)
  - Rule deleted (revoked), `issues.suppressed = true` → next job run will set to false
- **Never rely on `issues.suppressed` for proposal blocking** — always query rules table

**Suppression Expiry Enforcement:**

```sql
-- Check if suppressed (ignore expired rules)
SELECT 1 FROM inbox_suppression_rules
WHERE suppression_key = :key
  AND (expires_at IS NULL OR expires_at > :now_iso)
```

**Cleanup (optional):** A daily job may delete expired rules (`DELETE FROM inbox_suppression_rules WHERE expires_at < :now_iso`). Revocation endpoint deletes immediately.

**Issue Auto-Unsuppress Job (Required):**

When suppression rules expire, issues should be automatically unsuppressed to match UI microcopy ("hides for 90 days"):

```sql
-- Run hourly with suppression cleanup
-- Uses issue_id directly from suppression rules (no fragile inbox_items join)
UPDATE issues
SET suppressed = FALSE,
    suppressed_at = NULL,
    suppressed_by = NULL
WHERE suppressed = TRUE
  AND id IN (
    -- Find issues whose suppression rule has expired or been deleted
    SELECT i.id FROM issues i
    LEFT JOIN inbox_suppression_rules r ON r.issue_id = i.id AND r.item_type = 'issue'
    WHERE i.suppressed = TRUE
      AND (r.id IS NULL OR r.expires_at < :now_iso)
  );
```

**Rationale:** Without this job, `issues.suppressed` would remain `TRUE` forever after rule expiry, making the "90 days" UI copy misleading. Users expect issues to resurface after expiry.

**Implementation Note:** The `issue_id` field on `inbox_suppression_rules` enables deterministic auto-unsuppress without relying on historical inbox_items rows. When dismissing an issue, always set `issue_id = underlying_issue.id` on the suppression rule.

**Suppression Invariant Enforcement (Required):**

If `issues.suppressed = TRUE`, a corresponding suppression rule MUST exist. This prevents orphaned suppression flags from direct DB writes or bugs:

```python
# Startup canary — run with timestamp validation
def validate_suppression_consistency():
    """Check that all suppressed issues have corresponding suppression rules."""
    orphaned = query("""
        SELECT i.id FROM issues i
        LEFT JOIN inbox_suppression_rules r
            ON r.issue_id = i.id AND r.item_type = 'issue'
        WHERE i.suppressed = TRUE
          AND r.id IS NULL
    """)
    if orphaned:
        alert(f"CRITICAL: {len(orphaned)} issues suppressed without rules")
        return False
    return True
```

**Alternative (DB Trigger):**
```sql
-- Prevent setting suppressed=TRUE without a rule
CREATE TRIGGER enforce_suppression_rule
BEFORE UPDATE ON issues
FOR EACH ROW
WHEN NEW.suppressed = TRUE AND OLD.suppressed = FALSE
BEGIN
    SELECT RAISE(ABORT, 'Cannot suppress issue without suppression rule')
    WHERE NOT EXISTS (
        SELECT 1 FROM inbox_suppression_rules
        WHERE issue_id = NEW.id AND item_type = 'issue'
    );
END;
```

**Orphan Suppression Key TTL:** Default 180 days for orphans. Consider reducing to 60–90 days if orphans represent engagement discovery opportunities that should resurface sooner.

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
│   └── Returning by tomorrow: 1  ← snooze_until < local_midnight(today + 2)
└── Recently Actioned: 8      ← state IN ('linked_to_issue', 'dismissed') AND resolved_at >= today - 7 days
```

**Count definitions:**
- **Needs Attention:** `COUNT(*) WHERE state = 'proposed'`
- **Snoozed:** `COUNT(*) WHERE state = 'snoozed'`
- **Returning by Tomorrow:** `COUNT(*) WHERE state = 'snoozed' AND snooze_until < local_midnight_utc(org_tz, local_today + 2 days)` (i.e., "resurfaces before end of tomorrow in org timezone")
  - **UI Label:** "Returning by tomorrow"
  - **Boundary clarification:** "by tomorrow" = during today or tomorrow (before midnight ending tomorrow). Uses `today + 2` because `local_midnight_utc(today + 2)` = start of day-after-tomorrow = end of tomorrow.
- **Recently Actioned:** `COUNT(*) WHERE state IN ('linked_to_issue', 'dismissed') AND resolved_at >= window_start(org_tz, 7)`

**Header Window:** Header always uses `days=7` (hardcoded). Uses `window_start(org_tz, 7)` for consistency.

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

**Inclusive/Exclusive Boundaries:**
- **Start:** `>= window_start` (inclusive of midnight N days ago)
- **End:** `< now` (exclusive of current moment) or `<= now` (inclusive) — choose one, be consistent
- **Recommended:** `>= window_start AND resolved_at <= :now_iso` for explicit upper bound
- This means "last 7 days" spans 7 full local days from midnight N days ago through current moment

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
- "Mark as processed" sets `read_at = utc_now_iso_ms_z()` but does NOT change state
- Items remain in "Needs Attention" until actioned (Tag/Assign/Snooze/Dismiss)

**Setting `read_at`:**
- Explicit: `POST /api/inbox/:id/mark_read` (API name preserved for compatibility)
- Bulk: `POST /api/inbox/mark_all_read` (marks all proposed items)
- Implicit: NOT set on view; requires explicit action

**Semantic Clarification:** `read_at` is an **explicit acknowledgment** that the user has seen and mentally processed the item, not a "viewed" timestamp. Clicking into an item to view evidence does NOT set `read_at`. This prevents items from disappearing from the "Unprocessed" filter just because they were glanced at.

**⚠️ Org-Global Read State:** `read_at` is org-global, NOT per-user. When one team member marks an item as processed, it affects all users. This is intentional for shared workflow visibility. If per-user read receipts are needed later, add `inbox_item_reads(inbox_item_id, user_id, read_at)` table.

**Terminal State Behavior:**

`POST /api/inbox/:id/mark_read` on terminal items (`state IN ('dismissed', 'linked_to_issue')`):
- Returns `409 Conflict` with `error: 'invalid_state'`
- Message: "Cannot mark terminal item as read; item already resolved"
- Rationale: Terminal items are in `/api/inbox/recent` (read-only archive); marking as "processed" is meaningless

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
3. Issued totals: Prior Yr, YTD
4. Paid totals: Prior Yr, YTD
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
- Summary shows Issued/Paid for: Prior Yr, YTD, lifetime
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

**Hours Estimation Algorithm (Priority Order):**
1. `asana.estimated_hours` custom field (if populated)
2. `story_points * org.story_point_hours` (default: `story_point_hours = 4`)
3. `complexity_tag` mapping: `{ "trivial": 1, "small": 2, "medium": 4, "large": 8, "xlarge": 16 }`
4. Fallback: `null` (exclude from hours totals, but include in task counts)

```python
def estimate_hours(task, org):
    if task.estimated_hours:
        return task.estimated_hours
    if task.story_points:
        return task.story_points * org.story_point_hours
    if task.complexity_tag:
        return COMPLEXITY_MAP.get(task.complexity_tag)
    return None
```

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

**Canonical Task Definition for Team View:**

| Metric | Task Filter | Notes |
|--------|-------------|-------|
| **Tasks count** | `engagement_id = client engagement` AND `NOT completed` AND `parent IS NULL` | Top-level open tasks only |
| **Overdue count** | Same as above + `due_date < today_local` | Matches engagement health definition |
| **Hours estimated** | All tasks assigned to user for this client (open + completed in window) | Uses estimate algorithm above |

**Alignment with Engagement Health:**
- Team view uses same `parent IS NULL` filter (top-level only)
- Team view uses same `NOT archived` filter (implicit in sync)
- If Engagement says "12 open tasks" and Team says "18 tasks assigned to Sarah", the difference is: Team counts per-user across ALL engagements for this client, Engagement counts all users for ONE engagement

**Subtask Handling:** Subtasks (`parent IS NOT NULL`) are excluded from counts but their hours/story points are rolled up to parent task.

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

**Frontend Routing Guards:**
- `/clients/:id/snapshot` — ALLOW regardless of client status (snapshot is always accessible)
- `/clients/:id` (full detail) — BLOCK for cold clients; redirect to snapshot or show 403
- Implementation: check `client.status` in route guard; cold → redirect to `/clients/:id/snapshot`

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

| Metric | Formula | Use |
|--------|---------|-----|
| AR_outstanding | `SUM(amount) WHERE status IN ('sent', 'overdue')` | Total unpaid |
| AR_overdue_source | `SUM(amount) WHERE status = 'overdue'` | Issues, health penalty, `ar_overdue_pct` |
| AR_overdue_effective | `SUM(amount) WHERE status = 'overdue' OR (status = 'sent' AND is_past_due(due_date, today_local))` | Aging display buckets |
| AR by bucket | `SUM(amount) WHERE status IN ('sent', 'overdue') AND is_past_due(due_date, today_local) GROUP BY aging_bucket` | UI aging bars |

**Note:** `AR_outstanding` is the canonical name for total unpaid. In formulas, `AR_total = AR_outstanding`.

**Two Overdue Metrics (Intentional Split):**
- **`AR_overdue_source`** trusts Xero's `status = 'overdue'` flag. Used for financial issue creation and health penalty calculation. This is the "official" overdue.
- **`AR_overdue_effective`** includes `status_inconsistent` invoices (sent but past due). Used for aging display to show the user what's actually past due date.

**UI Labeling Requirement:**
- Health score tooltip: "Overdue (Xero)" — uses `AR_overdue_source`
- Aging breakdown chart: "Past due (computed)" — uses `AR_overdue_effective`
- If these differ significantly, show a warning: "N invoices past due but not marked overdue in Xero"

---

**AR Aging Buckets (canonical — computed from days_overdue, not status):**

Buckets are computed purely from `days_overdue`, regardless of Xero `status`. This ensures `status_inconsistent` invoices (sent but past due) display in the correct aging bucket.

| Bucket | API Value | Formula |
|--------|-----------|---------|
| Current (not due) | `current` | `status IN ('sent', 'overdue') AND (due_date >= today OR due_date IS NULL)` |
| 1-30 days overdue | `1_30` | `status IN ('sent', 'overdue') AND days_overdue BETWEEN 1 AND 30` |
| 31-60 days overdue | `31_60` | `status IN ('sent', 'overdue') AND days_overdue BETWEEN 31 AND 60` |
| 61-90 days overdue | `61_90` | `status IN ('sent', 'overdue') AND days_overdue BETWEEN 61 AND 90` |
| 90+ days overdue | `90_plus` | `status IN ('sent', 'overdue') AND days_overdue > 90` |

**Bucket Invariant:** All invoices in `AR_outstanding` have exactly one bucket based on computed `days_overdue`. The `current` bucket includes null `due_date` as fallback to ensure AR aging sums correctly.

**Status vs Computed Overdue (Two Concepts):**
- **Bucket assignment:** Uses computed `days_overdue` (date math)
- **AR_overdue_source:** Uses Xero `status = 'overdue'` (for health penalty, issue creation)
- **AR_overdue_effective:** Uses computed `is_past_due(due_date)` (for display totals)

**Data Quality Edge Cases:**

| Condition | Bucket | Flag |
|-----------|--------|------|
| `status = 'sent'` AND `due_date < today` | Computed bucket (e.g., `1_30`) | `flagged_signal: invoice_status_inconsistent` |
| `status = 'sent'` AND `due_date IS NULL` | `current` | `dq_flag: missing_due_date` |
| `status = 'overdue'` AND `due_date IS NULL` | `90_plus` | `dq_flag: missing_due_date` |
| `days_overdue` calculation | — | `MAX(0, today - due_date)` (negative clamped to 0) |

**Invoice Aging Algorithm:**

```python
def compute_invoice_aging(invoice, org_tz):
    """
    Compute aging fields for a single invoice.
    Returns: (days_overdue, aging_bucket, status_inconsistent)
    """
    status = invoice.status
    due_date = invoice.due_date
    today = get_today_local(org_tz)

    # Default values
    days_overdue = 0
    aging_bucket = None
    status_inconsistent = False

    if status == 'overdue':
        if due_date is not None:
            days_overdue = max(0, (today - due_date).days)
            aging_bucket = get_bucket(days_overdue)
        else:
            # Fallback: null due_date on overdue → 90_plus
            aging_bucket = '90_plus'
            days_overdue = None  # Unknown

    elif status == 'sent':
        if due_date is not None:
            if due_date < today:
                # STATUS INCONSISTENT: sent but past due
                days_overdue = max(0, (today - due_date).days)
                aging_bucket = get_bucket(days_overdue)
                status_inconsistent = True
            else:
                # due_date >= today → current (not yet due)
                aging_bucket = 'current'
                days_overdue = 0
        else:
            # Fallback: null due_date on sent → current
            aging_bucket = 'current'
            days_overdue = None  # Unknown

    # paid/voided/draft → return None for all (already excluded from AR)

    return days_overdue, aging_bucket, status_inconsistent


def get_bucket(days):
    """Map days overdue to aging bucket."""
    if days <= 0:
        return 'current'
    elif days <= 30:
        return '1_30'
    elif days <= 60:
        return '31_60'
    elif days <= 90:
        return '61_90'
    else:
        return '90_plus'
```

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
| `invoice_overdue` | xero | Xero `status = 'overdue'` (source-system value; creates financial issue) |
| `invoice_status_inconsistent` | xero | `status = 'sent'` AND `due_date < today` (DQ flagged_signal only; no financial issue) |

**Detector Rule Naming Convention:**
- `invoice_overdue` triggers on **Xero source status**, not date math
- `invoice_status_inconsistent` triggers on **date math** when Xero status is stale
- Financial issues are created ONLY from `invoice_overdue`; `invoice_status_inconsistent` creates a DQ flagged_signal

**Financial Issue Aggregation Threshold:**

`financial_issue_threshold = 1` — A financial issue is created as soon as ONE qualifying overdue invoice exists.

**Financial Issue Aggregation Key (Canonical):**

Since `threshold = 1`, each overdue invoice creates its own issue. The aggregation key is:

```python
financial_issue_key = sha256(
    f"{client_id}:{engagement_id or 'null'}:{invoice_source_id}"
)
```

- `invoice_source_id` is the Xero invoice UUID (not invoice_number)
- One issue per invoice guarantees no collision between invoices with same number
- If aggregation threshold changes (e.g., 3 invoices = 1 issue), key becomes:
  `sha256(f"{client_id}:{engagement_id}:{'|'.join(sorted(invoice_source_ids))}")`

**Invoice Anomaly Precedence (Decision C enforcement):**

When processing invoices in a detector run:
1. If invoice qualifies for financial issue (overdue) → create/update financial issue
2. If a financial issue exists for the invoice → do NOT create `invoice_status_inconsistent` flagged_signal
3. If NO financial issue exists AND `status='sent'` AND `due_date < today` → create `invoice_status_inconsistent` flagged_signal

This prevents duplicate proposals for the same invoice.

**DQ Flagged Signal Superseded Rule:**

When an invoice transitions from `status='sent'` to `status='overdue'` in Xero:
1. Detector creates a financial issue (new or enriched)
2. If a prior `invoice_status_inconsistent` flagged_signal exists for the same `source_id`:
   - Mark the signal as `dismissed = true` with `dismissed_by = 'system'`
   - Set `dismiss_reason = 'superseded_by_financial_issue'`
   - Archive any active inbox item for that signal to `dismissed` with `resolution_reason = 'superseded'`

This prevents duplicate noise in the Signals tab when the DQ signal becomes a real issue.

**Detector Contract — Upsert Invariant (REQUIRED):**
- Detectors MUST upsert by underlying key, never blind insert
- Before creating inbox item, check: `SELECT id FROM inbox_items WHERE underlying_issue_id = ? AND state IN ('proposed', 'snoozed')`
- If exists: update existing row (enrich evidence, set `last_refreshed_at = utc_now_iso_ms_z()`)
- If not exists: insert new row
- Use `INSERT ... ON CONFLICT DO UPDATE` or equivalent atomic operation

This prevents unique constraint violations under concurrent detector runs.

---

**Flagged Signal evidence structure (canonical envelope):**
```json
{
  "version": "v1",
  "kind": "flagged_signal",
  "url": null,
  "display_text": "Quarterly Review cancelled 2h before start",
  "source_system": "calendar",
  "source_id": "event_abc123",
  "payload": {
    "excerpt": "Quarterly Review cancelled 2h before start",
    "timestamp": "2026-01-15T10:00:00.000Z",
    "rule_triggered": "meeting_cancelled_short_notice",
    "rule_params": { "threshold_hours": 24, "actual_hours": 2 }
  }
}
```

**Orphan evidence structure (canonical envelope):**
```json
{
  "version": "v1",
  "kind": "orphan",
  "url": null,
  "display_text": "Task in unlinked project: 1234567890",
  "source_system": "asana",
  "source_id": "1234567890",
  "payload": {
    "raw_identifier": { "type": "asana_gid", "value": "1234567890" },
    "linkage_failure": "no_matching_engagement",
    "attempted_matches": [],
    "source_signal": { "id": "signal_xyz", "type": "task_created" }
  }
}
```

**Ambiguous evidence structure (canonical envelope):**
```json
{
  "version": "v1",
  "kind": "ambiguous",
  "url": null,
  "display_text": "Multiple engagement matches",
  "source_system": "asana",
  "source_id": "signal_xyz",
  "payload": {
    "candidates": [
      { "id": "uuid1", "name": "Project A", "match_type": "invoice_reference_parse", "confidence": 0.85 },
      { "id": "uuid2", "name": "Project B", "match_type": "email_subject_parse", "confidence": 0.60 }
    ],
    "source_signal": { "id": "signal_xyz" },
    "requires_user_selection": true
  }
}
```

**Evidence Envelope Rule:** All evidence everywhere uses the canonical envelope from §6.16. Detector-specific and type-specific fields go under `payload`.

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

**Open states (system):** `detected`, `surfaced`, `snoozed`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`

**Open states (user-visible):** `surfaced`, `snoozed`, `acknowledged`, `addressing`, `awaiting_resolution`, `regressed`
- `detected` is system-only (not surfaced to user yet)

**Closed states (user-visible):** `regression_watch`, `closed`
- `resolved` is internal-only (instantly transitions to `regression_watch`)

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
   - Set `inbox_items.resolved_at = utc_now_iso_ms_z()`
   - Set `inbox_items.resolved_issue_id = issue.id`
   - Set `inbox_items.resolution_reason = 'issue_snoozed_directly'`
   - Rationale: Client page action is the "proposal resolution" — user addressed it directly

2. No active inbox item exists:
   - No inbox action needed; issue snooze proceeds normally

This prevents contradictory UX where issue is snoozed (hidden) but inbox item remains in "Needs Attention".

**Issue Resolved ↔ Inbox Item Behavior:**

When an issue is resolved directly from the client detail page (not via inbox):

1. If an active inbox item exists for this issue (`underlying_issue_id = issue.id` AND `state IN ('proposed', 'snoozed')`):
   - Transition inbox item to `linked_to_issue`
   - Set `inbox_items.resolved_at = utc_now_iso_ms_z()`
   - Set `inbox_items.resolved_issue_id = issue.id`
   - Set `inbox_items.resolution_reason = 'issue_resolved_directly'`

2. No active inbox item exists:
   - No inbox action needed; issue resolve proceeds normally

This mirrors the snooze-direct rule and prevents stale proposals.

**Generalized Rule — Auto-Archive on Non-Actionable Issue Transition:**

Any issue transition that makes the issue non-actionable MUST auto-archive active inbox items wrapping it:

| Issue Transition | resolution_reason | Rationale |
|------------------|-------------------|-----------|
| → `snoozed` | `issue_snoozed_directly` | Issue hidden from user |
| → `regression_watch` (via resolve) | `issue_resolved_directly` | Issue closed |
| `suppressed = true` (via dismiss) | *(handled by inbox dismiss itself)* | Issue suppressed |
| → `closed` | `issue_closed` | Regression watch ended |

**Implementation:** Wrap issue state transitions in a helper that checks for active inbox items and archives them atomically:

```python
def transition_issue_with_inbox_cleanup(issue_id, new_state, actor, reason):
    with db.transaction():
        # 1. Transition issue
        old_state = update_issue_state(issue_id, new_state, actor)

        # 2. Auto-archive any active inbox item for this issue
        if new_state in NON_ACTIONABLE_STATES:
            archive_active_inbox_item(
                underlying_issue_id=issue_id,
                resolution_reason=reason
            )
```

**Suppressed issues:**

Issues with `suppressed = true` are excluded from:
- Health scoring
- Open issues counts
- Inbox surfacing

Suppression does not change the issue state — it's a parallel flag.

Default API behavior: `suppressed = false`. Override with `?include_suppressed=true`.

**UI Treatment for Suppressed Issues:**
- Show pill badge: `[Suppressed]`
- Available actions: `[Unsuppress]` only (disable all other actions)
- Row styling: muted/greyed to indicate inactive state
- Tooltip: "This issue was dismissed and will not affect health until unsuppressed"

**API action gating for suppressed issues:**
```json
{
  "suppressed": true,
  "available_actions": ["unsuppress"]
}
```

**Navigation Path to Suppressed Issues:**

Suppressed issues are effectively "gone" from normal views but must be accessible:
- **Client Detail Page → Issues Tab:** Add filter toggle `[Show Suppressed]` (off by default)
- **API:** `GET /api/clients/:id/issues?include_suppressed=true`
- **Admin View:** Global suppressed issues list (optional, for ops debugging)

This ensures users can find and unsuppress issues when needed.

**Navigation Path to Snoozed Issues:**

Snoozed issues are excluded from health and open counts but still exist:
- **Client Detail Page → Issues Tab:** Add filter toggle `[Show Snoozed]` (off by default)
- **API:** `GET /api/clients/:id/issues?include_snoozed=true` or `?state=snoozed`
- Without this toggle, snoozed issues feel "invisible" and users may confuse snooze with dismiss

**Suppressed Issues + New Evidence:**

When a suppressed issue receives new evidence (detector enrichment):
- Evidence is appended silently (no resurface, no inbox item)
- Issue remains suppressed until user unsuppresses
- **Exception:** If new evidence has a different aggregation key (new invoice source_id, new root_cause_fingerprint), a **new issue** is created (not a re-enrichment of the suppressed one)
- Suppression is sticky to the original issue identity, not to the underlying problem category

This prevents both over-suppression (hiding new problems) and under-suppression (re-surfacing the same dismissed issue).

---

**Issue Transition Audit Trail (Required):**

All issue state transitions must be logged to `issue_transitions`:

```sql
CREATE TABLE issue_transitions (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL REFERENCES issues(id),
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL,
  transition_reason TEXT NOT NULL,   -- 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation', 'system_workflow'
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

1. Query: `SELECT * FROM issues WHERE state = 'snoozed' AND snoozed_until <= :now_iso`
2. For each expired issue:
   - Update `issues.state = 'surfaced'`
   - Clear snooze fields: `snoozed_until = NULL`, `snoozed_by = NULL`, `snoozed_at = NULL`
   - Insert transition row with `:now_iso` from app layer

**Idempotency Requirement:** Job must be safe for concurrent execution. Use `SELECT ... FOR UPDATE SKIP LOCKED` or optimistic locking to prevent race conditions between job instances or user actions.
     ```sql
     INSERT INTO issue_transitions (
       id, issue_id, previous_state, new_state,
       transition_reason, trigger_rule, actor, transitioned_at
     ) VALUES (
       uuid(), issue.id, 'snoozed', 'surfaced',
       'system_timer', 'snooze_expired', 'system', :now_iso
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

    # Gating check 3: explicit guard for empty linked set
    if linked_open_tasks == 0:
        # No linked tasks to evaluate — engagement is "clear"
        return 100, "no_linked_open_tasks"

    # Health calculation uses linked open tasks (safe: linked_open_tasks > 0)
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

**UX Note on "no_tasks" gating:** Engagements with 0 open tasks show health as N/A. This is intentional:
- Health scoring is only meaningful when there's active work to evaluate
- Completed/winding-down engagements naturally show N/A

**State-Based Override (Reduces N/A Noise):**

For engagements in `delivering` or `delivered` state with 0 open tasks:
- Check if there were completed tasks in the last 7 days
- If yes: treat as "recently active" and show health = 100 with label "Clear" (not N/A)
- If no: show N/A as before

```python
def engagement_health_with_state_override(engagement):
    # Standard health calculation
    score, gating_reason = engagement_health(engagement)

    if gating_reason == "no_tasks" and engagement.state in ('delivering', 'delivered'):
        # Check for recent activity
        recent_completions = count(
            tasks WHERE engagement_id = engagement.id
            AND completed = TRUE
            AND completed_at >= window_start(org_tz, 7)
        )
        if recent_completions > 0:
            return 100, "recently_cleared"

    return score, gating_reason
```

**Required UI Copy:**

| Gating Reason | UI Display | Tooltip |
|---------------|------------|---------|
| `recently_cleared` | "100" (green) | "All tasks complete in last 7 days" |

**Required UI Copy for Health N/A:**

| Gating Reason | UI Display | Tooltip |
|---------------|------------|---------|
| `no_tasks` | "N/A" (grey) | "Health is computed only when there is active open work" |
| `task_linking_incomplete` | "N/A" (grey) | "Health pending: task linking below 90% coverage" |
| `no_linked_open_tasks` | Score=100 (green) | "All linked tasks complete" |

**Product Expectation:** Engagements in `delivering`/`delivered` state often have 0 open tasks and will show N/A. This is expected behavior, not a bug.
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
  transition_reason TEXT NOT NULL,  -- 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation', 'system_workflow'
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

**When client_id is NULL (orphan/ambiguous):**
- Related signals = only those linked to the same underlying signal/issue (no client join)
- For ambiguous with tentative client: use tentative client_id for related signals query

This view is read-only except for issue actions. It provides enough context to decide on the issue without navigating away.

---

### 6.10 Xero Linking (Canonical Rule)

**Xero does not provide public deep links.** Authenticated URLs require user login and are not reliably stable.

**Canonical behavior (everywhere):**
- Display: `INV-1234 (open in Xero)` — plain text, no arrow, no link
- Interaction: User copies invoice number manually
- Never render `↗` or `href` for Xero references

**Invoice Identity (Canonical):**
```
invoice_identity = (source_system='xero', source_id)
```
- `source_id` (Xero invoice UUID) is the **primary identity key**
- `invoice_number` is **display-only** — may collide in rare multi-tenant edge cases
- All deduplication, suppression, and uniqueness checks use `source_id`

**Xero URL Invariant (Scope: All Fields, Not Just Evidence):**
- **Scope:** This invariant applies to ALL Xero-related data, not just evidence payloads
- **invoices table:** Do NOT store `xero_url` or any URL field. If upstream API provides URLs, discard them at ingestion.
- **evidence fields:** For `source_system = 'xero'`, set `evidence.url = null` at ingestion time
- **Server-side enforcement:** If ingestion receives non-null URL for Xero anywhere, overwrite to `null`
- **Recursive URL stripping:** Scan entire evidence structure recursively for URLs
- Frontend EvidenceRenderer is defense-in-depth; server ensures data invariant
- Never store Xero URLs — prevents accidental rendering by generic components

**Rationale:** Xero authenticated URLs are unstable and require login. Storing them anywhere creates false expectations. Ban them entirely rather than relying on renderer-level filtering.

```python
import re

URL_PATTERN = re.compile(r'^https?://', re.IGNORECASE)
URL_KEY_PATTERN = re.compile(r'(url|link|href|uri)', re.IGNORECASE)

def sanitize_xero_evidence(evidence: dict) -> dict:
    """Recursively strip all URLs from Xero evidence."""
    if evidence.get('source_system') != 'xero':
        return evidence

    evidence['url'] = None

    def strip_urls_recursive(obj):
        """Recursively nullify URL keys and URL-like string values."""
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                # Nullify keys that look like URL fields
                if URL_KEY_PATTERN.search(key):
                    obj[key] = None
                else:
                    # Recursively process nested structures
                    obj[key] = strip_urls_recursive(obj[key])
            return obj
        elif isinstance(obj, list):
            return [strip_urls_recursive(item) for item in obj]
        elif isinstance(obj, str):
            # Nullify string values that are URLs
            if URL_PATTERN.match(obj):
                return None
            return obj
        else:
            return obj

    if 'payload' in evidence:
        evidence['payload'] = strip_urls_recursive(evidence['payload'])

    return evidence
```

This catches: nested dicts, arrays of objects, deep keys without "url" in name, and string values that are URLs.

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
  proposed_at TEXT NOT NULL,              -- when item first surfaced (constant)
  last_refreshed_at TEXT NOT NULL,        -- last detector upsert time (updated on evidence enrichment)
  read_at TEXT,                           -- when user explicitly acknowledged item (null if unprocessed); NOT set on view
  resurfaced_at TEXT,                     -- when item last resurfaced from snooze (null if never snoozed)
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
  resolution_reason TEXT,  -- 'tag', 'assign', 'issue_snoozed_directly' — for audit clarity

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
-- NOTE: suppression_key on inbox_items is AUDIT ONLY
-- ⚠️ NEVER use inbox_items.suppression_key for enforcement
-- Enforcement MUST query inbox_suppression_rules table
CREATE INDEX idx_inbox_items_suppression ON inbox_items(suppression_key);  -- For audit queries only

-- Integrity constraints
ALTER TABLE inbox_items ADD CONSTRAINT chk_underlying_exclusive
  CHECK (
    (underlying_issue_id IS NOT NULL AND underlying_signal_id IS NULL)
    OR
    (underlying_issue_id IS NULL AND underlying_signal_id IS NOT NULL)
  );  -- Portable XOR: exactly one underlying entity

-- Type ↔ underlying mapping constraints
ALTER TABLE inbox_items ADD CONSTRAINT chk_type_issue_mapping
  CHECK (type != 'issue' OR (underlying_issue_id IS NOT NULL AND underlying_signal_id IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_type_signal_mapping
  CHECK (type NOT IN ('flagged_signal', 'orphan', 'ambiguous') OR (underlying_signal_id IS NOT NULL AND underlying_issue_id IS NULL));

-- Forward constraints (state requires fields)
ALTER TABLE inbox_items ADD CONSTRAINT chk_snooze_requires_until
  CHECK (state != 'snoozed' OR snooze_until IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_dismissed_requires_key
  CHECK (state != 'dismissed' OR suppression_key IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_terminal_requires_resolved
  CHECK (state NOT IN ('dismissed', 'linked_to_issue') OR resolved_at IS NOT NULL);

-- Inverse constraints (non-state clears fields) — prevents stale data
ALTER TABLE inbox_items ADD CONSTRAINT chk_not_snoozed_clears_snooze
  CHECK (state = 'snoozed' OR (snooze_until IS NULL AND snoozed_at IS NULL AND snoozed_by IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_not_dismissed_clears_dismiss
  CHECK (state = 'dismissed' OR (dismissed_at IS NULL AND dismissed_by IS NULL AND suppression_key IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_not_linked_clears_resolution
  CHECK (state = 'linked_to_issue' OR (resolved_issue_id IS NULL AND resolution_reason IS NULL));

ALTER TABLE inbox_items ADD CONSTRAINT chk_linked_requires_issue
  CHECK (state != 'linked_to_issue' OR resolved_issue_id IS NOT NULL);

-- For issue-wrapping inbox items, resolved_issue_id must match underlying_issue_id
ALTER TABLE inbox_items ADD CONSTRAINT chk_issue_link_consistency
  CHECK (
    type != 'issue'
    OR state != 'linked_to_issue'
    OR resolved_issue_id = underlying_issue_id
  );

ALTER TABLE inbox_items ADD CONSTRAINT chk_linked_requires_reason
  CHECK (state != 'linked_to_issue' OR resolution_reason IS NOT NULL);

ALTER TABLE inbox_items ADD CONSTRAINT chk_dismissed_requires_audit
  CHECK (state != 'dismissed' OR (dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL));

-- Enum constraints (prevent typos)
ALTER TABLE inbox_items ADD CONSTRAINT chk_type_enum
  CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous'));

ALTER TABLE inbox_items ADD CONSTRAINT chk_state_enum
  CHECK (state IN ('proposed', 'snoozed', 'dismissed', 'linked_to_issue'));

ALTER TABLE inbox_items ADD CONSTRAINT chk_severity_enum
  CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info'));

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
- `proposed_at` remains constant (first surfaced time) — **immutable after creation**
- `last_refreshed_at` updated on each detector upsert (latest evidence refresh)

**Proposed_at Immutability (App-Layer Invariant):**
- All inbox item update paths MUST NOT modify `proposed_at`
- Validation: `if existing.proposed_at != update.proposed_at: reject("proposed_at is immutable")`
- DB trigger alternative: `CREATE TRIGGER prevent_proposed_at_change BEFORE UPDATE ON inbox_items FOR EACH ROW WHEN OLD.proposed_at != NEW.proposed_at BEGIN SELECT RAISE(ABORT, 'proposed_at is immutable'); END;`

**Note on snooze_until future enforcement:** DB CHECK constraint cannot validate "future" when using TEXT timestamps. Enforce at application layer: reject snooze requests where `snooze_until <= utc_now_iso_ms_z()`.

**Scoping Consistency Validation (Required):**

All inbox write paths (detectors, user actions, cron jobs) MUST call:

```python
def validate_inbox_item_scoping(inbox_item, underlying_entity):
    """Validate scoping consistency between inbox item and underlying entity."""
    if inbox_item.type == 'issue':
        assert inbox_item.client_id == underlying_entity.client_id
        assert inbox_item.brand_id == underlying_entity.brand_id
        assert inbox_item.engagement_id == underlying_entity.engagement_id
    elif inbox_item.type in ('flagged_signal', 'orphan', 'ambiguous'):
        # Signal scoping may be null for orphans; consistency means matching signal state
        assert inbox_item.client_id == underlying_entity.client_id
        assert inbox_item.engagement_id == underlying_entity.engagement_id
```

For `type = 'issue'` inbox items:
- `client_id`, `brand_id`, `engagement_id` MUST equal the underlying issue's scoping fields

For signal-based inbox items:
- Scoping reflects current signal scoping after any resolution (e.g., after "select" on ambiguous)

---

### 6.14 Issues Schema (Canonical)

```sql
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                     -- 'financial' | 'schedule_delivery' | 'communication' | 'risk'
  state TEXT NOT NULL DEFAULT 'detected', -- 10 states per 6.5 (note: 'resolved' is never persisted)
  severity TEXT NOT NULL,                 -- 'critical' | 'high' | 'medium' | 'low' | 'info'

  -- Aggregation (required for detector upsert — see §6.14.1)
  aggregation_key TEXT NOT NULL,          -- deterministic hash for dedup/upsert

  -- Scoping
  client_id TEXT NOT NULL REFERENCES clients(id),
  brand_id TEXT REFERENCES brands(id),
  engagement_id TEXT REFERENCES engagements(id),

  -- Core fields
  title TEXT NOT NULL,
  evidence JSON NOT NULL,
  evidence_version TEXT NOT NULL DEFAULT 'v1',
  root_cause_fingerprint TEXT,            -- deterministic hash for suppression fallback (see §1.8)

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

  -- Resolution/Regression (set on resolve action)
  resolved_at TEXT,                       -- when user resolved (triggers regression_watch)
  resolved_by TEXT REFERENCES users(id),
  regression_watch_until TEXT,            -- resolved_at + 90 days; timer job checks this
  closed_at TEXT,                         -- when regression_watch ended without recurrence

  -- Timestamps
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_issues_client ON issues(client_id);
CREATE INDEX idx_issues_state ON issues(state);
CREATE INDEX idx_issues_type ON issues(type);
CREATE INDEX idx_issues_severity ON issues(severity);

-- Aggregation key uniqueness: at most one non-suppressed issue per type+key
CREATE UNIQUE INDEX idx_issues_aggregation_unique
  ON issues (type, aggregation_key)
  WHERE suppressed = FALSE;

-- Hard invariant: resolved is never persisted (see §6.5)
ALTER TABLE issues ADD CONSTRAINT chk_no_resolved_state
  CHECK (state != 'resolved');
```

**tagged_* preservation rule:** If issue is already tagged (`tagged_by_user_id IS NOT NULL`) and then assigned, do NOT overwrite `tagged_by_user_id` or `tagged_at`. Preserve first user confirmation. Only set `assigned_*` fields.

**Severity Derivation (v1 heuristics):**

**Financial Issue Severity Scope:**
- Since `threshold = 1`, each overdue invoice creates its own issue
- **Invoice-level severity:** Based on that invoice's `days_overdue` and `amount`
- **Client-level override:** If client total overdue > threshold, bump all client's financial issues to at least `high`
- "Total overdue" = SUM of all overdue invoice amounts for the same client

| Issue Type | Severity | Condition |
|------------|----------|-----------|
| financial | critical | Invoice 45+ days overdue OR invoice amount > AED 50k OR client total overdue > AED 100k |
| financial | high | Invoice 30-44 days overdue OR invoice amount > AED 25k OR client total overdue > AED 50k |
| financial | medium | Invoice 15-29 days overdue |
| financial | low | Invoice 1-14 days overdue |
| schedule_delivery | critical | 5+ tasks overdue by 7+ days |
| schedule_delivery | high | 3+ tasks overdue OR any task 5+ days overdue |
| schedule_delivery | medium | 1-2 tasks overdue by 1-4 days |
| communication | high | 3+ negative signals in 7 days OR escalation keyword |
| communication | medium | 2 negative signals in 7 days |
| communication | low | 1 negative signal |
| risk | varies | Manual assignment or detector-specific rules |

**Inbox Item Severity Derivation:**

| Inbox Type | Severity Rule |
|------------|---------------|
| `issue` | `inbox_items.severity = issues.severity` (denormalized snapshot at upsert) |
| `flagged_signal` | Default `medium`; elevate to `high` for platinum/gold tier clients or escalation rules |
| `orphan` | Default `info`; elevate to `medium` if it blocks task linking coverage (engagement health gating) |
| `ambiguous` | Default `low`; elevate to `medium` if top candidate confidence < 0.5 (high uncertainty) |

**Aggregation Contract per Issue Type:**

| Issue Type | window_days | threshold | aggregation_key | dedupe_policy |
|------------|-------------|-----------|-----------------|---------------|
| `financial` | N/A (per invoice) | 1 | `sha256(client_id:engagement_id:invoice_source_id)` | One issue per invoice |
| `schedule_delivery` | 7 | 3 signals | `sha256(client_id:engagement_id)` | One issue per engagement |
| `communication` | 7 | 2 signals | `sha256(client_id:brand_id)` | One issue per brand |
| `risk` | 30 | 1 signal | `sha256(client_id:engagement_id:rule_triggered)` | One issue per rule per engagement |

**Regression Policy (all types):** 90-day watch; recurrence = same aggregation_key with new signal_id.

---

### 6.14.1 Aggregation Key Computation

Each issue type has a deterministic aggregation key. Detectors MUST upsert by this key.

**Canonical Computation:**

```python
def compute_aggregation_key(issue_type: str, scoping: dict) -> str:
    """Canonical aggregation key. Detectors MUST use this function."""
    match issue_type:
        case 'financial':
            payload = f"financial:{scoping['client_id']}:{scoping.get('engagement_id', '')}:{scoping['invoice_source_id']}"
        case 'schedule_delivery':
            payload = f"schedule:{scoping['client_id']}:{scoping.get('engagement_id', '')}"
        case 'communication':
            payload = f"comm:{scoping['client_id']}:{scoping.get('brand_id', '')}"
        case 'risk':
            payload = f"risk:{scoping['client_id']}:{scoping.get('engagement_id', '')}:{scoping['rule_triggered']}"
    return "agg_" + hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]
```

**Detector Upsert Behavior:**

When a detector finds a match for an existing `aggregation_key`:
1. Append new signals to `issue_signals`
2. Update `evidence` with merged/refreshed data
3. Update `updated_at = utc_now_iso_ms_z()`
4. Recalculate severity (may escalate)
5. **Do NOT create a new issue**

When no match exists:
1. Create new issue with computed `aggregation_key`

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

**Summary vs Evidence Display (Canonical Rendering):**

Two human-text fields exist; use them consistently:
- **`signals.summary`** — Primary text for list rows and cards
- **`evidence.display_text`** — Proof label (e.g., "INV-1234 · AED 35,000") for evidence links

UI rendering rule:
- List/card: show `summary` as main text
- Evidence section: use `display_text` for clickable link labels
- Do NOT duplicate `summary` in `evidence.display_text`

**Signal Scoping Contract:**

| Scoping State | client_id | brand_id | engagement_id | Inbox Item Type |
|---------------|-----------|----------|---------------|-----------------|
| Fully resolved | ✅ Set | ✅ Set (if applicable) | ✅ Set | `issue` or `flagged_signal` |
| Client-only | ✅ Set | ❌ NULL | ❌ NULL | `flagged_signal` |
| Orphan | ❌ NULL | ❌ NULL | ❌ NULL | `orphan` |
| Ambiguous | ✅ Set (tentative) | ❌ NULL | ❌ NULL | `ambiguous` |

**Display when client_id is NULL:**
- Inbox card shows: "Unknown client" + source system identity (e.g., "Asana project GID: 1234567890")
- This only occurs for `orphan` type items
- Orphans require user action (Link/Create) before client scoping is resolved

---

### 6.16 Evidence Meta-Schema (Canonical)

All evidence fields (issues, signals, inbox_items) follow this standardized envelope:

```json
{
  "version": "v1",
  "kind": "invoice|asana_task|gmail_thread|calendar_event|meet_event|minutes_analysis|gchat_message|xero_contact",
  "url": "https://...",                    // nullable (null for minutes, xero)
  "display_text": "INV-1234 · AED 35,000", // REQUIRED — never null, never empty
  "source_system": "xero",                 // source identifier (MUST be canonical)
  "source_id": "inv_abc123",               // unique ID in source
  "payload": {
    // Kind-specific fields
  }
}

**display_text Required (Hard Invariant):**
- `display_text` is REQUIRED on all evidence across issues, signals, and inbox_items
- Reject at ingestion if null, empty, or missing
- Fallback formula by kind:
  - `invoice`: `"{number} · {currency} {amount}"`
  - `asana_task`: `"{name}"`
  - `gmail_thread`: `"Email thread · {subject}"`
  - `calendar_event`: `"{title} · {start_time}"`
  - `minutes_analysis`: `"{meeting_title} · {meeting_platform}"`
  - `gchat_message`: `"Chat message · {sender}"`
- Detectors MUST compute `display_text` explicitly; no "optional" treatment
```

**Evidence Source System (Hard Invariant):**
- `source_system` MUST be one of: `asana`, `gmail`, `gchat`, `calendar`, `meet`, `minutes`, `xero`, `system`
- Must match the context of the parent entity (signal source, issue type, etc.)
- Validation: reject ingestion if `source_system` not in canonical list

**Payload URL Validation:**
- `payload.recording_url` and `payload.transcript_url` must be valid URLs if present (non-empty, https scheme)
- Reject at ingestion if malformed

**Kind-specific payload examples:**

| Kind | Payload Fields |
|------|----------------|
| `invoice` | `number`, `amount`, `currency`, `due_date`, `days_overdue`, `status` |
| `asana_task` | `task_gid`, `name`, `assignee`, `due_date`, `days_overdue`, `project_name` |
| `gmail_thread` | `thread_id`, `subject`, `sender`, `snippet`, `received_at` |
| `calendar_event` | `event_id`, `title`, `start_time`, `cancelled`, `rescheduled` |
| `minutes_analysis` | `meeting_id`, `meeting_title`, `meeting_platform`, `analysis_provider`, `key_points`, `sentiment_summary`, `recording_url` (nullable), `transcript_url` (nullable) |
| `meet_event` | `event_id`, `title`, `start_time`, `duration_minutes`, `participant_count`, `organizer` |
| `gchat_message` | `space_id`, `message_id`, `sender`, `snippet`, `keywords_detected` |

**JSON Schema Validation (Implementation Requirement):**
- Maintain one JSON Schema file per `kind` value (e.g., `evidence.invoice.schema.json`)
- Validate evidence on ingestion against appropriate schema
- EvidenceRenderer component MUST use `kind` + `source_system` switch; no generic "if url then link" logic
- Detectors populate only `payload` + required top-level fields; never invent new top-level keys

**Evidence Render Matrix (by kind + source_system):**

| kind | source_system | Top-level `url` | Payload URLs | Render Action |
|------|---------------|-----------------|--------------|---------------|
| `asana_task` | `asana` | Use if present | — | `[View in Asana ↗]` linked to `url` |
| `gmail_thread` | `gmail` | Use if present | — | `[View Thread ↗]` linked to `url` |
| `gchat_message` | `gchat` | Use if present | — | `[View in Chat ↗]` linked to `url` |
| `calendar_event` | `calendar` | Use if present | — | `[View Event ↗]` linked to `url` |
| `invoice` | `xero` | **Always null** | **Strip all** | Plain text: `INV-1234 (open in Xero)` — no link ever |
| `xero_contact` | `xero` | **Always null** | **Strip all** | Plain text only |
| `minutes_analysis` | `minutes` | **Always null** | `recording_url`, `transcript_url` | Render buttons only if payload URLs exist: `[View Recording ↗]` `[View Transcript ↗]` |
| `meet_event` | `meet` | Ignore | — | No link (recordings may be inaccessible) |

**Render Rules:**
1. **xero**: NEVER render any link, even if URLs exist (should be stripped server-side)
2. **minutes**: Ignore top-level `url`; use only `payload.recording_url` and `payload.transcript_url`
3. **gmail/gchat/calendar/asana**: Render link only if `url` is non-null and non-empty
4. **meet**: Do not render links (accessibility issues)

**Canonical EvidenceRenderer Component (Required):**

All evidence rendering MUST route through a single component. Generic "if url then link" logic is forbidden elsewhere.

```typescript
function EvidenceRenderer({ evidence }: { evidence: Evidence }) {
  const { source_system, url, payload, display_text } = evidence;

  switch (source_system) {
    case 'xero':
      // NEVER render link, even if url is present
      return <span>{display_text} (open in Xero)</span>;

    case 'minutes':
      // evidence.url is always null; check payload URLs
      return (
        <div>
          <span>{display_text}</span>
          {payload.recording_url && <Link href={payload.recording_url}>View Recording ↗</Link>}
          {payload.transcript_url && <Link href={payload.transcript_url}>View Transcript ↗</Link>}
        </div>
      );

    case 'asana':
    case 'gmail':
    case 'gchat':
    case 'calendar':
      // Render link if url present
      return url ? <Link href={url}>{display_text} ↗</Link> : <span>{display_text}</span>;

    case 'meet':
      // Do not render links (accessibility issues)
      return <span>{display_text}</span>;

    default:
      return <span>{display_text}</span>;
  }
}
```

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

### 6.19 Detector Window Boundaries (Canonical)

All detectors using `window_days` parameters MUST use org-local day boundaries, NOT rolling 24-hour windows.

**Canonical Window Computation:**

```python
def detector_window_start(org_tz: str, window_days: int) -> datetime:
    """
    Returns UTC timestamp for start of detection window.
    Uses org-local midnight boundaries, consistent with all other date logic.
    """
    local_today = datetime.now(ZoneInfo(org_tz)).date()
    window_start_date = local_today - timedelta(days=window_days)
    return local_midnight_utc(org_tz, window_start_date)

def detector_window_end(org_tz: str) -> datetime:
    """Returns current UTC timestamp (inclusive end)."""
    return datetime.now(UTC)
```

**Window Query Pattern:**

```sql
SELECT * FROM signals
WHERE observed_at >= :window_start
  AND observed_at <= :window_end
  AND client_id = :client_id
```

**Invariants:**
- `window_start` is always at org-local midnight N days ago
- `window_end` is current time (request-scoped)
- Signals near midnight boundary are included based on `observed_at` (source system time)
- Ingestion delays do not affect window membership — use `observed_at`, not `ingested_at`

**Application to Issue Types:**

| Issue Type | window_days | Window Start |
|------------|-------------|--------------|
| `schedule_delivery` | 7 | `local_midnight_utc(org_tz, today - 7)` |
| `communication` | 7 | `local_midnight_utc(org_tz, today - 7)` |
| `risk` | 30 | `local_midnight_utc(org_tz, today - 30)` |
| `financial` | N/A (per invoice) | N/A |

---

## 7. Minimum API Endpoints

### 7.1 Client Index

```
GET /api/clients
  ?status=active|recently_active|cold|all    (default: all)
  &tier=platinum|gold|silver|bronze|none     (optional filter)
  &has_issues=true|false                     (optional filter)
  &has_overdue_ar=true|false                 (optional filter)
  &sort=ar_overdue|last_invoice|name         (default: ar_overdue for active)
  &order=asc|desc                            (default: desc)
  &page=1                                    (default: 1)
  &limit=20                                  (default: 20, max: 100)
```

**Response Contract:**

```typescript
interface ClientIndexResponse {
  active: ActiveClientCard[];
  recently_active: RecentlyActiveClientCard[];
  cold: ColdClientCard[];
  counts: {
    active: number;
    recently_active: number;
    cold: number;
  };
}

interface ActiveClientCard {
  id: string;
  name: string;
  tier: "platinum" | "gold" | "silver" | "bronze" | "none";
  status: "active";
  health_score: number;              // 0-100
  health_label: "provisional";       // Always provisional in v1
  issued_ytd: number;
  issued_prior_year: number;
  paid_ytd: number;
  paid_prior_year: number;
  ar_outstanding: number;            // Total unpaid (sent + overdue)
  ar_overdue: number;                // Total overdue
  ar_overdue_pct: number;            // Round to nearest integer
  open_issues_high_critical: number; // Count of high/critical Open Actionable Issues
  last_invoice_date: string | null;  // ISO date
  first_invoice_date: string | null;
}

interface RecentlyActiveClientCard {
  id: string;
  name: string;
  tier: "platinum" | "gold" | "silver" | "bronze" | "none";
  status: "recently_active";
  issued_last_12m: number;
  issued_prev_12m: number;
  paid_last_12m: number;
  paid_prev_12m: number;
  issued_lifetime: number;
  paid_lifetime: number;
  last_invoice_date: string | null;
}

interface ColdClientCard {
  id: string;
  name: string;
  tier: "platinum" | "gold" | "silver" | "bronze" | "none";
  status: "cold";
  issued_lifetime: number;
  paid_lifetime: number;
  last_invoice_date: string | null;
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
- Forbidden section for status: returns 403 (no union payload on error)

**All-or-Nothing Behavior:** If ANY requested include section is forbidden for the client's status, the entire request returns 403. No partial success. Example: `?include=overview,signals` for `recently_active` client returns 403 because `signals` is forbidden, even though `overview` might be allowed.

**included_sections Response Field (Required):**

Every response MUST include an `included_sections` array listing which sections are present:

```json
{
  "id": "uuid",
  "name": "Client Name",
  "status": "active",
  "tier": "gold",
  "included_sections": ["overview", "financials"],  // Explicit list
  "overview": { ... },
  "financials": { ... },
  "engagements": null,  // Not requested
  "signals": null,      // Not requested
  "team": null          // Not requested
}
```

**Rationale:** Prevents ambiguity when debugging. Frontend can check `included_sections` to distinguish "not requested" (`null`) from "requested but empty" (`{}`). Eliminates "counts mismatch" bugs from assuming a field exists.

**Include Policy Matrix:**

| Client Status | Allowed Includes | Forbidden Includes |
|---------------|------------------|-------------------|
| `active` | `overview`, `engagements`, `financials`, `signals`, `team` | none |
| `recently_active` | `financials`, `brands`, `last_invoices` | `overview`, `engagements`, `signals`, `team`, `health` |
| `cold` | `financials` | all others |

**Error Responses:**

```typescript
// 403 Forbidden - attempting forbidden include
{
  "error": "forbidden_section",
  "message": "Cannot include 'signals' for recently_active client",
  "allowed_includes": ["financials", "brands", "last_invoices"]
}

// 400 Bad Request - empty or unknown include
{
  "error": "invalid_include",
  "message": "Include parameter cannot be empty"
}
```

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

**Response Contract:**

```typescript
interface ClientSnapshotResponse {
  id: string;
  name: string;
  status: "active" | "recently_active" | "cold";
  issued_lifetime: number;
  paid_lifetime: number;
  last_invoice_date: string | null;
  first_invoice_date: string | null;
  context: {
    source: "inbox_item" | "issue";
    inbox_item?: InboxItemContext;    // Present if source = inbox_item
    issue?: IssueContext;             // Present if source = issue OR inbox linked
  };
  related_signals: SignalSummary[];   // Max 5, last 90 days
}
```

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
      "status_inconsistent": false    // true if sent but due_date < today
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 10
}
```

**Invoice Aging Computation (Deterministic):**

| status | Condition | days_overdue | aging_bucket | status_inconsistent | dq_flag |
|--------|-----------|--------------|--------------|---------------------|---------|
| `overdue` | due_date not null | `max(0, today - due_date)` | Computed from days_overdue | false | — |
| `overdue` | due_date null | null | `90_plus` (fallback) | false | `missing_due_date` |
| `sent` | due_date >= today | null | `current` | false | — |
| `sent` | due_date < today | `max(0, today - due_date)` | Computed from days_overdue | **true** | — |
| `sent` | due_date null | null | `current` (fallback) | false | `missing_due_date` |
| `paid`/`voided`/`draft` | any | null | null | false | — |

**Key:** `status` field is never mutated; it reflects source system (Xero) value. `status_inconsistent=true` signals a data quality issue.

**AR Aging Invariant:** All invoices in `AR_outstanding` (status = 'sent' or 'overdue') MUST have a non-null `aging_bucket`. The `current` fallback for `sent + null due_date` ensures AR aging buckets sum to `total_outstanding`. Invoices with `dq_flag = 'missing_due_date'` should be surfaced as a data quality flagged_signal.

**Response Contracts:**

```typescript
interface ARAgingResponse {
  total_outstanding: number;
  buckets: ARBucket[];
}

interface ARBucket {
  bucket: "current" | "1_30" | "31_60" | "61_90" | "90_plus";
  amount: number;
  pct: number;  // Rounded to nearest integer
}

interface InvoicesResponse {
  invoices: Invoice[];
  total: number;
  page: number;
  limit: number;
}

interface Invoice {
  id: string;
  number: string;
  issue_date: string;              // ISO date
  due_date: string | null;         // ISO date, nullable
  amount: number;
  status: "draft" | "sent" | "overdue" | "paid" | "voided";
  days_overdue: number | null;     // 0 if not overdue; null if due_date missing
  aging_bucket: string | null;     // Server-computed
  status_inconsistent: boolean;    // true if sent but due_date < today
}
```

---

### 7.6 Issues

```
GET /api/clients/:id/issues
  ?state=surfaced|snoozed|acknowledged|addressing|awaiting_resolution|regression_watch|closed|regressed|all_open|all_closed|all
  // Note: 'detected' is internal (admin-only); 'resolved' is non-observable (use regression_watch)
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
      "created_at": "2026-01-10T10:00:00.000Z",
      "available_actions": ["acknowledge", "snooze", "resolve"]  // State-dependent
    }
  ],
  "counts": {...}
}
```

**available_actions Computation Order:**

1. **First check `suppressed`:** If `suppressed = true` → return `["unsuppress"]` (bypass state machine)
2. **Then check state:** Use state-based table below

**available_actions by state:**

| Issue State | Available Actions |
|-------------|-------------------|
| `suppressed = true` | `["unsuppress"]` *(supersedes state)* |
| `surfaced` | `["acknowledge", "snooze", "resolve"]` |
| `acknowledged` | `["assign", "snooze", "resolve"]` |
| `addressing` | `["snooze", "resolve", "escalate"]` |
| `awaiting_resolution` | `["resolve", "escalate"]` |
| `snoozed` | `["unsnooze"]` |
| `resolved` | *(internal-only — never returned by API; use regression_watch)* |
| `regression_watch` | `[]` |
| `closed` | `[]` |
| `regressed` | `["acknowledge", "snooze", "resolve"]` (same as surfaced) |

```
```

**State filters:**
- `all_open`: surfaced, snoozed (if include_snoozed), acknowledged, addressing, awaiting_resolution, regressed
  - **Note:** `detected` is excluded from `all_open` by default (not yet visible to user)
  - Use `?state=detected` explicitly to query pre-surfaced issues (internal/admin use)
- `all_closed`: regression_watch, closed (note: `resolved` is internal-only, never returned)
- `all`: all states

**Default behavior:**
- `suppressed = true` issues are excluded unless `include_suppressed=true`
- `state = snoozed` issues are excluded from `all_open` unless `include_snoozed=true`

**Canonical `all_open` Definition:**
- `all_open` = `surfaced` + `acknowledged` + `addressing` + `awaiting_resolution` + `regressed`
- Excludes `detected` (system-only, not yet surfaced)
- Excludes `snoozed` unless `include_snoozed=true`
- Client card "Open Issues" counts use this exact definition
- To fetch only snoozed: `?state=snoozed`

```
POST /api/issues/:id/transition
{
  "action": "acknowledge" | "snooze" | "resolve" | "escalate" | "assign" | "await" | "unsnooze",
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

| Action | Effect | Required Fields | Auto-Archive Inbox |
|--------|--------|-----------------|-------------------|
| `acknowledge` | → `acknowledged` | — | ✅ `resolution_reason='issue_acknowledged_directly'` |
| `snooze` | → `snoozed` | `snooze_days` | ✅ `resolution_reason='issue_snoozed_directly'` |
| `unsnooze` | `snoozed` → `surfaced` | — | ❌ (creates new inbox item if none exists) |
| `assign` | → `addressing`, sets assigned_* | `assigned_to` | ✅ `resolution_reason='issue_assigned_directly'` |
| `await` | → `awaiting_resolution` | — | ❌ |
| `resolve` | **Persists `regression_watch` only** (audit logs `resolved`) | — | ✅ `resolution_reason='issue_resolved_directly'` |
| `escalate` | Increases severity AND/OR sets escalated flag | — | ❌ |

**Auto-Archive Inbox on Issue Transition (Hard Rule):**

When transitioning an issue via `/api/issues/:id/transition`, if an active inbox item exists for that issue (`underlying_issue_id = issue.id AND state IN ('proposed', 'snoozed')`), it MUST be auto-archived:

```python
def auto_archive_inbox_on_issue_transition(issue_id, action):
    if action in ('acknowledge', 'snooze', 'assign', 'resolve'):
        inbox_item = query("""
            SELECT * FROM inbox_items
            WHERE underlying_issue_id = ? AND state IN ('proposed', 'snoozed')
        """, issue_id)
        if inbox_item:
            update_inbox_item(
                id=inbox_item.id,
                state='linked_to_issue',
                resolved_at=utc_now_iso_ms_z(),
                resolved_issue_id=issue_id,
                resolution_reason=f'issue_{action}d_directly'  # e.g., 'issue_snoozed_directly'
            )
```

**Escalate Action:**

Escalation means:
1. Set `issues.escalated = true`
2. Set `issues.escalated_at = utc_now_iso_ms_z()`
3. Set `issues.escalated_by = current_user`
4. Optionally increase severity by one level (if not already critical)
5. State remains unchanged (escalation is orthogonal to state)

**Transition: resolved → regression_watch (Transactional — Hard Rule):**

`resolved` is a **conceptual state only**, never persisted durably in `issues.state`:

```python
def resolve_issue(issue_id, actor):
    with db.transaction():
        # 1. Log transition: current_state → resolved (audit only)
        log_transition(issue_id, current_state, 'resolved', actor, 'user')

        # 2. Log transition: resolved → regression_watch (immediate)
        log_transition(issue_id, 'resolved', 'regression_watch', 'system', 'system_workflow',
                       trigger_rule='enter_regression_watch')

        # 3. Persist ONLY regression_watch (never store 'resolved')
        update_issue(issue_id, state='regression_watch',
                     regression_watch_until=now + 90_days,
                     resolved_at=now, resolved_by=actor)

        # Transaction commits atomically — 'resolved' never observable in DB
```

- **API Response:** Returns `new_state = 'regression_watch'` (not `resolved`)
- **Audit trail:** Both transitions logged to `issue_transitions` for audit
- **Failure mode prevention:** If transaction fails, issue stays in prior state (not stranded in `resolved`)

**Why not persist resolved?** If anything interrupts between `resolved` and `regression_watch` transitions, you'd leak issues in `resolved` state that are invisible to all queries (neither open nor closed). The transactional approach eliminates this risk.

**Hard Invariant — No Resolved in Storage:**

```sql
-- This query MUST always return 0 rows
SELECT id FROM issues WHERE state = 'resolved';

-- Add DB constraint to enforce (if supported)
ALTER TABLE issues ADD CONSTRAINT chk_no_resolved_state
  CHECK (state != 'resolved');
```

**API Response Validation (Defense in Depth):**

All endpoints returning issues MUST validate `state != 'resolved'` before serialization:

```python
def serialize_issue(issue: Issue) -> dict:
    if issue.state == 'resolved':
        # Should never happen if DB constraint works; log and substitute
        log_error(f"Unexpected resolved state for issue {issue.id}")
        issue.state = 'regression_watch'  # Safe fallback for response
    return { ... }
```

This catches edge cases where DB constraint isn't active (e.g., migrations, test fixtures).

**Required Test:**
```python
def test_no_resolved_state_in_db():
    # After any resolve operation, verify no 'resolved' state exists
    count = db.query("SELECT COUNT(*) FROM issues WHERE state = 'resolved'")[0]
    assert count == 0, "CRITICAL: Found issues with state='resolved' in storage"
```

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
   - Fresh `proposed_at = utc_now_iso_ms_z()`

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
      "created_at": "2026-01-14T10:00:00.000Z",
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
      "timestamp": "2026-01-14T10:00:00.000Z"
    },
    {
      "user_id": "uuid",
      "user_name": "Mike",
      "action": "started",
      "task_name": "Homepage Redesign Mockups",
      "timestamp": "2026-01-13T14:30:00.000Z"
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

- Default request (no `?include=`): Returns union shape with `null` for excluded sections (type-safe default)
- `?include=health,signals`: **Omits** non-requested sections entirely (smaller payload, clearer contract)
- `?include=<forbidden_section>`: Returns `403 Forbidden` with error body (no union payload)
- `?include=<empty>` or `?include=<unknown>`: Returns `400 Bad Request`

**Include vs Default Response Shape:**
| Request | Non-requested sections |
|---------|------------------------|
| No `?include=` param | Present as `null` (union shape) |
| With `?include=` param | **Omitted entirely** (requested sections only) |

**Base Envelope (Authoritative Definition):**

These fields are ALWAYS present in every `/api/clients/:id` response, regardless of `?include=` or client status:

```typescript
interface ClientBaseEnvelope {
  id: string;        // UUID, always present
  name: string;      // Client name, always present
  status: "active" | "recently_active" | "cold";  // Computed, always present
  tier: "platinum" | "gold" | "silver" | "bronze" | "none";  // Always present, may be "none"
}
```

All other fields are conditional on client status and `?include=` parameter.

**Section Membership (Authoritative Definition):**

| Section Name | Fields Included | Available For |
|--------------|-----------------|---------------|
| `overview` | `health_score`, `health_label`, `top_issues`, `recent_positive_signals` | active only |
| `engagements` | `engagements` (grouped by brand) | active only |
| `financials` | `issued_*`, `paid_*`, `ar_*` (summary + aging) | all statuses |
| `signals` | `signals` (list with summary) | active only |
| `team` | `involvement`, `workload`, `tardiness`, `recent_activity` | active only |
| `brands` | `brands` (list of brand names) | active, recently_active |
| `last_invoices` | `last_invoices` (max 5) | recently_active only |

**Section Availability by Status:**

| Status | Default Sections (no include) | Includable Sections |
|--------|-------------------------------|---------------------|
| `active` | All | `overview`, `engagements`, `financials`, `signals`, `team`, `brands` |
| `recently_active` | `financials`, `brands`, `last_invoices` | `financials`, `brands`, `last_invoices` |
| `cold` | `financials` | `financials` |

**TypeScript Safety Note:** When using `?include=`, typed clients MUST NOT assume optional fields exist. Use optional chaining or null checks.

```json
// 403 response for forbidden include
{
  "error": "forbidden_section",
  "message": "Cannot include 'signals' for recently_active client",
  "allowed_includes": ["id", "name", "status", "financials", "brands", "last_invoices"]
}
```

**Include Param Parsing Rules:**

1. Split by `,`
2. Trim whitespace from each token
3. Drop empty strings
4. Reject unknown tokens → 400 `invalid_param`
5. Deduplicate tokens
6. If result is empty after processing → 400 `invalid_param`

```python
def parse_include(include_param: str, valid_sections: set) -> list:
    tokens = [t.strip() for t in include_param.split(',')]
    tokens = [t for t in tokens if t]  # drop empties
    for t in tokens:
        if t not in valid_sections:
            raise InvalidParam(f"Unknown include section: {t}", allowed_values=list(valid_sections))
    tokens = list(dict.fromkeys(tokens))  # dedupe preserving order
    if not tokens:
        raise InvalidParam("include param cannot be empty after parsing")
    return tokens
```

---

### 7.10 Control Room Inbox

```
GET /api/inbox
  ?type=issue|flagged_signal|orphan|ambiguous|all
  &severity=critical|high|medium|low|info
  &state=proposed|snoozed
  &client_id=<uuid>
  &unprocessed_only=true|false     // Filters (read_at IS NULL OR read_at < resurfaced_at); matches is_unprocessed() helper
  &sort=severity|age|client
  &order=desc                     // Default: desc
  &page=1
  &limit=20

**Hard Rule — State Param Semantics:**
- `state=proposed` → only proposed items (use for "Needs Attention" tab)
- `state=snoozed` → only snoozed items (use for "Snoozed" tab)
- **Omit `state` param entirely** → combined view (both proposed + snoozed)
- `state=all` → **INVALID, returns 400** with `error: 'invalid_state'`
- Terminal states (`dismissed`, `linked_to_issue`) → use `/api/inbox/recent` endpoint only

**Combined View Usage:** The omit-state combined view is for non-tabbed UIs (e.g., dashboard widgets showing "all open inbox items"). Tabbed Control Room MUST use explicit `state=proposed` or `state=snoozed` per tab. Never use combined view for tabbed navigation—it causes accidental mixing.

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
      "proposed_at": "2026-01-10T10:00:00.000Z",
      "resolved_at": "2026-01-13T14:30:00.000Z",
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
    "scope": "global",              // ALWAYS "global" — counts ignore request filters
    "needs_attention": 12,          // state = 'proposed' (unfiltered)
    "snoozed": 3,                   // state = 'snoozed' (unfiltered)
    "snoozed_returning_soon": 1,    // snooze_until < local_midnight_utc(org_tz, today + 2 days)
    "recently_actioned": 8,         // terminal actions last 7 days (unfiltered)
    "unprocessed": 8,               // is_unprocessed(): read_at IS NULL OR read_at < resurfaced_at
    "unprocessed_scope": "proposed", // Clarify: unprocessed count is within proposed state only
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
      "proposed_at": "2026-01-13T10:00:00.000Z",
      "resurfaced_at": null,        // Set when snooze expired; used for is_unprocessed()
      "attention_age_start_at": "2026-01-13T10:00:00.000Z",  // Server-computed: resurfaced_at ?? proposed_at
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
      "available_actions": ["tag", "assign", "snooze", "dismiss"]  // REQUIRED, server-computed
    }
  ]
}
```

**available_actions (Required — Server-Computed):**

Server MUST compute and return `available_actions: string[]` on every InboxItem. Frontend MUST NOT derive actions locally — always use the server-provided list.

**Actions by type:**
- `issue`: `["tag", "assign", "snooze", "dismiss"]`
- `flagged_signal`: `["tag", "assign", "snooze", "dismiss"]`
- `orphan`: `["link", "create", "dismiss"]`
- `ambiguous`: `["select", "dismiss"]` (after select: type converts to `flagged_signal`, actions become `["tag", "assign", "snooze", "dismiss"]`)

**Implementation Requirement — Global Counts:**

Counts in the response are **always global** (ignore all request filters). This prevents UX confusion where tab badges don't match header totals.

- `counts.scope = "global"` is always returned to signal this contract
- Implementation MUST use a **separate unfiltered query** for counts
- Do NOT compute counts from the filtered items query — this is a common bug

**Recommended Architecture: Separate Counts Endpoint**

Use `GET /api/inbox/counts` as the **sole source** for counts:
- Returns global counts only (cacheable, e.g., 30-second TTL)
- `/api/inbox` returns items only, no `counts` block
- Reduces payload churn and eliminates counts-mismatch bugs entirely
- Frontend fetches counts independently, displays in header

```
GET /api/inbox/counts

Response (cacheable):
{
  "needs_attention": 12,
  "snoozed": 3,
  "snoozed_returning_soon": 1,
  "recently_actioned": 8,
  "unprocessed": 5,
  "by_severity": { "critical": 2, "high": 5, ... },
  "by_type": { "issue": 7, "flagged_signal": 3, ... }
}
```

**Cache Header:** `Cache-Control: max-age=30` (30 seconds). Counts can be slightly stale; items list must be fresh.

**client_id Filter and Counts:**

When `client_id` is specified, counts remain org-global (NOT filtered to that client):
- This is correct for the main Control Room Inbox screen
- **UI Warning:** If building a "Client-context Inbox view" (showing items for one client), do NOT display global counts as if they are client-scoped

**Filtered Counts Option (for client-context views):**

Add `?include_filtered_counts=true` to get both global and filtered counts:

```json
{
  "counts": {
    "scope": "global",
    "needs_attention": 12,  // org-wide
    "snoozed": 3
  },
  "filtered_counts": {      // Only present if include_filtered_counts=true
    "scope": "filtered",
    "needs_attention": 2,   // matching current filters (e.g., client_id)
    "snoozed": 1
  },
  "items": [...]
}
```

This prevents frontend engineers from accidentally displaying global counts in a filtered view.

**Required Test — Counts Independence:**
```python
def test_counts_ignore_filters():
    # Setup: 3 proposed items (1 critical, 1 high, 1 medium)
    resp1 = api.get('/api/inbox?severity=critical')
    resp2 = api.get('/api/inbox?severity=high')
    resp3 = api.get('/api/inbox')  # no filter

    # All responses must have identical counts
    assert resp1.counts == resp2.counts == resp3.counts
    assert resp1.counts.needs_attention == 3  # global, not filtered
```
This test MUST fail if counts are derived from the filtered query.

**issue_category field:** Present only when `type = "issue"`. Derived via join to `issues.type` (not stored in `inbox_items`). Values: `financial`, `schedule_delivery`, `communication`, `risk`.

**issue_state field:** Present only when `type = "issue"`. Derived via join to `issues.state`. Values per §6.5 issue lifecycle. Enables inbox cards to display underlying issue state (e.g., "surfaced", "acknowledged", "addressing") without requiring a separate `/api/issues/:id` call per row.

**issue_assignee field:** Present only when `type = "issue"` AND `issues.assigned_to IS NOT NULL`. Returns `{ id, name }` of assigned user. Enables inbox cards to show "Assigned to Sarah" inline.

```json
// Example inbox item response when type = "issue"
{
  "id": "uuid",
  "type": "issue",
  "issue_category": "financial",
  "issue_state": "addressing",         // NEW: from issues.state
  "issue_assignee": {                  // NEW: present if assigned
    "id": "user-uuid",
    "name": "Sarah Chen"
  },
  "severity": "high",
  "state": "proposed",
  ...
}
```

**Note on naming:** `type` refers to inbox item type; `issue_category` refers to the underlying issue's category; `issue_state` refers to the underlying issue's lifecycle state. This avoids ambiguity between inbox states and issue states.

**Denormalized vs Recomputed Fields (Data Freshness):**

Inbox response embeds data from related entities. Understand which fields are snapshots vs live:

| Field | Source | Freshness | Notes |
|-------|--------|-----------|-------|
| `severity` | `inbox_items.severity` | Snapshot | May drift from underlying issue; see severity sync rule below |
| `title` | `inbox_items.title` | Mutable snapshot | Detector may update while `state IN ('proposed', 'snoozed')`; frozen once terminal |
| `client.name` | Join to `clients.name` | Live (query-time) | Always current |
| `client.status` | Computed | Live (query-time) | Recomputed per request |
| `engagement.name` | Join to `engagements.name` | Live (query-time) | Always current |
| `evidence` | `inbox_items.evidence` | Mutable snapshot | Updated by detector enrichment (`last_refreshed_at`); frozen once terminal |
| `issue_category` | Join to `issues.type` | Live (query-time) | Always current |

**Title Mutability Rule:**
- Detectors MAY update `title` and `evidence` while `state IN ('proposed', 'snoozed')` (e.g., "2 invoices overdue" → "3 invoices overdue")
- Once `state IN ('dismissed', 'linked_to_issue')` (terminal), title is frozen for audit
- Updates set `last_refreshed_at = utc_now_iso_ms_z()`; `proposed_at` remains unchanged

**Severity Sync Rule (for type='issue' inbox items):**
- On read, compute `display_severity = max(inbox_items.severity, issues.severity)` to prevent drift
- Store `inbox_items.severity` for audit; display the max for UX consistency
- This ensures escalated issues show correctly even if inbox item wasn't refreshed

**`last_refreshed_at` Meaning:**
- Indicates when detector last updated evidence for this item
- Does NOT reflect changes to joined entities (client renamed, etc.)
- If `last_refreshed_at` is old but client/engagement changed, the card shows current names but stale evidence

**Refresh Behavior:** Inbox cards show live client/engagement names but snapshot severity/title/evidence. If this causes confusion ("client renamed but card shows old name"), the issue is in the join, not the snapshot.

**Evidence Rendering by Context:**

| Context | Evidence Source | Component Reuse Warning |
|---------|-----------------|-------------------------|
| **Inbox card** | `inbox_items.evidence` | Snapshot; may be stale if not refreshed |
| **Inbox card (type='issue')** | `inbox_items.evidence` | Do NOT fetch `issues.evidence` — use inbox snapshot |
| **Client page → Top Issues** | `issues.evidence` | Live from issue table |
| **Client page → Signals tab** | `signals.evidence` | Live from signal table |
| **Client Snapshot (cold)** | `inbox_items.evidence` OR `issues.evidence` | Depends on `context.source` in response |

**Do NOT reuse inbox card component for client page issues.** Inbox uses `inbox_items.evidence` (snapshot); client page uses `issues.evidence` (live). Mixing them causes stale data bugs.

**Frontend Integration: Tab → API Mapping**

UI Tabs (as shown in spec):
- **Needs Attention** → `state=proposed` (default tab)
- **Snoozed** → `state=snoozed`
- **Recently Actioned** → `/api/inbox/recent` endpoint

```typescript
// Helper: build inbox query params per tab
function getInboxParams(tab: 'needs_attention' | 'snoozed' | 'recent'): URLSearchParams {
  const params = new URLSearchParams();
  switch (tab) {
    case 'needs_attention':
      params.set('state', 'proposed');
      break;
    case 'snoozed':
      params.set('state', 'snoozed');
      break;
    case 'recent':
      // Use /api/inbox/recent endpoint instead
      throw new Error('Use /api/inbox/recent for Recently Actioned tab');
  }
  return params;
}

// To show BOTH proposed + snoozed (combined view): omit state param entirely
// ❌ NEVER: params.set('state', 'all')  // Returns 400 invalid_state
```

**Required Test — state=all Rejection:**
```typescript
test('state=all returns 400', async () => {
  const resp = await api.get('/api/inbox?state=all');
  expect(resp.status).toBe(400);
  expect(resp.body.error).toBe('invalid_state');
});

test('omitted state returns proposed+snoozed', async () => {
  const resp = await api.get('/api/inbox');  // no state param
  const states = resp.body.items.map(i => i.state);
  expect(states.every(s => s === 'proposed' || s === 'snoozed')).toBe(true);
});
```

**Sorting Defaults:**

| Sort Key | Order | Description | UI Label | SQL Clause |
|----------|-------|-------------|----------|------------|
| `severity` | Descending | critical > high > medium > low > info | "Severity" | `ORDER BY severity_weight DESC, proposed_at ASC, id ASC` |
| `age` | Ascending | Oldest first (`proposed_at` ASC) | "Oldest first" | `ORDER BY proposed_at ASC, id ASC` |
| `age_desc` | Descending | Newest first (`proposed_at` DESC) | "Newest first" | `ORDER BY proposed_at DESC, id ASC` |
| `client` | Ascending | Alphabetical by client name | "Client" | `ORDER BY client.name ASC, proposed_at ASC, id ASC` |

**Default sort:** `severity` descending, then `age` ascending, then `id` ascending (oldest critical items first; deterministic tie-breaker).

**Tie-break invariant:** All sort options end with `id ASC` to ensure deterministic pagination. Never omit the final tie-breaker.

**Note:** UI dropdowns should show explicit labels ("Oldest first" / "Newest first") rather than ambiguous "Age ▼".

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
  "resolved_at": "2026-01-15T14:30:00.000Z"
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
- **Link (orphan):** Item `type` converts from `orphan` → `flagged_signal`
- **Select (ambiguous):** Item `type` converts from `ambiguous` → `flagged_signal`
- Item becomes fully actionable with updated actions: `["tag", "assign", "snooze", "dismiss"]`
- Response includes updated scoping: `client_id`, `brand_id`, `engagement_id`
- Server response MUST include `actions` array with the updated available actions

**Type Conversion Rationale:** After link/select, the item is semantically a resolved flagged signal (single signal with known engagement). Converting the type:
- Eliminates special-case "post-resolution orphan/ambiguous" handling
- Simplifies suppression key logic (use flagged_signal formula)
- Keeps "Actions by type" table authoritative
- **Audit trail:** Store `evidence.payload.original_inbox_type = 'orphan'|'ambiguous'` to preserve history

**Actions Array is Authoritative:**

Server MUST return updated `actions` array in response to ALL state-changing actions:
- `tag`, `assign` → `actions: []` (terminal)
- `snooze` → `actions: ["tag", "assign", "dismiss"]` (snoozed items remain actionable)
- `dismiss` → `actions: []` (terminal)
- `link`, `select` → `actions: ["tag", "assign", "snooze", "dismiss"]`
- Bulk actions → each item in response includes updated `actions`

Frontend MUST NOT infer actions from state; always use server-provided array.

**Snoozed Inbox Items Are Actionable (Design Decision):**

Users can Tag/Assign/Dismiss snoozed inbox items directly from the Snoozed tab without waiting for expiry:
- This allows users to change their mind after snoozing
- Snoozed tab MUST render Tag/Assign/Dismiss buttons (not just "Unsnooze")
- Taking action on a snoozed item transitions it to terminal state immediately
- **UI copy:** Show "Snoozed until [date]" badge but keep action buttons visible

**mark_read Exemption:** `mark_read` is NOT a primary action and is NOT included in the `actions` array. It is always available on non-terminal items (`state IN ('proposed', 'snoozed')`) regardless of type. Frontend renders "Mark processed" button independently of the `actions` array. This exemption exists because `mark_read` affects presentation (bold/unbold) not workflow state.

**Action Payload Validation:**

| Action | Required Fields | Optional | Reject if Present |
|--------|-----------------|----------|-------------------|
| `tag` | — | `note` | `assign_to`, `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `assign` | `assign_to` | `note` | `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `snooze` | `snooze_days` | `note` | `assign_to`, `link_engagement_id`, `select_candidate_id` |
| `dismiss` | — | `note` | `assign_to`, `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `link` | `link_engagement_id` | `note` | `assign_to`, `snooze_days`, `select_candidate_id` |
| `create` | — | `note` | `assign_to`, `snooze_days`, `link_engagement_id`, `select_candidate_id` |
| `select` | `select_candidate_id` | `note` | `assign_to`, `snooze_days`, `link_engagement_id` |

Return `400 Bad Request` if required fields missing or unexpected fields present.

**State Machine Rejection Rules (409 Conflict):**

`POST /api/inbox/:id/action` MUST return `409 Conflict` with `error: 'invalid_state'` if:

| Condition | Error Message |
|-----------|---------------|
| Item is terminal (`state IN ('dismissed', 'linked_to_issue')`) | "Cannot act on terminal item" |
| Action not in server-returned `actions[]` for that item | "Action not available for current item state/type" |
| `snooze_until` already in past | "Snooze time must be in future" |

`POST /api/issues/:id/transition` MUST return `409 Conflict` with `error: 'invalid_state'` if:

| Condition | Error Message |
|-----------|---------------|
| `state = regression_watch` and action != (none) | "Cannot transition issue in regression watch" |
| `state = closed` and action != (none) | "Cannot transition closed issue" |
| `suppressed = true` and action != `unsuppress` | "Suppressed issue requires unsuppress first" |
| Action not in server-returned `available_actions[]` | "Action not available for current issue state" |

**Hard Rule:** Backend MUST enforce these rules even if frontend accidentally allows the action. Server is authoritative.

**Create Action (Two-Step Flow):**

The `create` action for orphan items initiates engagement creation but does not complete it:

1. `POST /api/inbox/:id/action` with `action='create'`
2. Response includes:
   - `draft_engagement`: Pre-populated fields inferred from signal (client, brand, suggested name)
   - `next_step_url`: URL to engagement creation form with draft pre-filled
   - `origin_signal_id`: The underlying signal ID (stored in inbox_items.underlying_signal_id)
3. User completes form and submits
4. `POST /api/engagements` creates the engagement, passing `origin_signal_id` in request body
5. System auto-links the orphan signal to the new engagement via `origin_signal_id`
6. Inbox item becomes actionable (Tag/Assign available) via resolver pass keyed by `signal_id`

Inbox item remains `proposed` throughout. The `draft_engagement` is a convenience, not a DB entity.

**Linkage Callback Semantics:** `POST /api/engagements` accepts optional `origin_signal_id` field. When present, system updates `signals.engagement_id` and refreshes any orphan inbox item referencing that signal.

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
  "read_at": "2026-01-15T14:30:00.000Z"
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
  "state_changed_at": "2026-01-01T00:00:00.000Z",
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
  "transitioned_at": "2026-01-15T14:30:00.000Z"
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
- [ ] Active cards: Issued + Paid (Prior Yr, YTD), AR (Outstanding + Overdue), Issues count
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
- [ ] AR_overdue_source (Xero status) vs AR_overdue_effective (computed) distinguished
- [ ] Partial payments: v1 treats as fully paid/unpaid
- [ ] Task linking: via engagement_id only, no name matching (6.3)
- [ ] Engagement resolver: may use name matching for low-confidence proposals (6.8)
- [ ] Evidence: URL or deterministic fallback; detector rules defined
- [ ] Issue lifecycle: 10 states (includes `snoozed`), uses `awaiting_resolution` (not "monitoring")
- [ ] Suppressed issues excluded from health/counts
- [ ] Signals: good/neutral/bad, 7 sources (asana, gmail, gchat, calendar, meet, minutes, xero)
- [ ] Timestamp format: ISO 8601
- [ ] Timestamp validation: parse+roundtrip (`validate_timestamp()`), not just length check
- [ ] DST zones rejected at org creation (not runtime)
- [ ] `today_local` computed once per request, passed to all subcomputations
- [ ] `resurfaced_at` set on snooze expiry; unprocessed = `read_at IS NULL OR read_at < resurfaced_at`

### Pagination & Sort Stability
- [ ] All sorted endpoints include deterministic tie-breaker (final sort key = `id ASC`)
- [ ] Inbox: `severity_weight DESC, proposed_at ASC, id ASC`
- [ ] Issues: `severity_weight DESC, created_at DESC, id ASC`
- [ ] Clients: `health_score ASC, ar_overdue DESC, id ASC`
- [ ] Signals: `observed_at DESC, id ASC`
- [ ] Engagements: `state_weight ASC, name ASC, id ASC`
- [ ] Cursor-based pagination uses `(sort_key, id)` tuples; no offset/limit for large sets

### Evidence Schema Versioning
- [ ] `evidence_version` field on issues, signals, inbox_items
- [ ] v1 schema defined in §6.16
- [ ] Migration rule: old evidence CAN be re-rendered if schema evolves (no payload changes, only renderer updates)
- [ ] Breaking changes: increment version, keep v1 renderer for historical records
- [ ] Backfill strategy: lazy migration on read, or batch job with `evidence_version < current`

### Concurrency & Terminal Immutability
- [ ] Terminal states (`dismissed`, `linked_to_issue`, `regression_watch`, `closed`) are immutable for inbox items
- [ ] Terminal states for issues: `regression_watch`, `closed` (note: `resolved` never persisted)
- [ ] Detector upsert MUST no-op if `state IN terminal_states`
- [ ] User actions on terminal items return `409 Conflict`
- [ ] Race condition rule: if user dismisses while detector enriches, dismiss wins (check state before write)
- [ ] Optimistic locking: include `updated_at` in WHERE clause for state transitions

### Authorization Model
- [ ] Org-global state: all users in org share inbox/issue/suppression state
- [ ] Action attribution: `*_by` fields track actor for audit
- [ ] Role-based access (future): exec, lead, finance, ops roles defined in §V4 spec
- [ ] Suppression: any authenticated org user can dismiss/suppress
- [ ] Unsuppress: any authenticated org user can unsuppress (no elevated permission required in v1)
- [ ] API auth: all endpoints require valid org membership token
- [ ] mark_all_read: scoped to `state='proposed'` only (excludes snoozed)

### State Machine Validation Tables
- [ ] Inbox allowed transitions defined (proposed↔snoozed, proposed→terminal, snoozed→terminal)
- [ ] Issue allowed transitions defined (10-state machine with explicit edges)
- [ ] Engagement allowed transitions defined (planned→active→...→completed + blocked/paused)
- [ ] Server validates transition before applying; rejects invalid with 409
- [ ] State machine tables stored as code constants, not DB lookups

### Idempotency Keys
- [ ] User actions (tag/assign/snooze/dismiss) accept optional `idempotency_key` header
- [ ] Duplicate requests with same key within 5 minutes return cached response
- [ ] Prevents double-click races creating duplicate issues or double state transitions
- [ ] Key format: `{user_id}:{action}:{item_id}:{timestamp_bucket}`

### Resurfaced_at Constraints
- [ ] `resurfaced_at` set ONLY when snooze expires (not on manual unsnooze)
- [ ] If `state='proposed'` AND item was previously snoozed, `resurfaced_at` should be non-null
- [ ] Startup canary: `SELECT * FROM inbox_items WHERE state='proposed' AND snooze_until IS NULL AND snoozed_at IS NOT NULL AND resurfaced_at IS NULL` should return 0 rows

### Terminal Fetch Rules (Server Enforcement)
- [ ] `GET /api/inbox` MUST exclude terminal states even if client passes `state=dismissed`
- [ ] Terminal states only via `/api/inbox/recent` endpoint
- [ ] Server ignores invalid state params; does NOT return terminal items from main endpoint
- [ ] API returns 400 for `state=all` (explicit rejection, not silent ignore)

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
- [ ] Transition reason enum aligned: user, system_timer, system_signal, system_threshold, system_aggregation, system_workflow

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
- [ ] Transition reasons: 'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation', 'system_workflow'

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
- [ ] Inbox state param: `proposed|snoozed` only; `state=all` returns 400 (omit param for "All")
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
9. Engagement health checks `open_tasks_in_source == 0` BEFORE `linked_pct` check; then checks `linked_open_tasks == 0` AFTER `linked_pct` passes
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
54. Org-global shared state explicitly stated (read/snooze/dismiss are global)
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
1. **Dismiss suppression expiry:** Dismiss a flagged_signal. Suppression key uses scope-based formula: `(client_id, engagement_id, source, rule_triggered)` — NOT `source_id`. Verify a **new signal with different source_id but same scope** is also suppressed within window (30 days). Verify suppression expires after 30 days.
2. **Issue suppression:** Suppress an issue via inbox dismiss. Verify `suppressed = true`, excluded from health penalty, excluded from open counts, excluded from inbox.
3. **Unsuppress:** Call `POST /api/issues/:id/unsuppress`. Verify issue reappears in counts and health scoring.

### Snooze Behavior
4. **Snooze expiry boundary:** Snooze an inbox item with `snooze_until` exactly equal to job run time. Verify it resurfaces exactly once (not duplicated). **Also verify:** snooze_until in the past resurfaces on next run; snooze_until null rejected at API with 400.
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
23. **Issue snooze archives inbox item:** Snooze an issue from client detail page while a proposed inbox item exists. Verify inbox item transitions to `linked_to_issue` with `resolution_reason = 'issue_snoozed_directly'` (not left in proposed). This distinguishes from tag/assign resolutions in audit.
24. **Inbox snooze independent of issue:** Snooze an inbox item. Verify underlying issue state is NOT changed (issue remains surfaced while inbox item is snoozed).

### AR Edge Cases
25. **Sent but past due:** Invoice with `status='sent'` and `due_date < today`. Verify:
    - `aging_bucket = '1_30'` (or appropriate bucket)
    - `status_inconsistent = true`
    - A `flagged_signal` with rule `invoice_status_inconsistent` is created
26. **No double-create:** Same invoice does NOT create both a financial issue AND a flagged_signal simultaneously (define precedence: issue takes priority once threshold reached).

### Multi-user Scope (Org-Global State)
27. **Global suppression:** User dismisses inbox item. Verify suppression applies globally (no other user can see re-proposals until expiry).
28. **Global read state:** Mark item as read. Verify `read_at` affects all users (single org-global read_at field).

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
37. **Dubai midnight conversion:** Invoice due date "2026-02-07" in UTC. Verify client status boundary uses Asia/Dubai midnight (test at 2026-02-06T20:00:00.000Z and 2026-02-07T19:59:59.999Z).

### Tagged Preservation
38. **Assign after tag preserves tagged_by:** Issue is tagged (tagged_by set). Later assigned. Verify `tagged_by_user_id` and `tagged_at` are NOT overwritten.

### Constraint Violations
39. **Constraint: linked requires issue:** Attempt `state = 'linked_to_issue'` with `resolved_issue_id = NULL`. Expect constraint violation.
40. **Constraint: dismissed requires audit:** Attempt `state = 'dismissed'` with `dismissed_by = NULL`. Expect constraint violation.

### Errata v2.2 Additions
41. **Suppressed issue action gating:** Verify `available_actions = ['unsuppress']` only for issues with `suppressed = true`. All other actions disabled.
42. **Snooze uses local midnight:** Verify snooze timestamp equals local midnight conversion (not `now + N*24h`). Inbox: `inbox_items.snooze_until`. Issue: `issues.snoozed_until`. Example: Snooze 7d on 2026-02-08 at 3pm Dubai → timestamp = `2026-02-14T20:00:00.000Z`.
43. **Invoice identity collision:** Two invoices with same `invoice_number` but different `source_id` must NOT collide in suppression or deduplication.
44. **Concurrent detector upsert:** Simulate two detector workers attempting to create inbox item for same underlying entity. Assert exactly one active row exists (upsert, not blind insert).
45. **state=all returns 400:** Call `GET /api/inbox?state=all`. Verify 400 response with `error: 'invalid_state'`.
46. **Issue snooze dialog copy:** Verify issue snooze dialog shows "Health impact removed while snoozed" (not inbox snooze copy).
47. **linked_open_tasks=0 after linking check:** Engagement where `open_tasks_in_source > 0` but `linked_open_tasks = 0` after linking check passes returns `score=100` with `gating_reason='no_linked_open_tasks'`.
48. **Suppression expiry resurface:** Dismiss an issue. Wait for suppression rule to expire (or mock time). Verify: (a) new matching proposal is allowed, (b) `issues.suppressed` is `FALSE` after auto-unsuppress job runs.
49. **proposed_at immutability:** Create inbox item. Run detector upsert/enrichment. Assert `proposed_at` unchanged; only `last_refreshed_at` updated.
50. **resolved_issue_id consistency:** For `type='issue'` inbox item, attempt to set `resolved_issue_id` to a different issue than `underlying_issue_id` when transitioning to `linked_to_issue`. Verify constraint violation.
51. **read_at not set on view:** Fetch inbox item detail/evidence. Assert `read_at` remains `NULL` until explicit `POST /api/inbox/:id/mark_read` is called.

### Additional High-Value Tests (v2.2)

52. **Timestamp write discipline:** Insert a row with `created_at='2026-02-08T14:30:00Z'` (no ms). Verify startup canary fails and row is flagged for repair.

53. **Invoice overdue boundary:** With `org_tz=Asia/Dubai`, invoice with `due_date=today_local` and `status='overdue'` (from Xero). Verify `days_overdue=0` and `aging_bucket='1_30'` (not current). Source status is respected; aging shows "0d overdue".

54. **Snooze until correctness:** Snooze 7d at Dubai 15:00 on 2026-02-08. Verify stored `snooze_until = 2026-02-14T20:00:00.000Z` (midnight 2026-02-15 Dubai = 20:00 UTC day before).

55. **Inbox counts independence:** (Mandatory CI test per §7.10) Verify `/api/inbox?severity=critical` and `/api/inbox?severity=high` return identical `counts` objects.

56. **Suppression expiry auto-unsuppress:** Insert suppression rule with `expires_at < now` and `issue.suppressed=true`. Run auto-unsuppress job. Verify `issues.suppressed = false`.

57. **No resolved state in DB:** After any `resolve` action, verify `SELECT COUNT(*) FROM issues WHERE state='resolved'` returns 0.

58. **root_cause_fingerprint required:** Attempt to create issue with `engagement_id=NULL`, `brand_id=NULL`, `root_cause_fingerprint=NULL`. Verify constraint violation.

59. **Snoozed inbox items actionable:** Verify snoozed inbox item returns `actions: ["tag", "assign", "dismiss"]` and all three actions succeed without unsnooze.

60. **Orphan type conversion on link:** Link an orphan inbox item. Verify `type` changes from `'orphan'` to `'flagged_signal'` and `evidence.payload.original_inbox_type = 'orphan'`.

### Timestamp Invariants (v2.2+)

61. **Roundtrip parse/format:** For each timestamp column in TIMESTAMP_COLUMNS, verify `parse(ts) → format() == ts`. Catch semantic errors (invalid dates like month=99).

62. **Lexicographic ordering:** Generate 100 random canonical timestamps, sort as strings vs sort as datetimes → order must be identical. This validates the 24-char format preserves chronological ordering.

63. **Overdue boundary strict <:** `due_date = today_local` → NOT overdue. `due_date = yesterday_local` → overdue with `days_overdue=1`. Test across UTC boundary around Dubai midnight.

### Terminal State Atomicity

64. **Dismiss requires all fields:** Attempt `UPDATE inbox_items SET state='dismissed'` without `resolved_at`, `dismissed_at`, `dismissed_by`, `suppression_key`. Verify CHECK constraint violation.

65. **Two-step update fails:** Attempt `UPDATE state='dismissed'; UPDATE resolved_at=...` as separate statements. Verify constraint violation on first statement.

### Suppression Key Determinism

66. **Cross-process determinism:** Compute suppression_key for same input in Python and JavaScript. Keys must match exactly (canonical JSON sorting + SHA-256).

67. **Separator consistency:** Verify `json.dumps(..., separators=(',', ':'))` produces no whitespace. Whitespace would break key determinism.

---

## 8. API Error Envelope (Canonical)

All API error responses use this standardized envelope:

```json
{
  "error": "error_code",           // snake_case error identifier
  "message": "Human-readable description",
  "details": {},                   // optional: additional context
  "allowed_values": []             // optional: valid options for the field
}
```

**Standard Error Codes:**

| Code | HTTP | When |
|------|------|------|
| `invalid_state` | 400/409 | Action not allowed for current state |
| `invalid_param` | 400 | Parameter value not in allowed set |
| `missing_param` | 400 | Required parameter not provided |
| `forbidden_section` | 403 | Include section not allowed for client status |
| `not_found` | 404 | Entity not found |
| `conflict` | 409 | Operation conflicts with current state |

**Examples:**

```json
// 400 - Invalid state param
{
  "error": "invalid_param",
  "message": "state=all is not valid; omit param for 'All'",
  "allowed_values": ["proposed", "snoozed"]
}

// 409 - Terminal item mark_read
{
  "error": "invalid_state",
  "message": "Cannot mark terminal item as read; item already resolved"
}

// 400 - Missing required param
{
  "error": "missing_param",
  "message": "assign_to is required for assign action",
  "details": { "action": "assign" }
}
```

---

## Changelog

### v2.9 (2026-02-09)
- **BREAKING:** `resolved` state is never persisted; resolve action persists `regression_watch` directly (added `chk_no_resolved_state` constraint)
- Added `aggregation_key` column to `issues` table for detector upsert with unique index
- Added §0.5: `attention_age_start_at` for canonical age sorting
- Added `unprocessed` count to header (using `is_unprocessed()`: `read_at IS NULL OR read_at < resurfaced_at`)
- Made `available_actions` required in InboxItem and Issue API responses
- Added §6.19: Detector window boundaries (org-local midnight)
- Extended timestamp validation canary to include ordering assertions (`validate_timestamp_ordering()`)
- Added `attention_age_start_at` and `resurfaced_at` to InboxItem response
- Updated `unprocessed` count definition to use `is_unprocessed()` helper

### v2.8 (2026-02-08)
- Initial detailed specification

---

*End of specification.*
