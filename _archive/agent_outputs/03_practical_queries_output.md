# 03 — Practical Use Cases (SQL Queries, Docs Excluded)

---

## MANDATORY PROOFS

### A) Counts + distinct subjects
```
tbl|rows|subjects
gmail_messages|255|20
calendar_events|38643|20
chat_messages|183244|20
drive_files|17722|20
```

### B) Timestamp ranges
```
tbl|min_time|max_time
chat_messages|2025-06-01T12:25:44.014319Z|2026-02-12T17:48:08.140127Z
calendar_events|2025-05-28T11:00:00+04:00|2026-02-13
drive_files|2025-06-01T09:13:20.000Z|2026-02-12T17:44:11.615Z
```

### C) Top-N sanity checks

**C1: Top 10 spaces by volume (chat)**
```
space_name|msg_count
spaces/AAQA96lTbFo|17204
spaces/AAQAeCfr53E|14290
spaces/AAQAW-_Vho8|7440
spaces/AAQAYXH_4mw|7170
spaces/AAQAYACvnBE|6269
```

**C2: Top 10 people by meetings (calendar)**
```
subject_email|event_count
joshua@hrmny.co|8682
raafat@hrmny.co|7545
aubrey@hrmny.co|5734
krystie@hrmny.co|3164
eifel@hrmny.co|3079
```

**C3: Top 10 modified files (drive)**
```
name|mime_type|modified_time
MOH Time OS v2.0 - 2026-01-17T15-25-55|spreadsheet|2026-02-12T17:44:11.615Z
HRMNY Timeline OS Data|spreadsheet|2026-02-12T17:26:51.787Z
[hrmny] 2026 GMG: Supermarkets Content Architecture|presentation|2026-02-12T14:39:50.507Z
```

**C4: Top 10 gmail label combinations**
```
label_ids|count
["UNREAD", "CATEGORY_UPDATES", "INBOX"]|72
["UNREAD", "IMPORTANT", "CATEGORY_PERSONAL", "INBOX"]|20
["UNREAD", "Label_31", "CATEGORY_PERSONAL", "INBOX"]|19
```

---

## READY NOW QUERY PACK (15+ queries)

### A) Activity / Volume

#### Q1: Daily message volume by service
```sql
-- Intent: Time series of daily activity per service
SELECT 
  DATE(create_time) as day,
  'chat' as service,
  COUNT(*) as volume
FROM chat_messages
WHERE create_time >= DATE('now', '-30 days')
GROUP BY 1
ORDER BY 1 DESC
LIMIT 30;
```
**Output columns:** `day, service, volume`
**Assumption:** create_time is ISO8601 format

#### Q2: Activity by hour of day (chat)
```sql
-- Intent: Find peak collaboration hours
SELECT 
  CAST(SUBSTR(create_time, 12, 2) AS INTEGER) as hour_utc,
  COUNT(*) as messages
FROM chat_messages
GROUP BY 1
ORDER BY 1;
```
**Output columns:** `hour_utc, messages`
**Assumption:** create_time format is YYYY-MM-DDTHH:MM:SS

#### Q3: Events per month (calendar)
```sql
-- Intent: Monthly meeting volume trend
SELECT 
  SUBSTR(start_time, 1, 7) as month,
  COUNT(*) as events
FROM calendar_events
WHERE start_time IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC
LIMIT 12;
```
**Output columns:** `month, events`

#### Q4: File types distribution (drive)
```sql
-- Intent: Understand file ecosystem
SELECT 
  REPLACE(mime_type, 'application/vnd.google-apps.', '') as type,
  COUNT(*) as count
FROM drive_files
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10;
```
**Output columns:** `type, count`

---

### B) People / Collaboration Graph

#### Q5: Most active chat participants
```sql
-- Intent: Top chat contributors
SELECT 
  sender_name,
  COUNT(*) as messages
FROM chat_messages
WHERE sender_name IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;
```
**Output columns:** `sender_name, messages`

#### Q6: Meeting load by person
```sql
-- Intent: Identify meeting-heavy individuals
SELECT 
  subject_email,
  COUNT(*) as total_events,
  COUNT(DISTINCT DATE(start_time)) as days_with_events
FROM calendar_events
WHERE start_time >= DATE('now', '-30 days')
GROUP BY 1
ORDER BY 2 DESC;
```
**Output columns:** `subject_email, total_events, days_with_events`

#### Q7: Spaces per person (chat)
```sql
-- Intent: Collaboration breadth
SELECT 
  subject_email,
  COUNT(DISTINCT space_name) as unique_spaces,
  COUNT(*) as total_messages
FROM chat_messages
GROUP BY 1
ORDER BY 2 DESC;
```
**Output columns:** `subject_email, unique_spaces, total_messages`

---

### C) Time Series and Trends

#### Q8: Weekly chat activity trend
```sql
-- Intent: Week-over-week comparison
SELECT 
  STRFTIME('%Y-W%W', create_time) as week,
  COUNT(*) as messages
FROM chat_messages
GROUP BY 1
ORDER BY 1 DESC
LIMIT 12;
```
**Output columns:** `week, messages`

#### Q9: Calendar event status breakdown
```sql
-- Intent: Understand event completion/cancellation rates
SELECT 
  status,
  COUNT(*) as count
FROM calendar_events
GROUP BY 1
ORDER BY 2 DESC;
```
**Output columns:** `status, count`

#### Q10: Files modified per day
```sql
-- Intent: Drive activity trend
SELECT 
  DATE(modified_time) as day,
  COUNT(*) as files_modified
FROM drive_files
WHERE modified_time >= DATE('now', '-30 days')
GROUP BY 1
ORDER BY 1 DESC;
```
**Output columns:** `day, files_modified`

---

### D) Cross-Service Joins

#### Q11: People active in both chat and calendar
```sql
-- Intent: Cross-platform engagement
SELECT 
  c.subject_email,
  c.chat_msgs,
  e.calendar_events
FROM (
  SELECT subject_email, COUNT(*) as chat_msgs 
  FROM chat_messages GROUP BY 1
) c
JOIN (
  SELECT subject_email, COUNT(*) as calendar_events 
  FROM calendar_events GROUP BY 1
) e ON c.subject_email = e.subject_email
ORDER BY c.chat_msgs DESC;
```
**Output columns:** `subject_email, chat_msgs, calendar_events`
**Assumption:** subject_email matches across tables

#### Q12: Chat + Drive activity correlation
```sql
-- Intent: Who shares files AND chats
SELECT 
  c.subject_email,
  c.chat_msgs,
  d.drive_files
FROM (
  SELECT subject_email, COUNT(*) as chat_msgs 
  FROM chat_messages GROUP BY 1
) c
JOIN (
  SELECT subject_email, COUNT(*) as drive_files 
  FROM drive_files GROUP BY 1
) d ON c.subject_email = d.subject_email
ORDER BY d.drive_files DESC;
```
**Output columns:** `subject_email, chat_msgs, drive_files`

#### Q13: Full activity summary per person
```sql
-- Intent: Complete activity profile
SELECT 
  p.email,
  COALESCE(g.gmail, 0) as gmail,
  COALESCE(c.calendar, 0) as calendar,
  COALESCE(ch.chat, 0) as chat,
  COALESCE(d.drive, 0) as drive
FROM people p
LEFT JOIN (SELECT subject_email, COUNT(*) as gmail FROM gmail_messages GROUP BY 1) g ON p.email = g.subject_email
LEFT JOIN (SELECT subject_email, COUNT(*) as calendar FROM calendar_events GROUP BY 1) c ON p.email = c.subject_email
LEFT JOIN (SELECT subject_email, COUNT(*) as chat FROM chat_messages GROUP BY 1) ch ON p.email = ch.subject_email
LEFT JOIN (SELECT subject_email, COUNT(*) as drive FROM drive_files GROUP BY 1) d ON p.email = d.subject_email
WHERE p.type = 'internal'
ORDER BY chat DESC;
```
**Output columns:** `email, gmail, calendar, chat, drive`

---

### E) Data Quality Checks

#### Q14: Null field audit
```sql
-- Intent: Find missing data
SELECT 
  'chat_messages' as tbl,
  SUM(CASE WHEN space_name IS NULL THEN 1 ELSE 0 END) as null_space,
  SUM(CASE WHEN sender_name IS NULL THEN 1 ELSE 0 END) as null_sender,
  SUM(CASE WHEN create_time IS NULL THEN 1 ELSE 0 END) as null_time
FROM chat_messages
UNION ALL
SELECT 
  'calendar_events',
  SUM(CASE WHEN summary IS NULL THEN 1 ELSE 0 END),
  SUM(CASE WHEN status IS NULL THEN 1 ELSE 0 END),
  SUM(CASE WHEN start_time IS NULL THEN 1 ELSE 0 END)
FROM calendar_events;
```
**Output columns:** `tbl, null_space, null_sender, null_time`

#### Q15: Duplicate check (should be 0)
```sql
-- Intent: Verify UNIQUE constraints work
SELECT 
  'gmail' as svc,
  COUNT(*) - COUNT(DISTINCT subject_email || '|' || message_id) as duplicates
FROM gmail_messages
UNION ALL
SELECT 
  'chat',
  COUNT(*) - COUNT(DISTINCT subject_email || '|' || message_name)
FROM chat_messages
UNION ALL
SELECT 
  'drive',
  COUNT(*) - COUNT(DISTINCT subject_email || '|' || file_id)
FROM drive_files;
```
**Output columns:** `svc, duplicates`
**Constraint:** duplicates should always be 0

#### Q16: Outlier detection - unusually large raw_json
```sql
-- Intent: Find potential data issues
SELECT 
  'chat_messages' as tbl,
  MAX(LENGTH(raw_json)) as max_json_bytes,
  AVG(LENGTH(raw_json)) as avg_json_bytes
FROM chat_messages
UNION ALL
SELECT 'calendar_events', MAX(LENGTH(raw_json)), AVG(LENGTH(raw_json)) FROM calendar_events
UNION ALL
SELECT 'drive_files', MAX(LENGTH(raw_json)), AVG(LENGTH(raw_json)) FROM drive_files;
```
**Output columns:** `tbl, max_json_bytes, avg_json_bytes`

---

## Coverage Summary

| Table | Rows | Subjects | Min Time | Max Time |
|-------|------|----------|----------|----------|
| gmail_messages | 255 | 20 | N/A (internal_date integer) | N/A |
| calendar_events | 38,643 | 20 | 2025-05-28 | 2026-02-13 |
| chat_messages | 183,244 | 20 | 2025-06-01 | 2026-02-12 |
| drive_files | 17,722 | 20 | 2025-06-01 | 2026-02-12 |

---

*Generated: 2026-02-13T02:10:00+04:00*
