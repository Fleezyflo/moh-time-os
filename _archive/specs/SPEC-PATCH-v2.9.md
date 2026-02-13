# CLIENT-UI-SPEC Patch — v2.8 → v2.9

**Date:** 2026-02-09
**Summary:** Address hard inconsistencies, missing invariants, and spec gaps identified in review.

---

## Patch Summary

| # | Area | Change | Section(s) Affected |
|---|------|--------|---------------------|
| 1 | Resolved state | Eliminate contradiction; `resolved` is NEVER persisted or returned | §0.3, §6.5, §7.6 |
| 2 | aggregation_key | Add column to `issues` table for detector upsert | §6.14 |
| 3 | attention_age_start_at | Define canonical age sort field | NEW §0.5, §1.9, §7.10 |
| 4 | Unprocessed count | Add count chip using `is_unprocessed()` | §1.9, §7.10 |
| 5 | available_actions | Add to InboxItem + Issue response payloads | §7.6, §7.10 |
| 6 | Detector window boundaries | Explicit org-local midnight boundaries | NEW §6.17 |
| 7 | Ordering validation canary | Add semantic validation beyond format | §0.1 |
| 8 | resolution_reason enum | Standardize values and UI label mapping | §0.4, §1.4 |
| 9 | Resurfaced badge | UI treatment for resurfaced items | §1.10 |
| 10 | EvidenceRenderer tests | Add CI contract tests | §6.16 |

---

## 1. Resolved State — Eliminate Contradiction

### Problem

§0.3 says `resolved` is "internal only—never returned by list endpoints," but the state diagram in §6.5 shows it as a distinct state and the transition table includes edges to/from it.

### Patch

**§0.3 — Update UI Label Mapping table:**

```diff
| API State/Value | UI Label | Display Bucket |
|-----------------|----------|----------------|
- | `resolved` | *(internal only — never returned by list endpoints; see §6.5)* | — |
+ | `resolved` | *(conceptual only — never persisted, never returned; see §6.5)* | — |
```

**§6.5 — Add explicit "resolved is not a state" callout after state diagram:**

```markdown
**API Invariant (Hard Rule):**

`POST /api/issues/:id/transition { action: "resolve" }` transitions the issue directly to `regression_watch` in a single atomic transaction. The state `resolved` is logged in `issue_transitions` for audit but is **never stored** in `issues.state` and **never returned** by any API endpoint.

```sql
-- This constraint MUST be present on the issues table
ALTER TABLE issues ADD CONSTRAINT chk_no_resolved_state
  CHECK (state != 'resolved');
```

**Why?** If the transaction were split (persist `resolved`, then persist `regression_watch`), a failure between steps would leak issues in an invisible state — neither open nor closed. The atomic approach eliminates this risk.
```

**§6.5 — Update States table:**

| # | State | API Value | Definition |
|---|-------|-----------|------------|
| 7 | `resolved` | *(never persisted — see API Invariant above)* | Conceptual; logged in audit trail only |

**§7.6 — Update available_actions table:**

```diff
- | `resolved` | *(internal-only — never returned by API; use regression_watch)* |
+ | `resolved` | *(never returned — resolve action persists regression_watch directly)* |
```

---

## 2. aggregation_key — Add to Issues Table

### Problem

§6.14 defines `financial_issue_key = sha256(client_id:engagement_id:invoice_source_id)` conceptually but doesn't add a column to enforce uniqueness or enable upsert.

### Patch

**§6.14 — Add to `issues` table schema:**

```sql
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'detected',
  severity TEXT NOT NULL,

+ -- Aggregation (required for detector upsert)
+ aggregation_key TEXT NOT NULL,           -- deterministic hash for dedup/upsert

  -- Scoping
  client_id TEXT NOT NULL REFERENCES clients(id),
  ...
);

+ -- Unique constraint: at most one non-suppressed issue per aggregation_key and type
+ CREATE UNIQUE INDEX idx_issues_aggregation_unique
+   ON issues (type, aggregation_key)
+   WHERE suppressed = FALSE;
```

**Add new section — §6.14.1 Aggregation Key Computation:**

```markdown
### 6.14.1 Aggregation Key Computation

Each issue type has a deterministic aggregation key. Detectors MUST upsert by this key.

| Issue Type | Aggregation Key Formula |
|------------|------------------------|
| `financial` | `sha256("financial:" + client_id + ":" + engagement_id + ":" + invoice_source_id)` |
| `schedule_delivery` | `sha256("schedule:" + client_id + ":" + engagement_id)` |
| `communication` | `sha256("comm:" + client_id + ":" + brand_id)` |
| `risk` | `sha256("risk:" + client_id + ":" + engagement_id + ":" + rule_triggered)` |

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
```

---

## 3. attention_age_start_at — Define Canonical Age Sort Field

### Problem

"Age" sorting is ambiguous. Multiple timestamps exist: `proposed_at` (immutable), `resurfaced_at` (on snooze expiry), `last_refreshed_at` (detector enrichment). Spec doesn't define which to use.

### Patch

**Add new section — §0.5 Attention Age (Canonical):**

```markdown
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

**Invariant:** `attention_age_start_at` is NEVER null (proposed_at is always set on creation).
```

**§1.9 — Update Sort definition:**

```diff
Sort:   [Severity ▼] [Age ▼] [Client ▼]
+
+ **Age Sort Definition:**
+ - Uses `attention_age_start_at` (= `resurfaced_at ?? proposed_at`)
+ - Descending = oldest first (longest waiting for attention)
+ - Ascending = newest first (most recently surfaced)
```

**§7.10 — Add to InboxItem response:**

```diff
{
  "id": "uuid",
  "type": "issue",
  "severity": "critical",
  "state": "proposed",
  "read_at": null,
  "proposed_at": "2026-01-13T10:00:00.000Z",
+ "resurfaced_at": null,                    // Set when snooze expired
+ "attention_age_start_at": "2026-01-13T10:00:00.000Z",  // Server-computed: resurfaced_at ?? proposed_at
  ...
}
```

---

## 4. Unprocessed Count — Add to Header

### Problem

Header shows state-based counts (Needs Attention, Snoozed) but not unprocessed count. `is_unprocessed()` is defined but not surfaced in counts.

### Patch

**§1.9 — Update Inbox Counts:**

```diff
Control Room
├── Needs Attention: 12       ← state = 'proposed'
│   ├── Critical: 2
│   ├── High: 5
│   ├── Medium: 3
│   └── Info: 2
+ │   └── Unprocessed: 8      ← is_unprocessed() = true (within proposed)
├── Snoozed: 3                ← state = 'snoozed'
│   └── Returning by tomorrow: 1
└── Recently Actioned: 8      ← terminal states, last 7 days
```

**Count definition:**

```python
def count_unprocessed() -> int:
    """Count proposed items that are unprocessed (new or resurfaced)."""
    return query("""
        SELECT COUNT(*) FROM inbox_items
        WHERE state = 'proposed'
          AND (read_at IS NULL OR read_at < resurfaced_at)
    """)
```

**§7.10 — Update counts response:**

```diff
"counts": {
  "scope": "global",
  "needs_attention": 12,
  "snoozed": 3,
  "snoozed_returning_soon": 1,
  "recently_actioned": 8,
- "unprocessed": 5,
+ "unprocessed": 8,                // Uses is_unprocessed(): read_at IS NULL OR read_at < resurfaced_at
+ "unprocessed_scope": "proposed", // Clarify: unprocessed is subset of proposed
  "by_severity": {...},
  "by_type": {...}
}
```

---

## 5. available_actions — Add to Response Payloads

### Problem

Actions depend on state, but spec doesn't require server to compute and return them. Frontend must infer, leading to drift.

### Patch

**§7.10 — Update InboxItem response (already partially present):**

Clarify that `actions` is computed server-side and REQUIRED:

```markdown
**available_actions (Required):**

Server MUST compute and return `available_actions: string[]` on every InboxItem:

```python
def compute_inbox_actions(item: InboxItem) -> list[str]:
    """Server-computed actions based on item type and state."""
    if item.state not in ('proposed', 'snoozed'):
        return []  # Terminal items are read-only

    match item.type:
        case 'issue':
            return ['tag', 'assign', 'snooze', 'dismiss']
        case 'flagged_signal':
            return ['tag', 'assign', 'snooze', 'dismiss']
        case 'orphan':
            return ['link', 'create', 'dismiss']
        case 'ambiguous':
            return ['select', 'dismiss']
```

Frontend MUST NOT derive actions from type/state locally — always use the server-provided list.
```

**§7.6 — Add to Issues response:**

```diff
{
  "id": "uuid",
  "type": "financial",
  "severity": "critical",
  "state": "surfaced",
  "title": "Invoice 45 days overdue",
  "evidence": {...},
  "created_at": "2026-01-10T10:00:00.000Z",
- "available_actions": ["acknowledge", "snooze", "resolve"]  // State-dependent
+ "available_actions": ["acknowledge", "snooze", "resolve"],  // REQUIRED, server-computed
+ "assigned_to": null,                                        // null or { id, name }
+ "suppressed": false
}
```

Add explicit computation rules (already present, make mandatory):

```markdown
**available_actions Computation (Required):**

1. If `suppressed = true` → return `["unsuppress"]` (bypass all other logic)
2. Else, compute by state:

| State | available_actions |
|-------|-------------------|
| `surfaced` | `["acknowledge", "assign", "snooze", "resolve"]` |
| `acknowledged` | `["assign", "snooze", "resolve"]` |
| `addressing` | `["snooze", "resolve", "escalate"]` |
| `awaiting_resolution` | `["resolve", "escalate"]` |
| `snoozed` | `["unsnooze"]` |
| `regression_watch` | `[]` |
| `closed` | `[]` |
| `regressed` | `["acknowledge", "assign", "snooze", "resolve"]` |

Server MUST return this field; frontend MUST NOT compute locally.
```

---

## 6. Detector Window Boundaries — Explicit Org-Local Definition

### Problem

Spec mentions `window_days` for detector aggregation but doesn't specify whether it's rolling 24-hour or org-local day boundaries.

### Patch

**Add new section — §6.17 Detector Window Boundaries:**

```markdown
### 6.17 Detector Window Boundaries (Canonical)

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
```

---

## 7. Ordering Validation Canary — Add Semantic Validation

### Problem

Current startup canary checks timestamp format (24-char) but not semantic validity (e.g., `2026-99-99T00:00:00.000Z` passes length check but is invalid).

### Patch

**§0.1 — Update validate_all_timestamps to include ordering assertions:**

```diff
def validate_all_timestamps():
    """
-   Full semantic validation on startup — catches both shape AND value errors.
+   Full semantic validation on startup — catches shape, value, AND ordering errors.
    """
    violations = []
    for table, columns in TIMESTAMP_COLUMNS.items():
        for col in columns:
            rows = query(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
            for row in rows:
                if not validate_timestamp(row[col]):
                    violations.append((table, col, row.id, row[col], 'invalid_format'))

+   # Ordering validation (cross-field invariants)
+   ordering_violations = validate_timestamp_ordering()
+   violations.extend(ordering_violations)

    if violations:
        alert(f"CRITICAL: {len(violations)} timestamp violations detected")
        for table, col, id, val, reason in violations[:10]:
            log(f"  {table}.{col} id={id}: '{val}' ({reason})")
        return False
    return True

+ def validate_timestamp_ordering() -> list:
+     """
+     Validate cross-field timestamp ordering invariants.
+     These invariants ensure lexicographic comparisons work correctly.
+     """
+     violations = []
+
+     # Inbox items: resurfaced_at >= proposed_at (if set)
+     rows = query("""
+         SELECT id, proposed_at, resurfaced_at FROM inbox_items
+         WHERE resurfaced_at IS NOT NULL AND resurfaced_at < proposed_at
+     """)
+     for row in rows:
+         violations.append(('inbox_items', 'resurfaced_at', row.id, row.resurfaced_at, 'resurfaced_before_proposed'))
+
+     # All tables: updated_at >= created_at
+     for table in ['inbox_items', 'issues', 'signals', 'engagements']:
+         rows = query(f"""
+             SELECT id, created_at, updated_at FROM {table}
+             WHERE updated_at < created_at
+         """)
+         for row in rows:
+             violations.append((table, 'updated_at', row.id, row.updated_at, 'updated_before_created'))
+
+     # Issues: resolved_at >= created_at (if set)
+     rows = query("""
+         SELECT id, created_at, resolved_at FROM issues
+         WHERE resolved_at IS NOT NULL AND resolved_at < created_at
+     """)
+     for row in rows:
+         violations.append(('issues', 'resolved_at', row.id, row.resolved_at, 'resolved_before_created'))
+
+     return violations
```

---

## 8. resolution_reason Enum — Standardize Values

### Problem

`inbox_items.resolution_reason` values are scattered across the spec. Need canonical enum and UI label mapping.

### Patch

**§0.4 — Add resolution_reason enum table:**

```markdown
**resolution_reason Enum (inbox_items):**

| API Value | UI Label (Recently Actioned) | Trigger |
|-----------|------------------------------|---------|
| `tag` | "Tagged & watching" | Inbox Tag action |
| `assign` | "Assigned" | Inbox Assign action |
| `issue_snoozed_directly` | "Issue snoozed" | Issue snooze from Client Page |
| `issue_resolved_directly` | "Issue resolved" | Issue resolve from Client Page |
| `issue_closed_directly` | "Issue closed" | Issue closed (end of regression_watch) |
| `issue_acknowledged_directly` | "Issue acknowledged" | Issue acknowledge from Client Page |
| `issue_assigned_directly` | "Issue assigned" | Issue assign from Client Page |
| `superseded` | "Superseded" | Newer inbox item replaced this one |

**DB Constraint:**

```sql
ALTER TABLE inbox_items ADD CONSTRAINT chk_resolution_reason_enum
  CHECK (resolution_reason IS NULL OR resolution_reason IN (
    'tag', 'assign', 'issue_snoozed_directly', 'issue_resolved_directly',
    'issue_closed_directly', 'issue_acknowledged_directly',
    'issue_assigned_directly', 'superseded'
  ));
```
```

**§1.4 — Update inbox state transition descriptions to use enum values:**

Already correct; just ensure consistency.

---

## 9. Resurfaced Badge — UI Treatment

### Problem

Items that resurfaced from snooze show `read_at` set (from before snooze), so they appear "processed" even though they need re-attention.

### Patch

**§1.10 — Add Resurfaced styling:**

```diff
**UI behavior:**
- Unprocessed items (`read_at IS NULL`) show bold styling
+ Unprocessed items (per `is_unprocessed()`) show bold styling
+ Resurfaced items show a "Resurfaced" badge when `resurfaced_at IS NOT NULL AND read_at < resurfaced_at`
- UI label: "Unprocessed" (not "Unread")
+ UI labels:
+   - "Unprocessed" — for never-read items
+   - "Resurfaced" badge — for items that returned from snooze and haven't been re-acknowledged
```

**Add Resurfaced Badge Component spec:**

```markdown
**Resurfaced Badge (Required):**

When displaying inbox items, show a "Resurfaced" badge if:
- `resurfaced_at IS NOT NULL` AND
- `read_at IS NULL OR read_at < resurfaced_at`

```typescript
function shouldShowResurfacedBadge(item: InboxItem): boolean {
  if (!item.resurfaced_at) return false;
  if (!item.read_at) return true;  // Also unprocessed, but resurfaced takes priority for badge
  return item.read_at < item.resurfaced_at;
}
```

**UI Treatment:**
- Badge text: "Resurfaced"
- Badge color: Amber (warning tone, needs re-attention)
- Position: After title, before severity badge
- Tooltip: "This item returned from snooze and hasn't been re-acknowledged"

**Row Styling for Resurfaced:**
- Use same bold styling as unprocessed items
- `is_unprocessed()` already handles this; use it for styling decisions
```

---

## 10. EvidenceRenderer Tests — Add CI Contract Tests

### Problem

EvidenceRenderer rules are defined but no CI enforcement to catch violations.

### Patch

**§6.16 — Add test requirements:**

```markdown
**EvidenceRenderer Contract Tests (Required):**

Add the following tests to CI:

```python
# Test 1: Xero evidence never renders links
def test_xero_evidence_no_links():
    evidence = {
        'source_system': 'xero',
        'url': 'https://go.xero.com/...',  # Should be stripped, but test defense
        'display_text': 'INV-1234 · AED 35,000',
        'payload': {
            'number': 'INV-1234',
            'invoice_url': 'https://...'  # Nested URL
        }
    }
    rendered = EvidenceRenderer(evidence).render()
    assert 'href' not in rendered
    assert '↗' not in rendered
    assert 'https://' not in rendered

# Test 2: Minutes uses payload URLs only, ignores top-level url
def test_minutes_uses_payload_urls():
    evidence = {
        'source_system': 'minutes',
        'url': 'https://should-be-ignored.com',
        'display_text': 'Q1 Review · 2026-01-14',
        'payload': {
            'recording_url': 'https://meet.google.com/rec/abc',
            'transcript_url': None
        }
    }
    rendered = EvidenceRenderer(evidence).render()
    assert 'https://meet.google.com/rec/abc' in rendered
    assert 'should-be-ignored' not in rendered

# Test 3: Asana/Gmail/GChat/Calendar render links when url present
@pytest.mark.parametrize('source_system', ['asana', 'gmail', 'gchat', 'calendar'])
def test_linkable_sources_render_urls(source_system):
    evidence = {
        'source_system': source_system,
        'url': f'https://{source_system}.example.com/item/123',
        'display_text': 'Test item'
    }
    rendered = EvidenceRenderer(evidence).render()
    assert 'href' in rendered
    assert f'https://{source_system}.example.com' in rendered

# Test 4: Linkable sources don't render link when url is null
@pytest.mark.parametrize('source_system', ['asana', 'gmail', 'gchat', 'calendar'])
def test_linkable_sources_no_link_when_null(source_system):
    evidence = {
        'source_system': source_system,
        'url': None,
        'display_text': 'Test item'
    }
    rendered = EvidenceRenderer(evidence).render()
    assert 'href' not in rendered
    assert '↗' not in rendered
```

**String Search Ban Test:**

```python
def test_ui_copy_blacklist():
    """Scan all UI strings for forbidden terms."""
    FORBIDDEN = ['Read', 'Unread', 'watch loop', 'Monitoring']
    EXCEPTIONS = ['Recently Actioned']  # "Actioned" contains "tion" not "Read"

    ui_strings = load_all_ui_strings()  # Implementation-specific
    for string in ui_strings:
        for term in FORBIDDEN:
            if term.lower() in string.lower():
                if not any(exc in string for exc in EXCEPTIONS):
                    pytest.fail(f"Forbidden term '{term}' found in: {string}")
```
```

---

## Version Bump

Update spec header:

```diff
- **Status:** v2.8
+ **Status:** v2.9
```

Add changelog entry:

```markdown
## Changelog

### v2.9 (2026-02-09)
- **BREAKING:** `resolved` state is never persisted; resolve action persists `regression_watch` directly
- Added `aggregation_key` column to `issues` table for detector upsert
- Defined `attention_age_start_at` for canonical age sorting
- Added `unprocessed` count to header (using `is_unprocessed()`)
- Made `available_actions` required in InboxItem and Issue API responses
- Documented detector window boundaries (org-local midnight)
- Extended timestamp validation canary to include ordering assertions
- Standardized `resolution_reason` enum values
- Added "Resurfaced" badge UI treatment
- Added EvidenceRenderer CI contract tests
```

---

## Implementation Checklist

- [ ] Add `chk_no_resolved_state` constraint to issues table
- [ ] Add `aggregation_key` column to issues table with unique index
- [ ] Update all detectors to compute and use `aggregation_key`
- [ ] Add `attention_age_start_at` to InboxItem API response
- [ ] Add `unprocessed` count to `/api/inbox/counts`
- [ ] Make `available_actions` required in all issue/inbox responses
- [ ] Update detector code to use `detector_window_start()` helper
- [ ] Add `validate_timestamp_ordering()` to startup canary
- [ ] Add `chk_resolution_reason_enum` constraint
- [ ] Implement "Resurfaced" badge in frontend
- [ ] Add EvidenceRenderer contract tests to CI
- [ ] Run migration to add `aggregation_key` (backfill existing issues)
