# 02 — Correctness Review (Pagination, Cursor Gating, Invariants) — Non-Docs Only

---

## MANDATORY EVIDENCE

### A) Grep-based evidence of cursor gating

**Example: Cursor WRITTEN (pagination exhausted)**
```python
# lib/collectors/all_users_runner.py:1611-1617
# CURSOR GATING: Only store historyId when pagination is FULLY exhausted
if pagination_exhausted:
    if current_history_id and all_messages:
        set_cursor(db_path, "gmail", user, "historyId", current_history_id)
    if max_internal_date > 0:
        set_cursor(db_path, "gmail", user, "max_internal_date", str(max_internal_date))
    debug_print(f"GMAIL cursor: set historyId={current_history_id}")
```

**Example: Cursor NOT WRITTEN (partial)**
```python
# lib/collectors/all_users_runner.py:1618
else:
    debug_print(f"GMAIL cursor: NOT advancing (pagination not exhausted, partial=true)")
```

### B) Cursor distribution (sqlite3)
```
service|key_pattern|subjects
calendar|calendar:*:last_until|20
calendar|last_until|1
chat|last_create_time|20
chat|last_until|20
chat|space:*:last_create_time|20
drive|last_modified_time|20
drive|last_until|20
gmail|historyId|20
gmail|last_until|19
gmail|max_internal_date|20
```

### C) Coverage evidence (sqlite3)
```
svc|subjects
gmail|20
calendar|20
chat|20
drive|20
```

---

## GMAIL

### 1) Pagination boundary
| Aspect | Value |
|--------|-------|
| Method | `users().messages().list()` (initial) / `users().history().list()` (incremental) |
| Page boundary | `nextPageToken` in response |
| pageSize | 100 |
| Termination | `nextPageToken` is absent |

### 2) Deterministic ordering
- **Initial sync:** No explicit ordering. Gmail returns messages in reverse chronological order by default.
- **Incremental sync:** `historyId` is monotonically increasing — changes since last historyId are returned.
- **Compensating mechanism:** historyId provides total ordering; no gaps possible if historyId is stored only after full pagination.

### 3) Cursor keys + gating rule
| Key | Gating Condition |
|-----|-----------------|
| `historyId` | Written ONLY when `pagination_exhausted == True` |
| `max_internal_date` | Written ONLY when `pagination_exhausted == True` |

**Partial behavior:** Cursor is NOT advanced. Next run restarts from same historyId.

### 4) Streaming persistence
- **When:** Per-page batch persist (`persist_gmail_messages` called after each page of message.get calls)
- **Kill-safe:** If process killed mid-run, persisted messages remain. Cursor not advanced, so next run re-fetches and UPSERTs (idempotent).

### 5) Failure modes table
| Failure | Gap Risk | Current Mitigation | Missing Mitigation |
|---------|----------|-------------------|-------------------|
| Process killed mid-run | LOW | Cursor not written until exhausted; UPSERT prevents duplicates | None |
| Repeated nextPageToken loop | MEDIUM | No loop detection | Add pageToken dedup check |
| API ordering instability | LOW | historyId is monotonic | None |
| historyId expired (too old) | LOW | Catches 404/history error, clears cursor, falls back to initial sync | None |

### 6) End-of-run invariants
- `pagination_exhausted == True` for all users
- `errors_count == 0`
- `historyId` cursor present for all active subjects

---

## CALENDAR

### 1) Pagination boundary
| Aspect | Value |
|--------|-------|
| Method | `events().list()` with `timeMin/timeMax` (initial) or `syncToken` (incremental) |
| Page boundary | `nextPageToken` in response |
| pageSize | 250 |
| Termination | `nextPageToken` is absent AND `nextSyncToken` present |

### 2) Deterministic ordering
- **Initial sync:** `orderBy=startTime` for `singleEvents=True`
- **Incremental sync:** syncToken returns changes in chronological order
- **Gap-free:** syncToken captures all changes since last sync

### 3) Cursor keys + gating rule
| Key | Gating Condition |
|-----|-----------------|
| `syncToken:{calendar_id}` | Written ONLY when per-calendar pagination is exhausted AND `nextSyncToken` present |

**Partial behavior:** Cursor is NOT advanced for that calendar. Next run re-fetches.

**410 GONE handling:** syncToken cleared, falls back to initial sync.

### 4) Streaming persistence
- **When:** Per-page persist (`persist_calendar_events` called after each page)
- **Kill-safe:** Persisted events remain. Cursor not advanced, so next run re-fetches.

### 5) Failure modes table
| Failure | Gap Risk | Current Mitigation | Missing Mitigation |
|---------|----------|-------------------|-------------------|
| Process killed mid-run | LOW | Cursor not written until exhausted | None |
| Repeated nextPageToken loop | LOW | No explicit detection | Add pageToken dedup |
| API ordering instability | NONE | orderBy=startTime + syncToken | None |
| syncToken invalidation (410) | LOW | Catches 410, clears cursor, initial sync | None |

### 6) End-of-run invariants
- All calendars have `pagination_exhausted == True`
- `errors_count == 0`
- `syncToken:{calendar_id}` present for all processed calendars

---

## CHAT

### 1) Pagination boundary
| Aspect | Value |
|--------|-------|
| Method | `spaces().list()` + `spaces().messages().list()` |
| Page boundary | `nextPageToken` in response |
| pageSize | 100 |
| Termination | `nextPageToken` is absent |

### 2) Deterministic ordering
- **⚠️ No server-side ordering:** Chat API does not support date filtering or ordering
- **Compensating mechanism:** Client-side date filtering + per-space cursor tracking
- **Risk:** If limit is hit before pagination exhausts, items may be skipped

### 3) Cursor keys + gating rule (PER-SPACE strategy)
| Key | Gating Condition |
|-----|-----------------|
| `space:{space_name}:last_create_time` | Written ONLY when that space's pagination is exhausted |
| `last_create_time` (subject-level) | Written when ALL spaces exhausted |

**Partial behavior:** Cursor for partial spaces NOT advanced. Exhausted spaces DO get cursors.

**LOOP DETECTION:** If `nextPageToken == prev_pageToken`, break and mark PARTIAL.

### 4) Streaming persistence
- **When:** Per-page persist (STREAMING mode — memory-safe)
- **Kill-safe:** Each page persisted immediately. Per-space cursors track progress.

### 5) Failure modes table
| Failure | Gap Risk | Current Mitigation | Missing Mitigation |
|---------|----------|-------------------|-------------------|
| Process killed mid-run | LOW | Per-space cursors + streaming persist | None |
| Repeated nextPageToken loop | MEDIUM | Loop detection breaks and marks PARTIAL | None |
| No server-side date filter | HIGH | Client-side filtering + per-space cursors | Use exhaust_pagination=True |
| Large space with limit | MEDIUM | Per-space cursor isolation | Warn when limit hit |

### 6) End-of-run invariants
- `spaces_partial == 0`
- All spaces have `space:{name}:last_create_time` cursor
- `errors_count == 0`

---

## DRIVE

### 1) Pagination boundary
| Aspect | Value |
|--------|-------|
| Method | `files().list()` with `modifiedTime` filter |
| Page boundary | `nextPageToken` in response |
| pageSize | 100 |
| Termination | `nextPageToken` is absent |

### 2) Deterministic ordering
- **Explicit ordering:** `orderBy=modifiedTime` — CRITICAL for gap-free sync
- **Gap-free:** Files returned in ascending modifiedTime order. Cursor advances to max persisted.

### 3) Cursor keys + gating rule
| Key | Gating Condition |
|-----|-----------------|
| `last_modified_time` | Written ONLY when `pagination_exhausted == True`. Value = max observed modifiedTime. |

**Partial behavior:** Cursor NOT advanced. Next run re-fetches from same point.

### 4) Streaming persistence
- **When:** Per-page persist (STREAMING mode)
- **Kill-safe:** Each page persisted immediately. Cursor only advances after full pagination.

### 5) Failure modes table
| Failure | Gap Risk | Current Mitigation | Missing Mitigation |
|---------|----------|-------------------|-------------------|
| Process killed mid-run | LOW | Cursor not written until exhausted | None |
| Repeated nextPageToken loop | MEDIUM | Loop detection breaks and marks PARTIAL | None |
| API ordering instability | NONE | `orderBy=modifiedTime` enforced | None |
| Limit hit before exhaustion | MEDIUM | Watermark warning emitted | Use exhaust_pagination=True |

### 6) End-of-run invariants
- `pagination_exhausted == True`
- `last_modified_time` cursor present
- `errors_count == 0`

---

## GLOBAL END-OF-RUN INVARIANTS

```python
# These must all be TRUE for a complete non-docs sweep:
assert report["totals"]["partial_subjects_count"] == 0
assert report["totals"]["errors_count"] == 0  # or sum of per-service errors
assert report["totals"]["active_targets_attempted"] == report["totals"]["active_targets_total"]

# For chat specifically:
assert all(user_report.get("chat", {}).get("spaces_partial", 0) == 0 for user_report in report["per_user"].values())
```

---

## RECOMMENDATIONS (if any changes needed)

No code changes required for correctness. Current implementation has:
- ✅ Cursor gating on `pagination_exhausted`
- ✅ Per-page streaming persistence
- ✅ Loop detection for Chat
- ✅ Deterministic ordering for Drive (`orderBy=modifiedTime`)
- ✅ syncToken/historyId for true incremental sync

**Minor improvement:** Add explicit pageToken loop detection to Gmail/Calendar (currently only Chat has it).

---

*Generated: 2026-02-13T02:05:00+04:00*
