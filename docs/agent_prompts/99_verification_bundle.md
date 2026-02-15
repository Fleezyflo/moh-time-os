# Prompt 99 — Verification Bundle (Non-Docs + Wiring)

Objective:
Provide a single, copy/paste verification bundle that:
1) Proves non-docs sweep completeness (gmail/calendar/chat/drive)
2) Proves DB + cursor invariants (coverage, monotonicity, no partial)
3) Is suitable to wire into docs/heartbeat.md as a deterministic “definition of done” section
Docs must be excluded here (Docs is Prompt 07 only).

Deliverable (STRICT):
Return exactly three sections:

A) RUN COMMANDS
- Commands to run an exhaustive sweep for non-docs only.
- Commands must be safe to rerun.
- Commands must write logs to /tmp and not require manual subject lists.

B) PASS/FAIL CHECKS
- Exact commands to compute PASS/FAIL (grep/rg/sqlite3).
- Each check must have an explicit expected output condition.
- Checks must cover:
  1) COMPLETE status (no partial, no errors)
  2) Subject coverage == 20 for each service table
  3) Cursor presence for each subject (gmail historyId, drive last_modified_time, chat per-space)
  4) Cursor monotonicity (sample-based acceptable)

C) HEARTBEAT.md SNIPPET
- A markdown snippet titled “Verification (Non-Docs)”
- Includes the RUN commands and PASS/FAIL checks in code blocks
- Defines a single line at the bottom: “DONE when all checks PASS.”

Hard requirements:
- Use AUTH_DEBUG=1 in sweep command.
- Use --full-sweep --exhaust --services gmail,calendar,chat,drive.
- PASS checks must not rely on hidden state outside DB/logs.
- No mention of “add scope” or Admin Console (already solved).
- Do not include Docs in any run/check.

MANDATORY COMMANDS TO INCLUDE:

A1) Run sweep:
  AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
    --full-sweep --exhaust --services gmail,calendar,chat,drive 2>&1 | tee /tmp/full_sweep.log

B1) Prove END lines count:
  rg "SWEEP .* phase=END" /tmp/full_sweep.log | wc -l

B2) Prove no partial:
  rg "partial=1" /tmp/full_sweep.log || true

B3) Prove no errors:
  rg "SWEEP .* phase=END" /tmp/full_sweep.log | rg "err=" | rg -v "err=none" || true

B4) Prove subject coverage:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
    UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
    UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
    UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
  "

B5) Prove cursor distribution:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT service, key, COUNT(DISTINCT subject) AS subjects
    FROM sync_cursor
    GROUP BY 1,2
    ORDER BY 1,2;
  "

B6) Prove chat per-space cursors exist:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT COUNT(*) AS chat_space_cursors
    FROM sync_cursor
    WHERE service='chat' AND key LIKE 'space:%:last_create_time';
  "
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT COUNT(DISTINCT space_name) AS spaces_with_messages
    FROM chat_messages;
  "

Expected: chat_space_cursors >= spaces_with_messages

B7) Optional kill/resume convergence (chat only):
  timeout 30 bash -c 'AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat' \
    2>&1 | tee /tmp/kill_run.log || true
  AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --full-sweep --exhaust --services chat \
    2>&1 | tee /tmp/resume_run.log
  rg "partial=1" /tmp/resume_run.log || true

Define expected outcomes explicitly:
- END lines == active_targets_total * 4 (active_targets_total is printed by target_report or sweep header)
- partial=1 occurrences == 0
- err!=none occurrences == 0
- subject counts == 20 for gmail/calendar/chat/drive
- chat_space_cursors >= spaces_with_messages

