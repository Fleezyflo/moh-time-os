# NI-5.1: Notification Analytics & Validation

## Objective
Build analytics queries for notification volume, response times, and mute effectiveness. Validate the full notification pipeline end-to-end.

## Implementation

### Analytics Queries
```python
class NotificationAnalytics:
    def volume_by_day(self, user_id, days=30) -> List[DailyVolume]:
        """Notifications per day, broken down by channel and severity."""

    def response_time_distribution(self, user_id, days=30) -> ResponseTimeStats:
        """Time from delivered_at to read_at and actioned_at."""

    def most_actioned_types(self, user_id, days=30) -> List[TypeCount]:
        """Which event types get the most actions (most valuable notifications)."""

    def mute_effectiveness(self, user_id) -> MuteReport:
        """How many notifications suppressed by mute rules, volume reduction %."""

    def digest_engagement(self, user_id, days=30) -> DigestStats:
        """Digest open rate, items clicked from digest vs dismissed."""
```

### API Endpoints
```
GET /api/v2/notifications/analytics/volume?days=30
GET /api/v2/notifications/analytics/response-times
GET /api/v2/notifications/analytics/top-types
GET /api/v2/notifications/analytics/mute-report
```

### End-to-End Validation
Test the full pipeline:
1. Generate mock events at different severity levels
2. Verify routing decisions match preferences
3. Verify immediate delivery to Chat channel
4. Verify queue for digest
5. Trigger digest generation and verify delivery
6. Verify history logged for all deliveries
7. Create mute rule and verify suppression
8. Verify analytics queries return correct data

## Validation
- [ ] Volume analytics returns correct daily counts
- [ ] Response time calculation correct (delivered → read → actioned)
- [ ] Mute effectiveness shows correct suppression count
- [ ] End-to-end: event → route → deliver → log → analytics all connected
- [ ] All Brief 21 tests pass
- [ ] No regressions on existing test suite

## Files Created
- `lib/notifications/analytics.py`
- `tests/test_notification_analytics.py`
- `scripts/validate_notifications.py`

## Files Modified
- `api/notification_router.py` — add analytics endpoints

## Estimated Effort
Small — ~200 lines
