# CS-4.1: Gmail Collector Expansion

## Objective
Expand `lib/collectors/gmail.py` from ~30% to ≥85% API coverage. Pull thread participants, Cc/Bcc, attachments metadata, labels, read/starred/importance flags.

## Context
Current Gmail collector (333 lines) pulls message subjects, bodies, from/to, and dates. Missing: full participant list (Cc/Bcc), attachment metadata, label assignments, read status, starred status, importance headers. These signals are critical for communication pattern analysis and client engagement scoring.

## Implementation

### New Data to Pull

1. **Full Participants** — Parse `Cc`, `Bcc` headers alongside existing `From`/`To` → store in `gmail_participants` with role field
2. **Attachment Metadata** — `message.payload.parts` where `filename` is non-empty → store in `gmail_attachments` (metadata only, no file content)
3. **Labels** — `message.labelIds` → store in `gmail_labels`, map system labels (INBOX, SENT, IMPORTANT, STARRED, UNREAD)
4. **Read Status** — Derived from `UNREAD` label presence → `communications.is_read`
5. **Starred Status** — Derived from `STARRED` label presence → `communications.is_starred`
6. **Importance** — `Importance` header or `IMPORTANT` label → `communications.importance`
7. **Attachment Count** — Count of parts with filenames → `communications.has_attachments`, `communications.attachment_count`

### Thread-Level Enrichment
- Pull full thread with `GET /threads/{id}` for threads with >1 message
- Map all unique participants across thread → `gmail_participants`
- Track thread depth (reply count)

### Incremental Sync
- Use `historyId` from Gmail API for efficient delta sync
- Only process messages newer than last `historyId`
- Store `last_history_id` in collector state

## Validation
- [ ] Cc/Bcc participants captured when present
- [ ] Attachment metadata stored without downloading content
- [ ] Label assignments match Gmail UI for sampled messages
- [ ] is_read, is_starred, importance populated correctly
- [ ] Thread participants include all Cc/Bcc across entire thread
- [ ] Incremental sync via historyId reduces API calls on subsequent runs

## Files Modified
- `lib/collectors/gmail.py` — expand collect method + add participant/attachment parsing

## Estimated Effort
Medium — ~150 lines added, mostly parsing existing API response fields that are currently ignored
