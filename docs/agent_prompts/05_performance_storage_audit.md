# Prompt 5 — Performance & Storage Audit (Docs Fixes Excluded)

Objective:
Produce a proof-driven performance/storage assessment of the current SQLite DB and collector write patterns, with a minimal, prioritized action list.

Scope:
- Include: gmail_messages, calendar_events, chat_messages, drive_files, docs_documents, sync_cursor, subject_blocklist, artifact_blobs (if present)
- You MAY mention Docs impact, but MUST NOT propose Docs resumability/robustness changes here (that is Prompt 07).

Deliverable format (STRICT):
1) Current DB stats (with proofs)
- DB file size (ls -lah)
- sqlite pragmas: page_size, page_count, freelist_count
- table row counts (top 15 by rowcount)
- index inventory for collector tables (explicit + auto indexes)

2) Workload model (collector-specific)
- For each service, list the highest-frequency reads/writes:
  - UPSERT existence checks (natural keys)
  - time-window queries (incremental sync)
  - cursor reads/writes
- Identify likely full table scans (collector runtime AND analyst queries)

3) Index recommendations (minimal set)
- Provide CREATE INDEX IF NOT EXISTS statements
- Each index must map to a real query pattern (show the query)
- Explicitly call out “do not add” indexes that are redundant with UNIQUE auto indexes

4) Storage pressure & mitigations (low-risk first)
- Identify largest columns (raw_json/text blobs) by table
- Propose safe reductions WITHOUT breaking correctness:
  - subset JSON (what keys to keep)
  - optional compression for text_content
  - externalize blobs if any table has multi-100KB payloads
- Include risk notes: what would be lost and how to recover via API if needed

5) Priority plan (max 6 items)
For each item:
- priority (HIGH/MED/LOW)
- impact
- risk
- exact verification query/proof

Mandatory proofs (paste outputs):
A) DB size + sqlite info:
  ls -lah ~/.moh_time_os/data/moh_time_os.db
  sqlite3 ~/.moh_time_os/data/moh_time_os.db "PRAGMA page_size; PRAGMA page_count; PRAGMA freelist_count;"

B) Largest tables:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT name, (SELECT COUNT(*) FROM sqlite_master) as _,
           (SELECT COUNT(*) FROM sqlite_master WHERE type='table') as __;
  "  -- (replace with a real top-N query using sqlite_master + COUNT(*) per table)

C) Index inventory (collector tables):
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT tbl_name, name, sql
    FROM sqlite_master
    WHERE type='index'
      AND tbl_name IN ('gmail_messages','calendar_events','chat_messages','drive_files','docs_documents','sync_cursor')
    ORDER BY tbl_name, name;
  "

D) For 2 representative queries (choose chat + drive):
- Show EXPLAIN QUERY PLAN before indexes
- Apply recommended indexes
- Show EXPLAIN QUERY PLAN after indexes (prove scan → index usage)

Hard requirements:
- Every recommendation must be tied to a proof (counts/plan/size).
- Do not propose schema redesign here (no partitioning, no new DB engine).
- Keep it minimal: indexing + safe storage reductions only.
