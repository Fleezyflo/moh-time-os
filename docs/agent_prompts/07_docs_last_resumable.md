# Prompt 7 — Docs (LAST): Resumable, Aggregated Counters, Proofs

Objective:
Make Docs collection run LAST and finish cleanly even on large domains by adding a resumable state model,
aggregated error counters (no per-doc spam), and deterministic proofs. This prompt is ONLY about Docs.

Scope constraints:
- Docs derives from Drive; Drive must run first.
- Do not change Drive discovery semantics: doc_ids come from drive_files where mime_type ==
  application/vnd.google-apps.document (and existing Drive time window/orderBy rules).
- Do not weaken correctness: never skip doc_ids silently.

Deliverable format (STRICT):

1) Execution ordering (must be enforced)
- Confirm sweep ordering: gmail → calendar → chat → drive → docs (LAST).
- Confirm docs runs only after Drive success for that subject (or uses persisted drive_files rows).

2) Resumability model (must be explicit)
A) New cursor/state keys (sync_cursor) for Docs:
- service='docs', subject=<subject_email>
- key='docs:last_doc_id' OR key='docs:last_modified_time' (pick one and justify)
- key='docs:complete' (boolean) OR inferred by exhaustion

B) Definition of “exhausted” for Docs:
- processed_count == total_doc_ids_discovered (for that subject + window)
- no pending doc_ids remain

C) Resume rule:
- On restart, resume from cursor/state (do NOT restart from the first doc every time).
- Must tolerate doc deletion between discovery and export.

3) Deterministic iteration plan (no drift)
- Define how doc_ids are ordered for processing (must be deterministic).
  Options:
  - by Drive modified_time asc + doc_id tie-break
  - OR by doc_id asc if modified_time unavailable in discovery set
- Explain how you guarantee “resume picks up exactly where it left off”.

4) Per-doc API contract (fixed)
For each doc_id (in order):
A) Drive files().get(fileId=doc_id, fields="id,name,mimeType,modifiedTime")  [or minimal fields used]
B) Drive files().export(fileId=doc_id, mimeType="text/plain")
C) Persist into docs_documents via UPSERT (subject_email, doc_id)

5) Aggregated counters (no per-doc spam)
Define counters per subject:
- attempted
- ok
- missing_404
- transient_5xx
- rate_limit
- other_err
- skipped_already_done (if resume skips doc_ids)

Logging requirements:
- Exactly ONE summary line per subject, plus optional debug lines behind AUTH_DEBUG.
- Summary line format (EXACT):
  DOCS subject=<email> attempted=<n> ok=<n> missing_404=<n> transient_5xx=<n> rate_limit=<n> other_err=<n> partial=<0|1> cursor_written=<0|1>

6) Cursor write gating (Docs)
- Cursor must only be advanced when the processed slice is committed to DB.
- If the process is killed mid-run, next run must restart from the last committed cursor, not past it.
- Define precisely when cursor_written=1.

7) “Correctness proofs” (must be runnable)
A) Coverage proof (docs_documents subjects should reach 20):
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT COUNT(DISTINCT subject_email) AS subjects, COUNT(*) AS rows
    FROM docs_documents;
  "

B) Per-subject completion report:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT subject_email, COUNT(*) AS docs_rows
    FROM docs_documents
    GROUP BY 1
    ORDER BY docs_rows DESC
    LIMIT 50;
  "

C) Compare Drive doc inventory vs Docs rows (spot missing):
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    WITH drive_docs AS (
      SELECT subject_email, COUNT(*) AS drive_doc_count
      FROM drive_files
      WHERE mime_type='application/vnd.google-apps.document'
      GROUP BY 1
    ),
    docs_rows AS (
      SELECT subject_email, COUNT(*) AS docs_rows
      FROM docs_documents
      GROUP BY 1
    )
    SELECT d.subject_email,
           d.drive_doc_count,
           COALESCE(r.docs_rows,0) AS docs_rows,
           (d.drive_doc_count-COALESCE(r.docs_rows,0)) AS delta
    FROM drive_docs d
    LEFT JOIN docs_rows r USING(subject_email)
    ORDER BY delta DESC, d.drive_doc_count DESC
    LIMIT 50;
  "

Expected:
- delta should converge toward 0 after repeated runs (allow some persistent delta only if export consistently fails; then counters must explain it).

D) Cursor presence proof:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT subject, key, value
    FROM sync_cursor
    WHERE service='docs'
    ORDER BY subject, key
    LIMIT 200;
  "

8) Operational command (Docs-only, LAST)
Provide an operator command to run ONLY docs after non-docs are complete:
  AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
    --docs-only --exhaust 2>&1 | tee /tmp/docs_only.log

Or if flags don’t exist, specify the minimal new flag(s) needed:
- --services docs
- --only-existing-targets
- --resume

Hard requirements:
- Docs must remain last in full sweep.
- No per-doc log spam: only aggregated counters.
- Must be resumable and converge without manual intervention.
- Any schema changes must be explicit (ALTER TABLE or new cursor keys only). Prefer cursor keys over new tables unless necessary.
