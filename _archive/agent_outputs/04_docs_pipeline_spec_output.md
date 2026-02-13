# 04 — Docs Pipeline Spec (Explain Only; Implementation Deferred)

---

## PROOF QUERIES (current situation)

### A) Docs per subject in Drive
```
subject_email|docs
ramy@hrmny.co|470
ayman@hrmny.co|437
molham@hrmny.co|437
joshua@hrmny.co|385
aubrey@hrmny.co|341
fabina@hrmny.co|295
mark@hrmny.co|290
imad@hrmny.co|243
raafat@hrmny.co|229
jessica@hrmny.co|220
... (total 20 subjects)
```
**Total Google Docs in drive_files:** ~4,252 across 20 subjects

### B) Current docs_documents coverage
```
rows|subjects
318|1
```
**Current state:** Only 318 docs extracted from 1 subject (aubrey@hrmny.co)
**Gap:** ~4,000 docs unextracted

---

## 1) DEPENDENCY GRAPH

```
┌──────────────────────────────────────────────────────────┐
│  DRIVE COLLECTOR                                         │
│  ├── files().list(q="...", orderBy=modifiedTime)        │
│  ├── Discovers ALL files including mimeType             │
│  └── Returns doc_ids[] where mimeType=google-apps.doc   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼ doc_ids[]
┌──────────────────────────────────────────────────────────┐
│  DOCS COLLECTOR                                          │
│  ├── For each doc_id:                                   │
│  │   ├── files().get(fileId) → title/metadata           │
│  │   └── files().export(fileId, text/plain) → content   │
│  └── persist_docs_documents(...)                        │
└──────────────────────────────────────────────────────────┘
```

**Explicit dependency:** Docs MUST run AFTER Drive completes.
Drive provides `doc_ids` via `drive_result["doc_ids"]`.

---

## 2) DISCOVERY LOGIC (from Drive)

### Drive query constraints:
```python
query = (
    f"modifiedTime >= '{since_rfc}' and modifiedTime <= '{until_rfc}' and trashed = false"
)
# orderBy=modifiedTime for deterministic ordering
```

### Docs identification:
```python
# In collect_drive_for_user:
for f in items:
    if f.get("mimeType") == "application/vnd.google-apps.document":
        doc_ids.append(f.get("id"))
```

**Filter criteria:**
- `mimeType == "application/vnd.google-apps.document"` (EXACT match)
- File not trashed (`trashed = false` in query)
- Within time window (`modifiedTime >= since AND <= until`)

---

## 3) PER-DOC PROCESSING STEPS

For each `doc_id` in `doc_ids`:

| Step | API Call | Purpose |
|------|----------|---------|
| A | `files().get(fileId=doc_id, fields="id,name,mimeType")` | Get title/metadata |
| B | `files().export(fileId=doc_id, mimeType="text/plain")` | Export as plain text |
| C | Decode response bytes to UTF-8 string | Normalization |

**Normalization performed:**
```python
text = response.decode("utf-8") if isinstance(response, bytes) else str(response)
```

**Not performed:** No HTML cleanup, no formatting extraction, no comment parsing.

---

## 4) PERSISTENCE CONTRACT

### Table: `docs_documents`
```sql
CREATE TABLE docs_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    title TEXT,
    text_content TEXT,
    char_count INTEGER,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_email, doc_id)
);
```

### Natural key: `(subject_email, doc_id)`

### Persisted columns:
| Column | Source |
|--------|--------|
| `subject_email` | Impersonated user |
| `doc_id` | Google Drive file ID |
| `title` | `files().get().name` |
| `text_content` | `files().export()` plain text |
| `char_count` | `len(text_content)` |
| `raw_json` | JSON-encoded file metadata |
| `created_at` | First insert timestamp |
| `updated_at` | Last upsert timestamp |

### NOT persisted:
- Binary exports (PDF, DOCX, etc.)
- Rich formatting (bold, italic, headings)
- Comments and suggestions
- Revision history
- Embedded images

---

## 5) FAILURE TAXONOMY

| Error Class | Meaning | Fail Run? | Advance Cursor? |
|-------------|---------|-----------|-----------------|
| `missing_404` | File deleted, permission revoked, or trashed between Drive listing and export | NO | N/A (no cursor) |
| `transient_5xx` | Google backend error (server overload, temporary outage) | NO | N/A |
| `rate_limit` | API quota exceeded | DEPENDS | N/A |
| `quota_exceeded` | Daily quota exhausted | YES (retry later) | N/A |
| `other_err` | Network errors, decode failures, unexpected exceptions | NO | N/A |

**Cursor note:** Docs does NOT have its own cursor. It processes doc_ids discovered by Drive.
The Drive cursor (`last_modified_time`) governs what files are discovered.

### Error handling behavior (current):
```python
except HttpError as e:
    if e.resp.status == 404:
        missing_404 += 1  # Counted, not logged per-item
    elif e.resp.status >= 500:
        transient_5xx += 1  # Counted, not logged per-item
    else:
        other_err += 1
        debug_print(...)  # Only logged with AUTH_DEBUG=1
    continue  # Skip to next doc, don't fail run
```

---

## 6) PERFORMANCE PROFILE

### Call count formula:
```
Total API calls = N_docs × 2
                = N_docs × (1 get + 1 export)
```

### Per-subject breakdown:
| Subject | Docs | API Calls | Est. Time (0.5s/call) |
|---------|------|-----------|----------------------|
| ramy@hrmny.co | 470 | 940 | ~8 min |
| ayman@hrmny.co | 437 | 874 | ~7 min |
| molham@hrmny.co | 437 | 874 | ~7 min |
| joshua@hrmny.co | 385 | 770 | ~6 min |
| **ALL 20** | ~4,252 | ~8,504 | **~71 min** |

### Why Docs dominates runtime:
1. **Single-threaded:** Each API call blocks until response
2. **No batching:** Google Drive API doesn't support batch export
3. **Large payloads:** Plain text export can be 100KB+ per doc
4. **Long tail:** Last subject still takes 8+ minutes even with good parallelism

### Why this causes mid-run kills:
```
Scenario: 4,252 docs × 0.5s/call = 71 minutes
- User/cron timeout: Often 30-60 min
- Signal SIGTERM/SIGKILL arrives mid-run
- Without per-doc persistence, all progress lost
- Without resume cursor, next run starts from scratch
```

**Current mitigation:** None. If killed, no docs progress is saved.

---

## 7) GAP ANALYSIS

| Metric | Value |
|--------|-------|
| Total Google Docs in drive_files | ~4,252 |
| Total docs_documents rows | 318 |
| Subjects with Docs data | 1 (aubrey@hrmny.co) |
| Subjects with 0 Docs data | 19 |
| Extraction rate | 7.5% |

**Root cause:** Docs collection runs after all other services per-subject. If run times out or is killed before reaching Docs for most subjects, those subjects get 0 Docs coverage.

---

## DEFERRED TO PROMPT 07

The following are explicitly NOT addressed here:
- [ ] Per-doc cursor/resume mechanism
- [ ] Aggregated counter logging (already implemented)
- [ ] Streaming persistence improvements
- [ ] Parallelization options

**Constraint:** Docs implementation changes belong ONLY in Prompt 07.

---

*Generated: 2026-02-13T02:15:00+04:00*
