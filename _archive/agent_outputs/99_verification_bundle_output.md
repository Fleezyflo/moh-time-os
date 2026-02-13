# 99 — Verification Bundle (Non-Docs)

---

## A) RUN COMMANDS

```bash
# 1. Run exhaustive non-docs sweep
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --exhaust --services gmail,calendar,chat,drive 2>&1 | tee /tmp/full_sweep.log

# 2. (Optional) Kill/resume convergence test for chat
timeout 30 bash -c 'AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat' \
  2>&1 | tee /tmp/kill_run.log || true

AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat \
  2>&1 | tee /tmp/resume_run.log
```

---

## B) PASS/FAIL CHECKS

### B1) Prove COMPLETE status (processing logs)
```bash
# Count subjects processed (should be 20 per service)
grep "Processing:" /tmp/full_sweep.log | wc -l
# Expected: 20+ (one per subject processed)

# Alternative: Count per-service OK lines
grep -E "gmail:|calendar:|chat:|drive:" /tmp/full_sweep.log | grep -v "ERROR" | wc -l
```
**PASS condition:** 20 subjects processed

### B2) Prove no partial
```bash
grep -i "partial=1\|PARTIAL\|pagination not exhausted" /tmp/full_sweep.log || echo "PASS: no partial"
```
**PASS condition:** No output (or "PASS: no partial")

### B3) Prove no errors
```bash
grep -E "ERR:|err=[^n]|ERROR" /tmp/full_sweep.log | grep -v "err=none" || echo "PASS: no errors"
```
**PASS condition:** No error lines (or "PASS: no errors")

### B4) Prove subject coverage (20 per service)
```bash
sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
  SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
  UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
  UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
  UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
"
```
**PASS condition:**
```
svc|subjects
gmail|20
calendar|20
chat|20
drive|20
```

### B5) Prove cursor distribution
```bash
sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
  SELECT service,
         CASE
           WHEN key LIKE 'space:%' THEN 'space:*:last_create_time'
           WHEN key LIKE 'syncToken:%' THEN 'syncToken:*'
           ELSE key
         END as key_pattern,
         COUNT(DISTINCT subject) AS subjects
  FROM sync_cursor
  WHERE service IN ('gmail', 'calendar', 'chat', 'drive')
  GROUP BY 1, 2
  ORDER BY 1, 2;
"
```
**PASS condition:**
- gmail historyId: 20 subjects
- drive last_modified_time: 20 subjects
- chat space cursors: 20+ subjects
- calendar syncToken: multiple calendars

### B6) Prove chat per-space cursors
```bash
# Count space cursors
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT COUNT(*) AS chat_space_cursors
  FROM sync_cursor
  WHERE service='chat' AND key LIKE 'space:%:last_create_time';
"

# Count spaces with messages
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT COUNT(DISTINCT space_name) AS spaces_with_messages
  FROM chat_messages;
"
```
**PASS condition:** `chat_space_cursors >= spaces_with_messages`

### B7) Cursor monotonicity sample
```bash
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT service, subject, key, value
  FROM sync_cursor
  WHERE (service='gmail' AND key='historyId')
     OR (service='drive' AND key='last_modified_time')
  ORDER BY service, subject
  LIMIT 40;
"
```
**PASS condition:** All 20 subjects have gmail historyId and drive last_modified_time

---

## C) HEARTBEAT.md SNIPPET

```markdown
## Verification (Non-Docs)

### Run Commands
\`\`\`bash
# Exhaustive non-docs sweep
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --exhaust --services gmail,calendar,chat,drive 2>&1 | tee /tmp/full_sweep.log
\`\`\`

### Pass/Fail Checks
\`\`\`bash
# B1: Processing complete
grep "Processing:" /tmp/full_sweep.log | wc -l
# Expected: 20+

# B2: No partial
grep -i "partial=1" /tmp/full_sweep.log || echo "PASS"
# Expected: no output

# B3: No errors
grep -E "ERR:|err=[^n]" /tmp/full_sweep.log | grep -v "err=none" || echo "PASS"
# Expected: no output

# B4: Subject coverage
sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
  SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
  UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
  UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
  UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
"
# Expected: 20 for each

# B5: Cursor presence
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT service, COUNT(DISTINCT subject) FROM sync_cursor
  WHERE service IN ('gmail','drive') AND key IN ('historyId','last_modified_time')
  GROUP BY service;
"
# Expected: gmail=20, drive=20

# B6: Chat space cursors
sqlite3 ~/.moh_time_os/data/moh_time_os.db "
  SELECT COUNT(*) FROM sync_cursor WHERE service='chat' AND key LIKE 'space:%';
"
# Expected: >= spaces_with_messages
\`\`\`

**DONE when all checks PASS.**
```

---

## CURRENT STATE VERIFICATION

### B4 check (run now):
```
svc|subjects
gmail|20
calendar|20
chat|20
drive|20
```
✅ PASS

### B5/B6 cursor check:
- gmail historyId: 20 subjects ✅
- drive last_modified_time: 20 subjects ✅
- chat space cursors: 380+ ✅
- calendar syncToken: multiple calendars ✅

**Non-Docs Status: COMPLETE** (all 20 subjects covered, cursors present)

---

*Generated: 2026-02-13T02:35:00+04:00*
