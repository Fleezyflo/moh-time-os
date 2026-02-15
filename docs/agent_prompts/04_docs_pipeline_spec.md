# Prompt 4 — Docs Pipeline Spec (Explain Only; Implementation Deferred)

Objective:
Explain the Docs pipeline end-to-end *without* implementing fixes yet. Docs work must remain LAST (Prompt 07),
but we still need a clear spec so the agent cannot drift.

Deliverable format (STRICT):
1) Dependency graph
- State explicitly: Docs derives from Drive. Drive must run before Docs.
- List the exact Drive signals that feed Docs (doc_ids discovery).

2) Discovery logic (from Drive)
- Precisely define which Drive files are treated as Google Docs:
  - mimeType == application/vnd.google-apps.document
- Show the exact Drive query constraints relevant to discovery (trashed=false, time window, orderBy).

3) Per-doc processing steps (API calls)
For each doc_id:
A) files().get(fileId=..., fields=...)  (title/mime verification)
B) files().export(fileId=..., mimeType="text/plain") (content)
C) Any normalization performed (if none, say none)

4) Persistence contract (docs_documents)
- Table name: docs_documents
- Natural key: (subject_email, doc_id)
- What columns are persisted (title, text_content, char_count, raw_json, timestamps)
- What is *not* persisted (binary exports, formatting, comments, revisions)

5) Failure taxonomy (MUST be explicit)
Define at least these classes and what they mean:
- missing_404 (deleted, permission revoked, moved to trash between list and export)
- transient_5xx (backend errors)
- rate_limit / quota
- other_err
For each, state:
- whether it should fail the run
- whether it should advance any cursor/state (answer should be “no cursor exists yet”)

6) Performance profile (why Docs is slow)
- Expected call count: 2 API calls per doc_id
- Explain why it becomes N_docs * 2 calls per subject and can dominate runtime.
- Include a “why this causes mid-run kills” section: single-threaded, long tail.

7) Proof queries (NON-IMPLEMENTATION)
Provide queries that show current situation, without promising fixes:
A) How many Docs exist per subject in Drive:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT subject_email,
           SUM(CASE WHEN mime_type='application/vnd.google-apps.document' THEN 1 ELSE 0 END) AS docs
    FROM drive_files
    GROUP BY 1
    ORDER BY docs DESC
    LIMIT 20;
  "

B) Current docs_documents coverage:
  sqlite3 -header ~/.moh_time_os/data/moh_time_os.db "
    SELECT COUNT(*) AS rows, COUNT(DISTINCT subject_email) AS subjects FROM docs_documents;
  "

Hard requirements:
- Do NOT propose any resume/cursor solution here. That belongs ONLY in Prompt 07.
- Do NOT suggest changing global sweep ordering except “Docs runs last”.
- Keep this prompt purely descriptive/spec-level.
