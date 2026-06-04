-- Phase A2 (correction) — fix gmail_attachments bloat with the STABLE natural key.
-- Run on the live DB (daemon stopped). Backup already exists at /tmp/moh_pre_dedupe.db.
--
-- WHY this corrects the earlier attempt:
--   gmail_attachments was keyed on Gmail's `attachment_id` (body.attachmentId, gmail.py:530),
--   which Gmail REGENERATES on every message fetch. Re-collecting a message ~900x produced
--   ~900 rows for the SAME file, each with a fresh attachment_id. So:
--     - rows = 3,379,707 but distinct real attachments = 703 (39 filenames, 1,247 messages).
--     - the first UNIQUE index idx_gmail_attachments_uniq (which INCLUDED attachment_id) was
--       useless against this (every re-fetch is "unique") AND cost ~1.78 GB.
--   The STABLE key is (message_id, filename, mime_type, size_bytes) -> 703 rows. Verified lossless:
--   distinct on stable key == 703 regardless of attachment_id.

.timeout 120000

-- 1) Drop the wrong index (keyed on the unstable attachment_id).
DROP INDEX IF EXISTS idx_gmail_attachments_uniq;

-- 2) Dedupe on the stable key, keeping the lowest id (its attachment_id is as good as any;
--    a future re-collect will refresh it via INSERT OR REPLACE once the new unique index exists).
BEGIN IMMEDIATE;
DELETE FROM gmail_attachments
 WHERE id NOT IN (
   SELECT MIN(id) FROM gmail_attachments
   GROUP BY message_id, filename, mime_type, size_bytes
 );
COMMIT;

-- 3) Correct UNIQUE index on the stable key. With this, the collector's INSERT OR REPLACE
--    will REPLACE the existing row (refreshing attachment_id) instead of appending.
CREATE UNIQUE INDEX IF NOT EXISTS idx_gmail_attachments_uniq
    ON gmail_attachments(message_id, filename, mime_type, size_bytes);

-- 4) Reclaim disk.
VACUUM;

-- 5) Verify.
SELECT 'attachments_rows', COUNT(*) FROM gmail_attachments;            -- expect 703
SELECT 'participants_rows', COUNT(*) FROM gmail_participants;          -- expect 6823 (unchanged)
SELECT 'labels_rows', COUNT(*) FROM gmail_labels;                      -- expect 4647 (unchanged)
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_gmail_%_uniq' ORDER BY name;
PRAGMA freelist_count;                                                  -- expect 0 after VACUUM
