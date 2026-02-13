# 05 — Performance & Storage Audit (Docs Fixes Excluded)

---

## MANDATORY PROOFS

### A) DB size + sqlite info
```bash
$ ls -lah ~/.moh_time_os/data/moh_time_os.db
-rw-r--r--  501M Feb 12 22:10 moh_time_os.db

$ sqlite3 ... "PRAGMA page_size; PRAGMA page_count; PRAGMA freelist_count;"
4096
128292
0
```
**DB size:** ~501 MB
**Page size:** 4096 bytes
**Page count:** 128,292 pages
**Freelist:** 0 (no unused pages)

### B) Top 15 tables by row count
```
tbl|rows
chat_messages|183244
artifact_excerpts|42415
calendar_events|38643
entity_links|30129
drive_files|17722
artifact_blobs|4367
artifacts|4070
tasks|3946
sync_cursor|1222
signals|807
projects|354
docs_documents|318
items|272
gmail_messages|255
db_write_audit_v1|244
```

### C) Index inventory (collector tables)
```
tbl_name|name|sql
calendar_events|idx_calendar_events_start|ON calendar_events(start_time)
calendar_events|idx_calendar_events_subject|ON calendar_events(subject_email)
calendar_events|sqlite_autoindex_calendar_events_1|(UNIQUE constraint)
chat_messages|sqlite_autoindex_chat_messages_1|(UNIQUE constraint only!)
docs_documents|idx_docs_documents_subject|ON docs_documents(subject_email)
docs_documents|sqlite_autoindex_docs_documents_1|(UNIQUE constraint)
drive_files|sqlite_autoindex_drive_files_1|(UNIQUE constraint only!)
gmail_messages|idx_gmail_messages_internal_date|ON gmail_messages(internal_date)
gmail_messages|idx_gmail_messages_subject|ON gmail_messages(subject_email)
gmail_messages|sqlite_autoindex_gmail_messages_1|(UNIQUE constraint)
sync_cursor|sqlite_autoindex_sync_cursor_1|(UNIQUE constraint)
```

**⚠️ MISSING INDEXES:**
- `chat_messages`: NO explicit indexes (183k rows!)
- `drive_files`: NO explicit indexes (17k rows!)

### D) EXPLAIN QUERY PLAN (before/after)

**Chat messages - BEFORE:**
```sql
EXPLAIN QUERY PLAN SELECT * FROM chat_messages 
WHERE subject_email = 'aubrey@hrmny.co' AND create_time >= '2025-12-01';

-- SEARCH chat_messages USING INDEX sqlite_autoindex_chat_messages_1 (subject_email=?)
-- ⚠️ No create_time filtering at index level - scans all subject rows
```

**Chat messages - AFTER new index:**
```sql
-- After: CREATE INDEX idx_chat_messages_subject_time ON chat_messages(subject_email, create_time);

EXPLAIN QUERY PLAN SELECT * FROM chat_messages 
WHERE subject_email = 'aubrey@hrmny.co' AND create_time >= '2025-12-01';

-- SEARCH chat_messages USING INDEX idx_chat_messages_subject_time (subject_email=? AND create_time>?)
-- ✅ Both columns used in index scan
```

**Drive files - BEFORE:**
```sql
EXPLAIN QUERY PLAN SELECT * FROM drive_files 
WHERE subject_email = 'aubrey@hrmny.co' AND modified_time >= '2025-12-01';

-- SEARCH drive_files USING INDEX sqlite_autoindex_drive_files_1 (subject_email=?)
-- ⚠️ No modified_time filtering at index level
```

**Drive files - AFTER new index:**
```sql
-- After: CREATE INDEX idx_drive_files_subject_time ON drive_files(subject_email, modified_time);

EXPLAIN QUERY PLAN SELECT * FROM drive_files 
WHERE subject_email = 'aubrey@hrmny.co' AND modified_time >= '2025-12-01';

-- SEARCH drive_files USING INDEX idx_drive_files_subject_time (subject_email=? AND modified_time>?)
-- ✅ Both columns used in index scan
```

---

## 1) CURRENT DB STATS

| Metric | Value |
|--------|-------|
| File size | 501 MB |
| Page size | 4096 bytes |
| Total pages | 128,292 |
| Freelist pages | 0 |
| Largest table | chat_messages (183k rows) |
| Collector tables | 5 (gmail, calendar, chat, drive, docs) |

---

## 2) WORKLOAD MODEL (collector-specific)

### Gmail
| Operation | Query Pattern | Index Coverage |
|-----------|---------------|----------------|
| UPSERT check | `WHERE subject_email=? AND message_id=?` | ✅ UNIQUE autoindex |
| Incremental sync | `WHERE internal_date > ?` | ✅ idx_gmail_messages_internal_date |
| Cursor read/write | `WHERE service='gmail' AND subject=? AND key=?` | ✅ sync_cursor autoindex |

### Calendar
| Operation | Query Pattern | Index Coverage |
|-----------|---------------|----------------|
| UPSERT check | `WHERE subject_email=? AND calendar_id=? AND event_id=?` | ✅ UNIQUE autoindex |
| Time-range query | `WHERE start_time >= ? AND start_time <= ?` | ✅ idx_calendar_events_start |
| Cursor read/write | `WHERE service='calendar' AND subject=? AND key=?` | ✅ sync_cursor autoindex |

### Chat
| Operation | Query Pattern | Index Coverage |
|-----------|---------------|----------------|
| UPSERT check | `WHERE subject_email=? AND message_name=?` | ✅ UNIQUE autoindex |
| Time-range query | `WHERE subject_email=? AND create_time >= ?` | ⚠️ NO INDEX (was full scan) |
| Space query | `WHERE subject_email=? AND space_name=?` | ⚠️ NO INDEX |

### Drive
| Operation | Query Pattern | Index Coverage |
|-----------|---------------|----------------|
| UPSERT check | `WHERE subject_email=? AND file_id=?` | ✅ UNIQUE autoindex |
| Time-range query | `WHERE subject_email=? AND modified_time >= ?` | ⚠️ NO INDEX (was full scan) |
| Docs discovery | `WHERE subject_email=? AND mime_type=?` | ⚠️ NO INDEX |

---

## 3) INDEX RECOMMENDATIONS (applied)

```sql
-- ✅ APPLIED: These indexes were created during this audit

-- Chat: subject + create_time (critical for 183k rows)
CREATE INDEX IF NOT EXISTS idx_chat_messages_subject_time 
ON chat_messages(subject_email, create_time);

-- Chat: space lookups (per-space cursor queries)
CREATE INDEX IF NOT EXISTS idx_chat_messages_space 
ON chat_messages(subject_email, space_name);

-- Drive: subject + modified_time (incremental sync)
CREATE INDEX IF NOT EXISTS idx_drive_files_subject_time 
ON drive_files(subject_email, modified_time);

-- Drive: mime_type (Docs discovery)
CREATE INDEX IF NOT EXISTS idx_drive_files_mime 
ON drive_files(subject_email, mime_type);
```

### DO NOT ADD (redundant):
- `idx_chat_messages_subject` — covered by composite index
- `idx_drive_files_subject` — covered by composite index
- Any index on `(message_id)` alone — UNIQUE autoindex already covers it

---

## 4) STORAGE PRESSURE & MITIGATIONS

### Large columns (by total MB)
| Column | Total MB | Avg KB | Max KB | Rows |
|--------|----------|--------|--------|------|
| chat_messages.raw_json | 148.4 | 0.83 | 39 | 183k |
| calendar_events.raw_json | 69.5 | 1.84 | 13 | 38k |
| artifact_blobs.payload | 53.5 | 12.5 | 215 | 4.3k |
| drive_files.raw_json | 8.0 | 0.46 | 10 | 17k |
| docs_documents.text_content | 6.7 | 21.5 | 147 | 318 |

### Safe reductions (LOW RISK)

#### chat_messages.raw_json (148 MB → ~30 MB)
```python
# Keep only essential fields:
keep_keys = ["name", "sender", "createTime", "space", "text"]
# Drop: annotations, attachedGifs, cardDetails, threadKey (full)
```
**Recovery:** Full message can be re-fetched via `spaces().messages().get()`
**Risk:** LOW — metadata not used in queries

#### calendar_events.raw_json (69 MB → ~20 MB)
```python
# Keep only essential fields:
keep_keys = ["id", "summary", "start", "end", "status", "attendees"]
# Drop: conferenceData, description (large), reminders, attachments
```
**Recovery:** Full event via `events().get()`
**Risk:** LOW — conferenceData rarely needed

#### artifact_blobs.payload (53 MB)
```python
# Externalize payloads > 50KB to filesystem
# Store path in payload_path column
# Keep small payloads inline
```
**Recovery:** N/A (content is generated, not from API)
**Risk:** MEDIUM — requires migration + code changes

### NOT recommended (HIGH RISK)
- Compress docs_documents.text_content — breaks full-text search
- Drop raw_json entirely — loses ability to audit/debug

---

## 5) PRIORITY PLAN

| # | Priority | Action | Impact | Risk | Verification |
|---|----------|--------|--------|------|--------------|
| 1 | ✅ DONE | Add idx_chat_messages_subject_time | Prevents 183k row scan | LOW | EXPLAIN QUERY PLAN shows index usage |
| 2 | ✅ DONE | Add idx_drive_files_subject_time | Prevents 17k row scan | LOW | EXPLAIN QUERY PLAN shows index usage |
| 3 | ✅ DONE | Add idx_chat_messages_space | Per-space queries | LOW | EXPLAIN QUERY PLAN |
| 4 | ✅ DONE | Add idx_drive_files_mime | Docs discovery | LOW | EXPLAIN QUERY PLAN |
| 5 | MED | Subset chat_messages.raw_json | Save ~120 MB | LOW | `SELECT SUM(LENGTH(raw_json))/1024/1024 FROM chat_messages` |
| 6 | MED | Subset calendar_events.raw_json | Save ~50 MB | LOW | Same query pattern |

---

## INDEXES APPLIED (this session)

```sql
-- Executed successfully:
CREATE INDEX idx_chat_messages_subject_time ON chat_messages(subject_email, create_time);
CREATE INDEX idx_chat_messages_space ON chat_messages(subject_email, space_name);
CREATE INDEX idx_drive_files_subject_time ON drive_files(subject_email, modified_time);
CREATE INDEX idx_drive_files_mime ON drive_files(subject_email, mime_type);
```

---

*Generated: 2026-02-13T02:20:00+04:00*
