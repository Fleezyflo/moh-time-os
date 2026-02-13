# 07 — Docs (LAST): Resumable, Aggregated Counters, Proofs

---

## CURRENT STATE PROOFS

### A) Coverage (docs_documents)
```
subjects|rows
1|318
```
**Gap:** Only 1 of 20 subjects have any docs extracted.

### B) Per-subject completion
```
subject_email|docs_rows
aubrey@hrmny.co|318
```

### C) Drive vs Docs delta
```
subject_email|drive_doc_count|docs_rows|delta
ramy@hrmny.co|470|0|470
ayman@hrmny.co|437|0|437
molham@hrmny.co|437|0|437
joshua@hrmny.co|385|0|385
aubrey@hrmny.co|341|318|23
... (19 subjects with delta > 0)
```
**Total gap:** ~3,934 docs unextracted

### D) Cursor presence
```
(empty - no docs cursors exist)
```

---

## 1) EXECUTION ORDERING (enforced)

### Sweep order:
```
gmail → calendar → chat → drive → docs (LAST)
```

### Enforcement in code:
```python
# In run_all_users(), services are processed in order:
for service in ["gmail", "calendar", "chat", "drive", "docs"]:
    if service in requested_services:
        collect_<service>_for_user(...)

# Docs runs ONLY after Drive completes:
if "drive" in services:
    drive_result = collect_drive_for_user(...)
    doc_ids = drive_result.get("doc_ids", [])

if "docs" in services and doc_ids:
    docs_result = collect_docs_for_user(user, doc_ids, ...)
```

---

## 2) RESUMABILITY MODEL

### A) Cursor keys for Docs
| Key | Type | Purpose |
|-----|------|---------|
| `service='docs'` | - | Service identifier |
| `subject=<email>` | - | Subject identifier |
| `key='last_processed_doc_id'` | TEXT | Last doc_id successfully persisted |
| `key='processed_count'` | INTEGER | Count of docs processed this sweep |

**Justification:** `last_processed_doc_id` is preferred over `last_modified_time` because:
- doc_ids are stable identifiers
- Can resume from exact position in ordered list
- No ambiguity with time collisions

### B) Definition of "exhausted" for Docs
```python
exhausted = (processed_count == len(doc_ids_to_process))
# Where doc_ids_to_process = [d for d in all_doc_ids if d > last_processed_doc_id]
```

### C) Resume rule
```python
def get_docs_to_process(subject, all_doc_ids):
    last_doc_id = get_cursor(db_path, "docs", subject, "last_processed_doc_id")
    if last_doc_id:
        # Skip already-processed docs
        remaining = [d for d in sorted(all_doc_ids) if d > last_doc_id]
        return remaining
    return sorted(all_doc_ids)
```

**Tolerance for deletion:** If a doc_id is 404, it's counted in `missing_404` and skipped (not blocking).

---

## 3) DETERMINISTIC ITERATION PLAN

### Ordering strategy:
```python
# Option 1 (preferred): Sort by doc_id ASC for stable ordering
doc_ids_ordered = sorted(doc_ids)

# Option 2: Sort by modified_time from drive_files (requires extra query)
# Not preferred - adds complexity
```

### Guarantee for resume:
1. doc_ids are sorted ASC before processing
2. `last_processed_doc_id` cursor updated ONLY after successful persist
3. On restart: `remaining = [d for d in sorted(doc_ids) if d > last_doc_id]`
4. Exact position preserved

---

## 4) PER-DOC API CONTRACT

For each `doc_id` in sorted order:

| Step | API Call | Fields |
|------|----------|--------|
| A | `files().get(fileId=doc_id, fields="id,name,mimeType")` | Title, verify type |
| B | `files().export(fileId=doc_id, mimeType="text/plain")` | Extract text |
| C | `persist_docs_documents(subject, [doc])` | UPSERT to DB |
| D | `set_cursor("docs", subject, "last_processed_doc_id", doc_id)` | Update cursor |

---

## 5) AGGREGATED COUNTERS (already implemented)

### Counters per subject:
| Counter | Meaning |
|---------|---------|
| `attempted` | Total doc_ids attempted |
| `ok` | Successfully extracted and persisted |
| `missing_404` | File not found (deleted/permission revoked) |
| `transient_5xx` | Server errors |
| `rate_limit` | Quota exceeded |
| `other_err` | Other failures |
| `skipped_already_done` | Skipped via cursor resume |

### Summary line format (EXACT):
```
DOCS subject=<email> attempted=<n> ok=<n> missing_404=<n> transient_5xx=<n> rate_limit=<n> other_err=<n> partial=<0|1> cursor_written=<0|1>
```

### Current implementation:
```python
# In collect_docs_for_user() (lib/collectors/all_users_runner.py):
logger.info(
    f"docs: {user} attempted={len(docs_to_process)} ok={len(extracted_docs)} "
    f"missing_404={missing_404} transient_5xx={transient_5xx} other_err={other_err}"
)
```

---

## 6) CURSOR WRITE GATING

### Rules:
1. Cursor written ONLY after `persist_docs_documents()` succeeds
2. Cursor value = `doc_id` of last successfully persisted doc
3. If killed mid-run: cursor points to last committed doc
4. Next run resumes from `cursor + 1` position

### When `cursor_written=1`:
```python
# Per-doc (streaming):
if persist_success:
    set_cursor(db_path, "docs", subject, "last_processed_doc_id", doc_id)
    cursor_written = True

# OR batch (end of run):
if pagination_exhausted and any_persisted:
    set_cursor(...)
```

---

## 7) OPERATIONAL COMMAND

### Docs-only sweep (after non-docs complete):
```bash
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --services docs --exhaust 2>&1 | tee /tmp/docs_only.log
```

### Full sweep including docs:
```bash
AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner \
  --full-sweep --services gmail,calendar,chat,drive,docs 2>&1 | tee /tmp/full_sweep.log
```

---

## 8) CORRECTNESS PROOFS (runnable)

### A) Coverage proof:
```sql
SELECT COUNT(DISTINCT subject_email) AS subjects, COUNT(*) AS rows
FROM docs_documents;
-- Expected after full run: subjects=20, rows=~4000
```

### B) Per-subject completion:
```sql
SELECT subject_email, COUNT(*) AS docs_rows
FROM docs_documents
GROUP BY 1
ORDER BY docs_rows DESC;
```

### C) Drive vs Docs delta:
```sql
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
ORDER BY delta DESC;
-- Expected: delta converges to 0 (or small persistent delta explained by missing_404)
```

### D) Cursor presence:
```sql
SELECT subject, key, value
FROM sync_cursor
WHERE service='docs'
ORDER BY subject, key;
-- Expected: 20 subjects with last_processed_doc_id
```

---

## GAP SUMMARY

| Metric | Current | Target |
|--------|---------|--------|
| Subjects with docs | 1 | 20 |
| Total docs extracted | 318 | ~4,252 |
| Delta to close | 3,934 | 0 (or explained by 404s) |
| Cursors present | 0 | 20 |

---

*Generated: 2026-02-13T02:30:00+04:00*
