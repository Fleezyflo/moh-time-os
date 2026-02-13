# Spec Errata — Time OS UI Spec v2.1.1

*Amendments to CLIENT-UI-SPEC-v2.1-FINAL.md based on implementation review*

**Status:** REVIEW REQUIRED
**Date:** 2025-02-08

---

## 1. Contradictions / Spec Drift

### 1.1 Decision A.1 — Inbox Snooze vs Issue Snooze Semantics

**Problem:** Decision A says inbox snooze hides the reminder; issue remains open and health unchanged. But §6.5/6.6 says snoozed issues are excluded from health scoring. Both are correct but the distinction isn't explicit.

**Fix:** Add after Decision A:

> **Decision A.1: Snooze Semantics Distinction**
>
> | Snooze Type | Target | Health Impact | UI Copy Requirement |
> |-------------|--------|---------------|---------------------|
> | **Inbox snooze** | Reminder/proposal only | ❌ Unchanged — issue remains open | "Health unchanged" |
> | **Issue snooze** | The problem itself | ✅ Removed — penalty suspended | "Health impact removed while snoozed" |
>
> Inbox snooze = "reminder snooze" (defer notification, problem persists)
> Issue snooze = "problem snooze" (defer problem, health relieved)

**UI Copy Amendment:**

Add to §6.5 under "Issue Snooze ↔ Inbox Item Behavior":

> **Required UI copy for issue snooze dialog:** "Health impact removed while snoozed. Issue will resurface on [date]."

---

### 1.2 GET /api/inbox — Ban `state=all` Explicitly

**Problem:** Spec says omit param for "All" and checklist #74 says `state` doesn't include "all", but no explicit 400 error is defined.

**Fix:** Add to §7.2 (Inbox API):

> **Invalid state values:**
> - If `state=all` is provided, return `400 Bad Request`:
>   ```json
>   {
>     "error": "invalid_state",
>     "message": "Use omit state param for 'All'; 'all' is not a valid filter value"
>   }
>   ```

---

### 1.3 "Single-user scope" Typo Correction

**Problem:** Checklist #83 correctly says "Single-org multi-user", but earlier mentions exist of "single-user scope".

**Fix:** Global find/replace in spec:
- Replace "single-user scope" → "org-global shared state"
- Verify: only "single-org, multi-user team with org-global shared state" pattern exists

**Affected locations:** Search for "single-user" and correct.

---

### 1.4 Timestamp Formatting — DB Write Discipline

**Problem:** Spec requires `YYYY-MM-DDTHH:MM:SS.sssZ` (24 chars) but doesn't prohibit direct `now()` calls which may produce different formats.

**Fix:** Add to §0.1 "Time Library Contract":

> **DB Write Discipline:**
> - DB writes NEVER call `now()` directly
> - All timestamp writes use `utc_now_iso_ms_z()` from time library
> - This ensures consistent 24-char format with exactly 3-digit milliseconds
>
> ```python
> def utc_now_iso_ms_z() -> str:
>     """Returns current UTC time in canonical format."""
>     return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.') + \
>            f'{datetime.now(UTC).microsecond // 1000:03d}Z'
> ```

---

## 2. High-Risk Implementation Pitfalls

### 2.1 Suppressed Issue UI/Action Gating

**Problem:** Suppressed issues remain `surfaced` but are excluded from health/counts. UI needs explicit visual treatment or they appear "stuck open forever".

**Fix:** Add to §6.5 under "Suppressed issues":

> **UI Treatment for Suppressed Issues:**
> - Show pill badge: `[Suppressed]`
> - Available actions: `[Unsuppress]` only (disable all other actions)
> - Row styling: muted/greyed to indicate inactive state
> - Tooltip: "This issue was dismissed and will not affect health until unsuppressed"

**API Amendment (§7.6):**

> For issues with `suppressed = true`:
> ```json
> {
>   "available_actions": ["unsuppress"]
> }
> ```

---

### 2.2 Dedupe Index — Concurrent Detector Upsert Contract

**Problem:** Unique indexes prevent duplicate active inbox items, but concurrent detector runs could race.

**Fix:** Add to §6.4 (Detectors):

> **Detector Contract — Upsert Invariant (REQUIRED):**
> - Detectors MUST upsert by underlying key, never blind insert
> - Before creating inbox item, check: `SELECT id FROM inbox_items WHERE underlying_issue_id = ? AND state IN ('proposed', 'snoozed')`
> - If exists: update existing row (enrich evidence, bump timestamp)
> - If not exists: insert new row
> - Use `INSERT ... ON CONFLICT DO UPDATE` or equivalent atomic operation
>
> This prevents unique constraint violations under concurrent detector runs.

---

### 2.3 Invoice Identity — Canonical Key

**Problem:** "Same invoice" checks use invoice number, but number can collide across edge cases. `source_id` is the canonical key.

**Fix:** Add to §6.10 (Xero Linking):

> **Invoice Identity (Canonical):**
> ```
> invoice_identity = (source_system='xero', source_id)
> ```
> - `source_id` (Xero invoice UUID) is the **primary identity key**
> - `invoice_number` is **display-only** — may collide in rare multi-tenant edge cases
> - All deduplication, suppression, and uniqueness checks use `source_id`

---

### 2.4 Resolve → Regression Watch — Collapse Transition

**Problem:** `resolved` state is instantaneous (immediately transitions to `regression_watch`), creating audit noise and UI confusion.

**Fix (Option 1 — Collapse):** Amend §6.5:

> **Resolve Transition (Amended):**
> - User clicks "Resolve" → issue transitions directly to `regression_watch` (skip `resolved` state)
> - Set `resolved_at` timestamp for audit (field exists even though `resolved` state doesn't persist)
> - Log single transition: `previous_state → regression_watch` with `trigger_rule = 'user_resolve_enter_regression_watch'`
>
> **Rationale:** `resolved` as a transient state lasting <1 second adds complexity without value. The `resolved_at` field captures the semantic moment.

**UI Label Mapping Update:**

| API State | UI Label | Notes |
|-----------|----------|-------|
| `regression_watch` | "Resolved (watching)" | Combines resolved + watch semantics |

---

### 2.5 Engagement Health — Explicit Division Guard

**Problem:** Division by `tasks_total` (which is `linked_open_tasks`) could be zero after passing the linking check. Currently safe due to early return, but implicit.

**Fix:** Add explicit guard to §6.6 engagement health pseudocode:

```python
# After linking check passes...
if linked_open_tasks == 0:
    # No linked tasks to evaluate — engagement is "clear"
    return EngagementHealth(
        score=100,
        gating_reason='no_linked_open_tasks',
        gating_label='No open tasks'
    )

# Safe to proceed — linked_open_tasks > 0
tasks_total = linked_open_tasks
overdue_pct = round((tasks_overdue / tasks_total) * 100)
# ...
```

---

## 3. Underspecified Areas

### 3.1 Assign Implies Acknowledgment

**Problem:** Assign action "skips acknowledged" and sets `tagged_*` fields, but UI copy says "Assigned (and acknowledged)". Clarify intent.

**Fix:** Add to §1.7:

> **Assign Semantics:**
> - Assign implies acknowledgment — the `tagged_*` fields represent acknowledgment even when state goes directly to `addressing`
> - User saw and acted on the issue; no separate "acknowledged" state needed
> - This is intentional: "Assign" is a stronger commitment than "Acknowledge"

---

### 3.2 Snooze Duration — Local Midnight Semantics

**Problem:** "Snooze 7d" could mean `now + 7*24h` or `local midnight of today + 7 days`. Spec uses day boundaries elsewhere but snooze is ambiguous.

**Fix:** Add to §1.6 (Snooze action):

> **Snooze Duration Semantics:**
> - "Snooze N days" = until local midnight of `(today + N days)` in org timezone
> - Aligns with "days=N uses org-local day boundaries" convention
> - Example: Snooze 7d on 2026-02-08 at 3pm Dubai → `snoozed_until = 2026-02-15T00:00:00` Dubai = `2026-02-14T20:00:00Z`
>
> ```python
> def snooze_until(org_tz: str, days: int) -> datetime:
>     today_local = datetime.now(ZoneInfo(org_tz)).date()
>     target_date = today_local + timedelta(days=days)
>     return local_midnight_utc(org_tz, target_date)
> ```

---

### 3.3 "Recently Actioned" Window — Header Uses days=7

**Problem:** Header shows "Recently Actioned" but doesn't specify the window. API supports `days=N` param.

**Fix:** Add to §1.2 (Inbox Structure):

> **"Recently Actioned" Section:**
> - Header always uses `days=7` (hardcoded)
> - Uses `window_start(org_tz, 7)` for consistency
> - API: `GET /api/inbox/recent?days=7`

---

### 3.4 Cold Client Snapshot — Action List Alignment

**Problem:** Snapshot example shows `[Tag & Watch] [Dismiss]` but issue-based items also support `assign` and `snooze`.

**Fix:** Clarify in §5 (Cold Client Snapshot):

> **Snapshot Actions:**
> - Snapshot respects the same `actions` array returned by `GET /api/inbox` for each item
> - Available actions depend on item type and state (same rules as inbox)
> - Snapshot is a filtered view of inbox, not a restricted one

---

## 4. Spec Hygiene

### 4.1 Rename `unread` → `unprocessed` in API

**Problem:** UI label is "Unprocessed" but API field is `unread`.

**Fix:** Amend §7.2 (GET /api/inbox response):

```json
{
  "counts": {
    "unprocessed": 5,  // Renamed from "unread"
    "proposed": 12,
    "snoozed": 3
  }
}
```

> **Deprecation:** Accept `unread` as read-only alias for one release cycle.

---

### 4.2 Evidence Schema — Source System Invariant

**Problem:** `evidence.source_system` should be constrained to canonical sources.

**Fix:** Add to §6.16:

> **Evidence Source System (Hard Invariant):**
> - `evidence.source_system` MUST be one of: `asana`, `gmail`, `gchat`, `calendar`, `minutes`, `xero`, `system`
> - Must match the context of the parent entity (signal source, issue type, etc.)
> - Validation: reject ingestion if source_system not in canonical list

---

### 4.3 Xero Evidence — URL Always Null

**Problem:** Spec says "never render Xero URL" but best practice is to never store it.

**Fix:** Add to §6.10:

> **Xero Evidence URL Rule:**
> - For `source_system = 'xero'`, set `evidence.url = null` at ingestion time
> - Never store Xero URLs — prevents accidental rendering by generic components
> - Display uses invoice number only (user copies to Xero search)

---

## 5. Additional Test Cases (Required)

Add to IMPLEMENTATION_CHECKLIST.md:

| # | Test Case | Section |
|---|-----------|---------|
| 84 | Suppressed issue UI: verify `available_actions = ['unsuppress']` only | 6.5, 7.6 |
| 85 | Snooze uses local midnight: verify `snooze_until` equals local midnight conversion | 1.6, 0.1 |
| 86 | Invoice identity: two invoices with same number but different `source_id` do not collide in suppression | 6.10, 1.8 |
| 87 | Concurrent detector upsert: simulate two workers; assert exactly one active inbox item | 6.4, 6.13 |
| 88 | `state=all` returns 400: verify invalid_state error | 7.2 |
| 89 | Issue snooze dialog shows "Health impact removed" copy | 6.5 |
| 90 | `linked_open_tasks = 0` after linking check: returns score=100 with gating | 6.6 |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v2.1.1 | 2025-02-08 | Errata document created; 15 amendments |

---

## Application

These amendments should be applied to CLIENT-UI-SPEC-v2.1-FINAL.md as a patch. After review, merge into v2.2.
