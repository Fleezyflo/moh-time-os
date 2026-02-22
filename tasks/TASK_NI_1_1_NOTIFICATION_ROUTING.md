# NI-1.1: Notification Preferences & Routing

## Objective
Build a per-user notification preference model and a NotificationRouter that evaluates events against preferences to decide: deliver immediately, queue for digest, or suppress.

## Context
Currently every event fires a Google Chat webhook immediately via `GoogleChatChannel`. There's no per-user config, no severity-based routing, no quiet hours. This task builds the intelligent routing layer between event sources and delivery channels.

## Implementation

### New Tables
```sql
-- User notification preferences
CREATE TABLE notification_preferences (
    user_id TEXT PRIMARY KEY,
    primary_channel TEXT DEFAULT 'chat',        -- 'chat' | 'email' | 'in_app'
    secondary_channel TEXT DEFAULT 'in_app',
    severity_threshold TEXT DEFAULT 'medium',   -- minimum severity for immediate delivery
    digest_frequency TEXT DEFAULT 'daily',      -- 'hourly' | 'daily' | 'weekly'
    quiet_hours_start TEXT DEFAULT '20:00',     -- HH:MM in user timezone
    quiet_hours_end TEXT DEFAULT '08:00',
    timezone TEXT DEFAULT 'Asia/Dubai',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TEXT,
    updated_at TEXT
);

-- Queued items for digest delivery
CREATE TABLE notification_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,                   -- 'proposal' | 'issue' | 'watcher' | 'pattern'
    event_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    digest_bucket TEXT NOT NULL,                -- 'hourly' | 'daily' | 'weekly'
    queued_at TEXT NOT NULL,
    delivered_at TEXT,                          -- NULL until digest sent
    FOREIGN KEY (user_id) REFERENCES notification_preferences(user_id)
);
```

### NotificationRouter (`lib/notifications/router.py`)
```python
class NotificationRouter:
    def route(self, event: NotificationEvent, user_id: str) -> RoutingDecision:
        """Evaluate event against user preferences."""
        prefs = self.get_preferences(user_id)

        if not prefs.enabled:
            return RoutingDecision.SUPPRESS

        if self._is_muted(event, user_id):
            return RoutingDecision.SUPPRESS

        if event.severity >= prefs.severity_threshold:
            if self._in_quiet_hours(prefs):
                if event.severity == 'critical':
                    return RoutingDecision.IMMEDIATE  # critical breaks quiet hours
                return RoutingDecision.QUEUE_DIGEST
            return RoutingDecision.IMMEDIATE

        return RoutingDecision.QUEUE_DIGEST

    def deliver_immediate(self, event, user_id, channel):
        """Send via specified channel and log to history."""

    def queue_for_digest(self, event, user_id, bucket):
        """Insert into notification_queue for later batch delivery."""
```

### API Endpoints
```
GET    /api/v2/notifications/preferences          → get current user's prefs
PUT    /api/v2/notifications/preferences          → update preferences
POST   /api/v2/notifications/test                 → send test notification
```

## Validation
- [ ] Preferences table created with sensible defaults
- [ ] Critical events always deliver immediately (even during quiet hours)
- [ ] Medium events during quiet hours get queued
- [ ] Low events always get queued regardless of time
- [ ] Disabled preferences suppress all notifications
- [ ] API endpoints work for CRUD operations
- [ ] Existing GoogleChatChannel still works as delivery backend
- [ ] Tests: routing logic for each severity × time × preference combination

## Files Created
- `lib/notifications/router.py`
- `lib/notifications/models.py`
- `lib/notifications/preferences.py`
- `api/notification_router.py` (API endpoints)
- `tests/test_notification_routing.py`

## Files Modified
- Schema migration for new tables

## Estimated Effort
Medium — ~400 lines
