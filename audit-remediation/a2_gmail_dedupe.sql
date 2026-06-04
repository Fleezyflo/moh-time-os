-- Phase A2 — gmail relation table dedupe + UNIQUE indexes + VACUUM
-- RUN ON MOLHAM'S MAC ONLY (live DB). Daemon/API must be STOPPED (verified stopped).
-- Do NOT restart the daemon/API until Phase C2 lands.
-- The wrapper command takes a .backup to /tmp/moh_pre_dedupe.db BEFORE invoking this script.
--
-- Verified against the live DB on a single quiescent connection (2026-05-31):
--   gmail_participants : key (message_id, role, email)                                  6,133,839 -> 6,823
--   gmail_labels       : key (message_id, label_id)                                     4,103,337 -> 4,647
--   gmail_attachments  : key (message_id, filename, mime_type, size_bytes, attachment_id) 3,379,707 (0 dups)
-- All natural-key columns are NULL-free, so MIN(id) dedupe + UNIQUE index are fully effective.
-- gmail_attachments has ZERO duplicates -> no DELETE, only the UNIQUE index (defense-in-depth).
--
-- Root cause: lib/collectors/gmail.py inserts via StateStore.insert_many, which uses
-- "INSERT OR REPLACE" (lib/safe_sql.py:99). With no UNIQUE natural-key constraint, OR REPLACE
-- never finds a conflict, so every re-collection appends. These UNIQUE indexes make OR REPLACE
-- correctly replace instead of duplicate -- no collector code change required.

.timeout 120000

BEGIN IMMEDIATE;

-- 1) Dedupe: keep the lowest id per natural key. (attachments skipped -- already unique)
DELETE FROM gmail_participants
 WHERE id NOT IN (SELECT MIN(id) FROM gmail_participants GROUP BY message_id, role, email);

DELETE FROM gmail_labels
 WHERE id NOT IN (SELECT MIN(id) FROM gmail_labels GROUP BY message_id, label_id);

COMMIT;

-- 2) Enforce uniqueness at the DB level so bloat cannot recur regardless of writer.
CREATE UNIQUE INDEX IF NOT EXISTS idx_gmail_participants_uniq
    ON gmail_participants(message_id, role, email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_gmail_labels_uniq
    ON gmail_labels(message_id, label_id);
-- SUPERSEDED by a2_attachments_fix.sql: this 5-col key INCLUDES attachment_id, which Gmail
-- regenerates per fetch, so it can NOT prevent re-collection bloat. The correct key is the
-- 4-col stable key (no attachment_id). Do NOT use the line below on a fresh DB; run
-- a2_attachments_fix.sql instead. Kept here only as a record of what was originally run.
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_gmail_attachments_uniq
--     ON gmail_attachments(message_id, filename, mime_type, size_bytes, attachment_id);

-- 3) Reclaim disk (3.0 GB -> ~0.5 GB expected).
VACUUM;

-- 4) Verify (expect the distinct counts below; the *_uniq indexes must appear).
SELECT 'participants', COUNT(*) FROM gmail_participants;   -- expect 6823
SELECT 'labels',       COUNT(*) FROM gmail_labels;         -- expect 4647
SELECT 'attachments',  COUNT(*) FROM gmail_attachments;    -- expect 3379707
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_gmail_%_uniq' ORDER BY name;
