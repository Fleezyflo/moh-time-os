# Prompt 3 — Practical Use Cases (SQL Queries, Docs Excluded)

Objective:
Provide an operator/analyst-ready set of practical SQLite queries that we can run TODAY against the current schema to validate usefulness and spot obvious gaps — for:
- Gmail
- Calendar
- Chat
- Drive
Docs must be excluded from this prompt (Docs is handled in Prompt 07).

Deliverable format (STRICT):
1) “Ready now” query pack (minimum 15 queries)
- Each query must be:
  - copy/paste runnable in sqlite3
  - scoped to existing tables/columns
  - named + one-line intent
- Cover these buckets:
  A) Activity / volume
  B) People / collaboration graph
  C) Time series and trends
  D) Cross-service joins (chat + calendar, chat + drive, gmail + calendar)
  E) Data quality checks (nulls, duplicates, outliers)

2) For each query:
- Provide the SQL
- Provide the expected output shape (columns)
- Provide at least one constraint/assumption (e.g., time windows, dedup keys)

3) Coverage proofs
- For each service table, include:
  - total rows
  - distinct subjects
  - min/max timestamp fields (where applicable)

Mandatory proofs (paste outputs):
A) Counts + distinct subjects:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT 'gmail_messages' AS tbl, COUNT(*) AS rows, COUNT(DISTINCT subject_email) AS subjects FROM gmail_messages
    UNION ALL
    SELECT 'calendar_events', COUNT(*), COUNT(DISTINCT subject_email) FROM calendar_events
    UNION ALL
    SELECT 'chat_messages', COUNT(*), COUNT(DISTINCT subject_email) FROM chat_messages
    UNION ALL
    SELECT 'drive_files', COUNT(*), COUNT(DISTINCT subject_email) FROM drive_files;
  "

B) Timestamp ranges (where columns exist):
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT 'chat_messages' AS tbl,
           MIN(create_time) AS min_time, MAX(create_time) AS max_time
    FROM chat_messages
    UNION ALL
    SELECT 'calendar_events',
           MIN(start_time), MAX(start_time)
    FROM calendar_events
    UNION ALL
    SELECT 'drive_files',
           MIN(modified_time), MAX(modified_time)
    FROM drive_files;
  "

C) Top-N sanity checks (paste outputs for each):
- Top 10 spaces by volume (chat)
- Top 10 people by meetings (calendar)
- Top 10 modified files (drive)
- Top 10 gmail labels by count (gmail)

Hard requirements:
- Do NOT propose schema changes here.
- Do NOT include any docs_documents queries.
- Prefer queries that will still be valid after data volume increases (avoid SELECT * without LIMIT).
