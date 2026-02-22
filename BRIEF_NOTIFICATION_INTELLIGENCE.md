# Brief 21: Notification Intelligence & Digest Engine

## Status: DESIGNED
## Priority: P2 — Operational efficiency, reduces noise
## Dependencies: Brief 15 (Bidirectional Integrations), Brief 19 (UI Completion — SSE)

## Problem Statement

The notification system is binary: every event fires a Google Chat webhook immediately. There's no user preference, no batching, no priority routing, no digest. A busy day can generate 50+ Chat messages — overwhelming the operator and burying critical alerts in noise. The system knows event severity but doesn't use it to decide *when* or *how* to notify. There's no notification history, no read/unread tracking, and no way to mute noisy sources.

## Success Criteria

- Per-user notification preferences: channel (Chat/email/in-app), frequency (immediate/hourly/daily), severity threshold
- Digest engine batches low/medium items into scheduled summaries (daily 9am, weekly Monday)
- Smart routing: critical → immediate all channels, high → immediate primary channel, medium → next digest, low → weekly digest only
- Quiet hours: no notifications outside configured working hours (default 8am-8pm GST) except critical
- Notification history with read/unread tracking, searchable
- Mute rules: silence specific clients, signal types, or pattern categories for N days
- Email digest channel with rich HTML formatting
- Notification analytics: volume per day, response time, most-actioned types

## Scope

### Phase 1: Notification Preferences & Routing (NI-1.1)
Build a preferences model (per-user channel config, severity thresholds, quiet hours, timezone). Create a NotificationRouter that evaluates each event against preferences and decides: deliver immediately, queue for next digest, or suppress. Store preferences in DB with sensible defaults.

### Phase 2: Digest Engine (NI-2.1)
Build a DigestEngine that accumulates queued notifications and generates batched summaries on schedule (hourly/daily/weekly). Group by category (proposals, issues, watchers, patterns). Include counts, top items by severity, and direct links. Generate both plaintext (for Chat) and HTML (for email) formats.

### Phase 3: Email Digest Channel (NI-3.1)
Build an EmailDigestChannel using Gmail API (Brief 15's GmailWriter). Rich HTML template with sections per category, severity color coding, action links, and unsubscribe footer. Schedule via the daemon's cron infrastructure.

### Phase 4: Notification History & Muting (NI-4.1)
Build notification_history table tracking every notification sent: channel, timestamp, event_type, severity, read_at, actioned_at. Add mute rules table. API endpoints: list history, mark read, create/delete mute rules. Wire into the UI notification center (Brief 19's SSE work).

### Phase 5: Notification Analytics & Validation (NI-5.1)
Build analytics queries: notification volume trends, response time distribution, most-actioned types, mute rule effectiveness. Validation: end-to-end test of routing logic, digest generation, email delivery, mute suppression.

## Architecture

```
Event Source (proposals, issues, watchers, patterns)
    ↓
NotificationRouter
    ├─ evaluate(event, user_preferences)
    ├─ IMMEDIATE → GoogleChatChannel / EmailChannel / SSE push
    ├─ DIGEST → DigestQueue (hourly/daily/weekly bucket)
    └─ SUPPRESS → log only (muted or below threshold)

DigestEngine (cron-scheduled)
    ├─ collect(bucket, since_last_digest)
    ├─ group_by_category()
    ├─ render(format: 'chat' | 'email_html')
    └─ deliver(channels)

notification_history table
    ├─ id, user_id, event_type, severity, channel
    ├─ created_at, delivered_at, read_at, actioned_at
    └─ muted_by (FK to mute_rules if suppressed)
```

## Task Files
- `tasks/TASK_NI_1_1_NOTIFICATION_ROUTING.md`
- `tasks/TASK_NI_2_1_DIGEST_ENGINE.md`
- `tasks/TASK_NI_3_1_EMAIL_DIGEST.md`
- `tasks/TASK_NI_4_1_HISTORY_MUTING.md`
- `tasks/TASK_NI_5_1_ANALYTICS_VALIDATION.md`

## Estimated Effort
Large — routing logic (~400 lines), digest engine (~500 lines), email templates (~300 lines), history/muting (~400 lines), analytics (~200 lines).
