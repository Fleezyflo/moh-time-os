# Prompt 2 — Correctness Review (Pagination, Cursor Gating, Invariants) — Non-Docs Only

Objective:
Do a correctness review focused on gap-freedom and restart safety for:
- Gmail
- Calendar
- Chat
- Drive
Docs must be excluded (Docs is Prompt 07 only).

Deliverable format (STRICT):
For each service, produce exactly these sections:

1) Pagination boundary
- Which API method provides page boundaries (nextPageToken/historyId/syncToken/etc.)
- pageSize used
- termination condition

2) Deterministic ordering
- Whether explicit ordering exists (orderBy=...) and what it is
- If no ordering is available, explain the compensating mechanism (e.g., historyId)

3) Cursor keys + gating rule
- Exact sync_cursor keys written
- Exact condition for writing (must mention “pagination exhausted” / “space exhausted” / “syncToken present”)
- What happens on partial (explicitly state “cursor not advanced”)

4) Streaming persistence
- When persistence occurs (per page vs end of run)
- Why kill mid-run cannot create gaps

5) Failure modes table
Include at least:
- process killed mid-run
- repeated nextPageToken loop
- API ordering instability
- token expiry / syncToken invalidation
For each: gap risk + current mitigation + missing mitigation (if any)

6) End-of-run invariants (global)
Define invariants we should log/verify:
- partial_subjects_count == 0
- errors_count == 0
- active_targets_attempted == active_targets_total
- for chat: spaces_partial == 0

7) Mandatory evidence (paste outputs)
A) Grep-based evidence from logs showing cursor gating:
- One example where cursor is written because exhausted
- One example where cursor is NOT written because partial

B) DB evidence:
- Cursor distribution:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT service, key, COUNT(DISTINCT subject) AS subjects
    FROM sync_cursor
    GROUP BY 1,2
    ORDER BY 1,2;
  "

C) Coverage evidence:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT 'gmail' AS svc, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
    UNION ALL SELECT 'calendar', COUNT(DISTINCT subject_email) FROM calendar_events
    UNION ALL SELECT 'chat', COUNT(DISTINCT subject_email) FROM chat_messages
    UNION ALL SELECT 'drive', COUNT(DISTINCT subject_email) FROM drive_files;
  "

Hard requirements:
- Non-docs only.
- Call out any place where ordering is non-deterministic and how we avoid gaps anyway.
- If you recommend a change, name the exact file/function and show a minimal unified diff.

