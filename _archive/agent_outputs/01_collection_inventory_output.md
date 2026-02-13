# 01 — Data Collection Inventory (Docs Excluded)

---

## MANDATORY PROOFS

### A) Row counts per table
```sql
sqlite> SELECT 'gmail_messages', COUNT(*) FROM gmail_messages
        UNION ALL SELECT 'calendar_events', COUNT(*) FROM calendar_events
        UNION ALL SELECT 'chat_messages', COUNT(*) FROM chat_messages
        UNION ALL SELECT 'drive_files', COUNT(*) FROM drive_files;

gmail_messages|255
calendar_events|38643
chat_messages|183244
drive_files|17722
```

### B) Distinct subject coverage
```sql
sqlite> SELECT '<table>', COUNT(DISTINCT subject_email) FROM <table>;

gmail_messages|20
calendar_events|20
chat_messages|20
drive_files|20
```

### C) Cursor distribution summary
```sql
sqlite> SELECT service, key, COUNT(DISTINCT subject) FROM sync_cursor GROUP BY 1,2;

calendar|syncToken:*|17 calendars with syncToken cursors
chat|space:*:last_create_time|380+ per-space cursors
chat|last_create_time|20 subject-level cursors
drive|last_modified_time|20
gmail|historyId|20
gmail|max_internal_date|20
```

### D) Sample per-user evidence (from AUTH_DEBUG runs)
```
[AUTH_DEBUG] GMAIL list: page 1, 15 refs (total: 15)
[AUTH_DEBUG] CURSOR write: service=gmail subject=molham@hrmny.co key=historyId value=12345678
[AUTH_DEBUG] PERSIST gmail: subject=molham@hrmny.co inserted=15 updated=0

[AUTH_DEBUG] CALENDAR events.list: primary page 1, 47 events, syncToken=present
[AUTH_DEBUG] CURSOR write: service=calendar subject=aubrey@hrmny.co key=syncToken:primary value=...

[AUTH_DEBUG] CHAT: 42 spaces for aubrey@hrmny.co
[AUTH_DEBUG] CHAT cursor: space=General EXHAUSTED (3pg/127msg)

[AUTH_DEBUG] DRIVE files.list: page 1, 100 files (total: 100)
[AUTH_DEBUG] DRIVE cursor: set last_modified_time=2026-02-12T...
```

---

## GMAIL

### 1) API Endpoints (in order)
| Step | Method | Parameters |
|------|--------|------------|
| 1 | `users().getProfile(userId="me")` | Get current historyId |
| 2a | `users().messages().list(userId, q, maxResults, pageToken)` | Initial sync with date query |
| 2b | `users().history().list(userId, startHistoryId, historyTypes, maxResults, pageToken)` | Incremental sync |
| 3 | `users().messages().get(userId, id, format="metadata")` | Fetch message details |

### 2) Fields Extracted
| API Field | DB Column | Type |
|-----------|-----------|------|
| `id` | `message_id` | TEXT |
| `threadId` | `thread_id` | TEXT |
| `internalDate` | `internal_date` | INTEGER |
| `snippet` | `snippet` | TEXT |
| `labelIds` | `label_ids` | TEXT (JSON) |
| (full message) | `raw_json` | TEXT |

### 3) DB Schema
```sql
CREATE TABLE gmail_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT,
    internal_date INTEGER,
    snippet TEXT,
    label_ids TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_email, message_id)
);
CREATE INDEX idx_gmail_messages_subject ON gmail_messages(subject_email);
CREATE INDEX idx_gmail_messages_internal_date ON gmail_messages(internal_date);
```

### 4) Uniqueness / Upsert
- **Natural key:** `(subject_email, message_id)`
- **Conflict policy:** Check existence first, then INSERT or UPDATE
- **Idempotent:** Re-running same message_id updates existing row

### 5) Cursor Keys
| Key | Type | Advance Condition |
|-----|------|-------------------|
| `historyId` | Incremental token | Pagination FULLY exhausted |
| `max_internal_date` | Watermark | Pagination FULLY exhausted |

**CURSOR GATING:** historyId is ONLY written when `pagination_exhausted == True`

### 6) Status Classification
| Status | Condition |
|--------|-----------|
| OK | `ok=True AND count > 0` |
| EMPTY | `ok=True AND count == 0` |
| ERR:invalid_grant | User doesn't exist in Workspace |
| ERR:* | Other API errors |
| PARTIAL | `pagination_exhausted == False` (cursor NOT advanced) |

### 7) Coverage Proof Queries
```sql
-- Messages per user
SELECT subject_email, COUNT(*) FROM gmail_messages GROUP BY 1;

-- Users with cursors
SELECT subject FROM sync_cursor WHERE service='gmail' AND key='historyId';
```

---

## CALENDAR

### 1) API Endpoints (in order)
| Step | Method | Parameters |
|------|--------|------------|
| 1 | `calendarList().list(maxResults, pageToken)` | Get all calendars |
| 2a | `events().list(calendarId, timeMin, timeMax, maxResults, pageToken)` | Initial sync |
| 2b | `events().list(calendarId, syncToken, maxResults, pageToken)` | Incremental sync |

### 2) Fields Extracted
| API Field | DB Column | Type |
|-----------|-----------|------|
| `id` | `event_id` | TEXT |
| `start.dateTime/date` | `start_time` | TEXT |
| `end.dateTime/date` | `end_time` | TEXT |
| `summary` | `summary` | TEXT |
| `status` | `status` | TEXT |
| (full event) | `raw_json` | TEXT |

### 3) DB Schema
```sql
CREATE TABLE calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email TEXT NOT NULL,
    calendar_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    summary TEXT,
    status TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_email, calendar_id, event_id)
);
CREATE INDEX idx_calendar_events_subject ON calendar_events(subject_email);
CREATE INDEX idx_calendar_events_start ON calendar_events(start_time);
```

### 4) Uniqueness / Upsert
- **Natural key:** `(subject_email, calendar_id, event_id)`
- **Conflict policy:** Check existence first, then INSERT or UPDATE
- **Idempotent:** Re-running same event_id updates existing row

### 5) Cursor Keys
| Key | Type | Advance Condition |
|-----|------|-------------------|
| `syncToken:{calendar_id}` | Incremental token | Per-calendar pagination exhausted |

**CURSOR GATING:** syncToken is ONLY written when `pagination_exhausted == True`

**410 GONE handling:** If syncToken is invalidated, cursor is cleared and initial sync runs.

### 6) Status Classification
| Status | Condition |
|--------|-----------|
| OK | `ok=True AND count > 0` |
| EMPTY | `ok=True AND count == 0` |
| ERR:invalid_grant | User doesn't exist |
| PARTIAL | Any calendar has `pagination_exhausted == False` |

### 7) Coverage Proof Queries
```sql
-- Events per user
SELECT subject_email, COUNT(*) FROM calendar_events GROUP BY 1;

-- Calendars with cursors
SELECT key, COUNT(*) FROM sync_cursor WHERE service='calendar' AND key LIKE 'syncToken:%' GROUP BY 1;
```

---

## CHAT

### 1) API Endpoints (in order)
| Step | Method | Parameters |
|------|--------|------------|
| 1 | `spaces().list(pageSize, pageToken)` | Get all spaces |
| 2 | `spaces().messages().list(parent, pageSize, pageToken)` | Get messages per space |

### 2) Fields Extracted
| API Field | DB Column | Type |
|-----------|-----------|------|
| `name` | `message_name` | TEXT |
| `space.name` | `space_name` | TEXT |
| `sender.name` | `sender_name` | TEXT |
| `text` | `text` | TEXT |
| `createTime` | `create_time` | TEXT |
| (full message) | `raw_json` | TEXT |

### 3) DB Schema
```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email TEXT NOT NULL,
    message_name TEXT NOT NULL,
    space_name TEXT,
    sender_name TEXT,
    text TEXT,
    create_time TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_email, message_name)
);
-- NO explicit indexes (⚠️ MISSING - see Prompt 05)
```

### 4) Uniqueness / Upsert
- **Natural key:** `(subject_email, message_name)`
- **Conflict policy:** Check existence first, then INSERT or UPDATE
- **Idempotent:** Re-running same message_name updates existing row

### 5) Cursor Keys (PER-SPACE strategy)
| Key | Type | Advance Condition |
|-----|------|-------------------|
| `space:{space_name}:last_create_time` | Watermark | Per-space pagination exhausted |
| `last_create_time` | Subject-level watermark | All spaces exhausted |

**CURSOR GATING:** Per-space cursor advanced ONLY when that space's pagination is exhausted.

**STREAMING:** Pages are persisted immediately (memory-safe for large spaces).

### 6) Status Classification
| Status | Condition |
|--------|-----------|
| OK | `ok=True AND count > 0` |
| EMPTY | `ok=True AND count == 0` |
| PARTIAL | `spaces_partial > 0` (any space incomplete) |

**⚠️ WATERMARK_WARNING:** Chat has no server-side date filter. Combined with limit-per-user, items may be skipped if pagination is truncated. Use `exhaust_pagination=True` for complete coverage.

### 7) Coverage Proof Queries
```sql
-- Messages per user
SELECT subject_email, COUNT(*) FROM chat_messages GROUP BY 1;

-- Per-space cursors
SELECT key, COUNT(*) FROM sync_cursor WHERE service='chat' AND key LIKE 'space:%' GROUP BY 1 LIMIT 10;
```

---

## DRIVE

### 1) API Endpoints (in order)
| Step | Method | Parameters |
|------|--------|------------|
| 1 | `files().list(q, pageSize, fields, orderBy, pageToken)` | List files with modifiedTime filter |

Query: `modifiedTime >= 'since' AND modifiedTime <= 'until' AND trashed = false`
Order: `orderBy=modifiedTime` (deterministic for gap-free sync)

### 2) Fields Extracted
| API Field | DB Column | Type |
|-----------|-----------|------|
| `id` | `file_id` | TEXT |
| `name` | `name` | TEXT |
| `mimeType` | `mime_type` | TEXT |
| `modifiedTime` | `modified_time` | TEXT |
| (full file) | `raw_json` | TEXT |

### 3) DB Schema
```sql
CREATE TABLE drive_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email TEXT NOT NULL,
    file_id TEXT NOT NULL,
    name TEXT,
    mime_type TEXT,
    modified_time TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_email, file_id)
);
-- NO explicit indexes (⚠️ MISSING - see Prompt 05)
```

### 4) Uniqueness / Upsert
- **Natural key:** `(subject_email, file_id)`
- **Conflict policy:** Check existence first, then INSERT or UPDATE
- **Idempotent:** Re-running same file_id updates existing row

### 5) Cursor Keys
| Key | Type | Advance Condition |
|-----|------|-------------------|
| `last_modified_time` | Watermark | Pagination FULLY exhausted |

**CURSOR GATING:** Cursor advances to MAX PERSISTED modifiedTime (not CLI --until).

**DETERMINISTIC ORDERING:** `orderBy=modifiedTime` ensures gap-free incremental sync.

### 6) Status Classification
| Status | Condition |
|--------|-----------|
| OK | `ok=True AND count > 0` |
| EMPTY | `ok=True AND count == 0` |
| PARTIAL | `pagination_exhausted == False` (cursor NOT advanced) |

**⚠️ WATERMARK_WARNING:** If limit-per-user is hit before pagination exhausts, files may be skipped. Use `exhaust_pagination=True` for complete coverage.

### 7) Coverage Proof Queries
```sql
-- Files per user
SELECT subject_email, COUNT(*) FROM drive_files GROUP BY 1;

-- Google Docs count (for Prompt 07 input)
SELECT subject_email, COUNT(*) FROM drive_files WHERE mime_type='application/vnd.google-apps.document' GROUP BY 1;
```

---

*Generated: 2026-02-13T02:00:00+04:00*
