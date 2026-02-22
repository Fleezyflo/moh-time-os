# CS-4.2: Google Chat Collector Expansion

## Objective
Expand Chat collection from ~40% to ≥85% API coverage. Pull reactions, attachments, full threading, space metadata, and membership.

## Context
Current Chat collection captures messages with basic fields. Missing: reactions (sentiment signal), attachments, thread structure (reply chains), space metadata (type, member count), and space membership (who is in which space). These are needed for collaboration pattern analysis.

## Implementation

### New Data to Pull

1. **Reactions** — `GET /spaces/{space}/messages/{msg}/reactions` → store in `chat_reactions`
2. **Attachments** — `message.attachment` array → store in `chat_attachments`
3. **Thread Structure** — `message.thread.name` + `message.threadReply` → `chat_messages.thread_id`, `chat_messages.thread_reply_count`
4. **Space Metadata** — `GET /spaces/{space}` → store in `chat_space_metadata` (type, displayName, threaded, spaceType)
5. **Space Members** — `GET /spaces/{space}/members` → store in `chat_space_members`

### Threading Model
Google Chat threads: a thread is identified by `thread.name`. Messages with the same `thread.name` are replies. Store `thread_id` on each message, compute `thread_reply_count` as count of messages sharing the same thread_id (excluding the root).

### Space Sync Strategy
- Sync space metadata once per cycle (changes rarely)
- Sync membership once per day (changes infrequently)
- Sync messages incrementally using `orderBy=createTime` + `filter=createTime > "{last_sync}"`

## Validation
- [ ] Reactions stored with emoji and user attribution
- [ ] Attachments metadata captured (no file downloads)
- [ ] Thread chains reconstructed — root message + replies linked
- [ ] All spaces listed with correct type classification
- [ ] Space membership matches actual members
- [ ] Incremental message sync works correctly

## Files Modified
- Chat collector file (identify exact file — may be in `lib/collectors/` or `lib/integrations/`)

## Estimated Effort
Medium — ~200 lines, mostly new endpoint calls + data mapping
