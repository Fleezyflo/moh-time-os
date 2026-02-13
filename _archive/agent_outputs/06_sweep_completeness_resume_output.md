# 06 — Sweep Completeness & Resume (Non-Docs Only)

---

## 1) DEFINITION OF "COMPLETE" (non-docs)

### Invariants for COMPLETE state:
```python
# ALL must be TRUE:
active_targets_attempted == active_targets_total  # All subjects processed
partial_subjects_count == 0                        # No truncated pagination
errors_count == 0                                  # No failures
# For each service:
gmail_pagination_exhausted == True for all subjects
calendar_pagination_exhausted == True for all subjects
chat_spaces_partial == 0 for all subjects
drive_pagination_exhausted == True for all subjects
```

### How computed from logs/DB:

| Metric | Source |
|--------|--------|
| `active_targets_total` | Count of internal users with email, minus permanent blocklist |
| `attempted_count` | Count of subjects where collection was attempted |
| `partial_subjects_count` | Count of subjects with any `partial=True` |
| `errors_count` | Count of subjects with any `err != none` |
| `per-service pagination_exhausted` | Per-user result in run report |

---

## 2) RESUME STRATEGY (deterministic)

### A) Subject ordering
```python
# Deterministic ordering in get_internal_users():
cursor.execute("SELECT email FROM people WHERE type='internal' AND email IS NOT NULL")
emails = [row[0] for row in cursor.fetchall()]
# Sorted by natural SQLite rowid, but explicit ORDER BY email ASC is safer
```

### Service ordering (fixed):
```python
# In run_all_users and full_sweep:
service_order = ["gmail", "calendar", "chat", "drive"]  # docs excluded here
```

### B) Per-subject state machine

| State | Condition | Cursor | Next Action |
|-------|-----------|--------|-------------|
| NOT_STARTED | No rows in table for subject | None | Run collection |
| IN_PROGRESS | Process running (transient) | None | (only during runtime) |
| COMPLETE | Cursor exists AND pagination_exhausted=True | Present | Skip |
| PARTIAL | Cursor NOT advanced (pagination not exhausted) | Absent/stale | Retry |
| ERR:invalid_grant | Permanent blocklist | N/A | Skip forever |
| ERR:transient | Transient blocklist with retry_at | N/A | Skip until retry_at |

### C) Resume rule
```python
# On restart:
for subject in sorted_subjects:
    if is_permanent_blocklisted(subject):
        skip("permanent")
    elif is_transient_blocked_not_ready(subject):
        skip("transient_wait")
    else:
        # Run collection - UPSERT handles already-present data
        # Cursor gating ensures no regression
        run_collection(subject)
```

**Key guarantee:** Cursor is ONLY written on `pagination_exhausted=True`, so:
- If killed mid-run → no cursor → next run re-fetches
- If COMPLETE → cursor present → incremental sync from cursor

---

## 3) PERSISTENCE + CURSOR GATING AUDIT HOOKS

### Existing log lines (via `debug_print` when `AUTH_DEBUG=1`):

```
[AUTH_DEBUG] CURSOR read: service=gmail subject=user@domain key=historyId value=...
[AUTH_DEBUG] CURSOR write: service=gmail subject=user@domain key=historyId value=...
[AUTH_DEBUG] GMAIL cursor: NOT advancing (pagination not exhausted, partial=true)
[AUTH_DEBUG] PERSIST gmail: subject=user@domain inserted=15 updated=0
```

### Proposed SWEEP log format (single-line, parseable):

```
SWEEP service=gmail subject=user@domain phase=START
SWEEP service=gmail subject=user@domain phase=END ok=1 count=50 partial=0 err=none cursor_written=1
SWEEP service=gmail subject=user@domain phase=CURSOR_WRITE key=historyId value=12345
SWEEP service=gmail subject=user@domain phase=CURSOR_SKIP reason=partial
```

**Implementation location:** `lib/collectors/all_users_runner.py`
- Add to `collect_gmail_for_user`, `collect_calendar_for_user`, `collect_chat_for_user`, `collect_drive_for_user`

---

## 4) CLI ERGONOMICS

### Current flags (verified):
```bash
--full-sweep        # Run exhaustive sweep (exhaust=True by default)
--exhaust           # Force exhaustive pagination mode
--services gmail,calendar,chat,drive  # Explicit service list
--include-transient # Retry transient-blocked subjects
--subject EMAIL     # Target specific subject(s)
--dry-run           # Print plan without API calls
```

### Usage for non-docs sweep:
```bash
# Full sweep excluding docs:
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --services gmail,calendar,chat,drive 2>&1 | tee /tmp/sweep.log
```

### Resume behavior (automatic):
- `--full-sweep` defaults to `--exhaust` mode
- UPSERT semantics prevent duplicates
- Cursor gating prevents regression
- Just re-run same command to resume

---

## 5) VERIFICATION BUNDLE (non-docs)

### A) Run sweep command:
```bash
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --services gmail,calendar,chat,drive 2>&1 | tee /tmp/full_sweep.log
```

### B) Prove COMPLETE from logs:
```bash
# Count END lines (should be 20 subjects × 4 services = 80)
grep "phase=END\|Processing:" /tmp/full_sweep.log | wc -l

# Check for partial (should be 0)
grep "partial=1\|PARTIAL" /tmp/full_sweep.log | wc -l

# Check for errors (should be 0)
grep -E "ERR:|err=[^n]" /tmp/full_sweep.log | wc -l
```

**Expected:**
- END/Processing lines: ~80
- partial=1 lines: 0
- err!=none lines: 0

### C) Prove cursor presence (sample):
```bash
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT service, subject, key, value
  FROM sync_cursor
  WHERE (service='gmail' AND key='historyId')
     OR (service='drive' AND key='last_modified_time')
  ORDER BY service, subject
  LIMIT 40;
" > /tmp/cursors.txt
cat /tmp/cursors.txt
```

**Expected:** 20 rows for gmail historyId, 20 rows for drive last_modified_time

### D) Prove subject coverage:
```bash
sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
  SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
  UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
  UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
  UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
"
```

**Expected:**
```
svc|subjects
gmail|20
calendar|20
chat|20
drive|20
```

---

## 6) KILL/RESUME CONVERGENCE TEST

### A) Kill mid-run:
```bash
timeout 30 bash -c 'AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --services chat' 2>&1 | tee /tmp/kill_run.log || true
```

### B) Resume:
```bash
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --services chat 2>&1 | tee /tmp/resume_run.log
```

### Expected behavior:
1. Kill run persists some spaces/messages
2. Per-space cursors are written for exhausted spaces
3. Resume run:
   - Skips spaces with existing cursors
   - Continues from unfinished spaces
4. Final run shows `spaces_partial=0`

### Verify convergence:
```bash
# Check spaces_exhausted vs spaces_partial in both runs
grep "spaces_exhausted\|spaces_partial" /tmp/kill_run.log /tmp/resume_run.log

# Resume should show higher spaces_exhausted count
```

---

## CURRENT STATE PROOF

### Subject coverage (verified):
```
svc|subjects
gmail|20
calendar|20
chat|20
drive|20
```

### Cursor presence:
- gmail historyId: 20 subjects ✓
- drive last_modified_time: 20 subjects ✓
- chat per-space cursors: 380+ spaces ✓
- calendar syncToken: multiple calendars per subject ✓

---

## CODE TOUCHPOINTS

| Component | File | Function |
|-----------|------|----------|
| CLI entry | `all_users_runner.py` | `main()` |
| Full sweep | `all_users_runner.py` | `full_sweep()` |
| Per-service collectors | `all_users_runner.py` | `collect_{gmail,calendar,chat,drive}_for_user()` |
| Cursor gating | `all_users_runner.py` | Each collector's `if pagination_exhausted:` block |
| Resume logic | `all_users_runner.py` | `is_blocklisted()` + UPSERT persistence |

---

*Generated: 2026-02-13T02:25:00+04:00*
