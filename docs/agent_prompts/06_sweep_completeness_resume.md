# Prompt 6 — Sweep Completeness & Resume (Non-Docs Only)

Objective:
Design and implement a clean, repeatable way to run a full sweep that *always converges* to COMPLETE even if the
process is killed mid-run — WITHOUT involving Docs. This must cover Gmail, Calendar, Chat, Drive only.

The end state must be:
- active_targets_attempted == active_targets_total
- partial_subjects_count == 0
- errors_count == 0
- cursors advanced only under correct gating (pagination exhausted per service rules)

Deliverable format (STRICT):

1) Define “COMPLETE” precisely (non-docs)
Provide the exact invariants and how they are computed from logs/DB:
- active_targets_total
- attempted_count
- complete_subjects_count
- partial_subjects_count
- errors_count
- per-service pagination_exhausted

2) Resume strategy (must be deterministic)
A) Subject ordering:
- deterministic ordering of subjects (email ASC)
- deterministic ordering of services (gmail,calendar,chat,drive)

B) Per-subject state machine:
For each subject/service, classify:
- NOT_STARTED
- IN_PROGRESS (only during process runtime)
- COMPLETE (cursor advanced and persistence succeeded)
- PARTIAL (cursor not advanced due to partial pagination)
- ERR:<class>

C) Resume rule:
- On restart, skip subject/service pairs that are COMPLETE.
- Retry only PARTIAL or ERR (unless permanent blocklist applies).
- Ensure no cursor regression.

3) Persistence + cursor gating audit hooks (mandatory)
Add log lines (single-line, parseable) for each subject/service:
- START
- PAGE persisted (optional, but not spammy)
- CURSOR_WRITE (with key/value)
- CURSOR_SKIP (with reason=partial)
- END (ok=<bool> count=<n> partial=<bool> err=<class|none>)

Log format requirement (exact keys):
  SWEEP service=<svc> subject=<email> phase=<START|END|CURSOR_WRITE|CURSOR_SKIP> ok=<0|1> count=<n> partial=<0|1> err=<none|...> detail=<...>

4) Minimal CLI ergonomics
Add flags (or confirm existing ones) to support clean ops:
- --full-sweep (non-docs only here)
- --exhaust (unlimited pagination)
- --services gmail,calendar,chat,drive (explicit)
- --resume (default true; restarts converge)
- --only-remaining (optional: run only NOT_STARTED + PARTIAL)

Constraints:
- Must NOT change Docs order or behavior here.
- Must NOT introduce new external dependencies.
- Must NOT require manual subject lists to continue (operator should just rerun the same command).

5) Verification bundle (non-docs)
Provide the exact commands and expected pass conditions:

A) Run sweep (exhaustive, non-docs):
  AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
    --full-sweep --exhaust --services gmail,calendar,chat,drive 2>&1 | tee /tmp/full_sweep.log

B) Prove COMPLETE from logs:
  rg "SWEEP .* phase=END" /tmp/full_sweep.log | wc -l
  rg "partial=1" /tmp/full_sweep.log
  rg "err=" /tmp/full_sweep.log | rg -v "err=none"

Expected:
- END lines == active_targets_total * 4
- zero partial=1 lines
- zero err!=none lines

C) Prove cursor monotonicity (sample-based; at least gmail + drive):
  sqlite3 ~/.moh_time_os/data/moh_time_os.db "
    SELECT service,subject,key,value
    FROM sync_cursor
    WHERE (service='gmail' AND key='historyId') OR (service='drive' AND key='last_modified_time')
    ORDER BY service,subject
    LIMIT 200;
  " > /tmp/cursors_after.txt

(If you have /tmp/cursors_before.txt from a prior run, diff it; otherwise just show values are present for all 20 subjects.)

D) Prove subject coverage:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
    UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
    UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
    UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
  "

Expected: 20 for each.

6) Kill/resume convergence test (mandatory)
Provide a safe reproducible test:
A) Kill mid-run:
  timeout 30 bash -c 'AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat' \
    2>&1 | tee /tmp/kill_run.log || true

B) Resume:
  AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat \
    2>&1 | tee /tmp/resume_run.log

Expected:
- resume run should skip spaces already COMPLETE (cursor exists)
- final run shows partial=0

Hard requirements:
- Non-docs only (gmail/calendar/chat/drive).
- Deterministic, restartable, convergent behavior is the goal.
- Provide exact code touchpoints (file/function names) for any modifications.
