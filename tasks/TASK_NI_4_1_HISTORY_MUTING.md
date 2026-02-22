# NI-4.1: Notification History & Muting

## Objective
Track every notification sent (channel, timestamp, read status). Build mute rules to silence specific clients, signal types, or categories for configurable periods.

## Implementation

### New Tables
```sql
CREATE TABLE notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    channel TEXT NOT NULL,           -- 'chat' | 'email' | 'in_app' | 'digest'
    delivered_at TEXT NOT NULL,
    read_at TEXT,
    actioned_at TEXT,
    action_taken TEXT                -- 'dismissed' | 'snoozed' | 'resolved' | etc.
);

CREATE TABLE mute_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    rule_type TEXT NOT NULL,         -- 'client' | 'event_type' | 'category' | 'source'
    rule_value TEXT NOT NULL,        -- client_id, or 'proposal', or 'capacity_warning'
    muted_until TEXT NOT NULL,       -- ISO 8601 datetime
    reason TEXT,
    created_at TEXT NOT NULL
);
```

### API Endpoints
```
GET    /api/v2/notifications/history?page=1&limit=50&unread=true
PATCH  /api/v2/notifications/history/:id/read
GET    /api/v2/notifications/mutes
POST   /api/v2/notifications/mutes     → {rule_type, rule_value, days, reason}
DELETE /api/v2/notifications/mutes/:id
```

### Integration with Router
NotificationRouter checks mute_rules before routing:
```python
def _is_muted(self, event, user_id) -> bool:
    rules = self.get_active_mute_rules(user_id)
    for rule in rules:
        if rule.matches(event):
            return True
    return False
```

### Notification Center (UI integration point)
Wire history into the UI notification bell (Brief 19's SSE work):
- Bell icon with unread count badge
- Dropdown: list of recent notifications, grouped by today/yesterday/earlier
- Click to mark read and navigate to item
- "Mute this type" option per notification

## Validation
- [ ] Every delivered notification logged in history
- [ ] Read/unread tracking works via API
- [ ] Mute rules suppress matching notifications
- [ ] Expired mute rules auto-ignored (past muted_until)
- [ ] History paginated (no full-table scans)
- [ ] Mute rule CRUD endpoints work
- [ ] Integration: muted events don't appear in Chat or email

## Files Created
- `lib/notifications/history.py`
- `lib/notifications/muting.py`
- `tests/test_notification_history.py`
- `tests/test_mute_rules.py`

## Files Modified
- `lib/notifications/router.py` — integrate mute check
- `api/notification_router.py` — add history and mute endpoints

## Estimated Effort
Medium — ~400 lines
