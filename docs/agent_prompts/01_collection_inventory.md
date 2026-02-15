# Prompt 1 — Concrete Data Collection Inventory (Docs Excluded)

Objective:
Produce an exact, verifiable inventory of what we collect, how we collect it (endpoints), what we persist, and what keys/cursors guarantee no gaps — for:
- Gmail
- Calendar
- Chat
- Drive
Docs must be excluded from this prompt (Docs is handled in Prompt 07).

Deliverable format (STRICT):
For each service, output these sections:
1) API Endpoints (in order)
2) Fields Extracted (table)
3) DB Schema (CREATE TABLE)
4) Uniqueness / Upsert (natural key + conflict policy)
5) Cursor Keys (sync_cursor keys + advance condition)
6) Status Classification (OK/EMPTY/ERR + partial rules)
7) Coverage Proof queries (sqlite3 SELECTs)

Requirements:
- List the exact endpoints used in code (method names + parameters that matter).
- Name the SQLite tables exactly as in the codebase.
- Cursor gating rules must mention the “pagination exhausted” condition where applicable.
- Include “WATERMARK_WARNING” risk explanation only where limits can truncate.

Mandatory proofs (paste outputs):
A) Row counts per table:
  SELECT COUNT(*) FROM gmail_messages;
  SELECT COUNT(*) FROM calendar_events;
  SELECT COUNT(*) FROM chat_messages;
  SELECT COUNT(*) FROM drive_files;

B) Distinct subject coverage per table:
  SELECT COUNT(DISTINCT subject_email) FROM <table>;

C) Cursor distribution summary:
  SELECT service, key, COUNT(DISTINCT subject) FROM sync_cursor GROUP BY 1,2 ORDER BY 1,2;

D) One sample “per user” evidence line for each service from logs showing:
- page count / fetched count
- persisted inserted/updated
- cursor writes (or explicit non-advance when partial)
