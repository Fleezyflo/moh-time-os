# CS-5.1: Calendar Collector Expansion

## Objective
Expand `lib/collectors/calendar.py` from ~35% to ≥85% API coverage. Pull attendee responses, video call links, recurrence rules, event types (focus time, OOO), multiple calendars, and organizer field.

## Context
Current Calendar collector (280 lines) pulls event title, start/end, description. Missing: who accepted/declined (meeting effectiveness signal), whether it's a video call (remote work signal), recurrence patterns (recurring commitment signal), focus time blocks, OOO status, and secondary calendars.

## Implementation

### New Data to Pull

1. **Attendee Details** — `event.attendees[]` with `responseStatus`, `email`, `displayName`, `organizer`, `self` → store in `calendar_attendees`
2. **Organizer** — `event.organizer.email/displayName` → `calendar_events.organizer_email`, `calendar_events.organizer_name`
3. **Conference/Video** — `event.conferenceData.entryPoints[].uri` → `calendar_events.conference_url`, derive `conference_type` (Meet, Zoom, Teams)
4. **Recurrence** — `event.recurrence[]` RRULE strings → `calendar_events.recurrence` + `calendar_recurrence_rules`
5. **Event Type** — `event.eventType` → `calendar_events.event_type` (default, focusTime, outOfOffice, workingLocation)
6. **Multiple Calendars** — List calendars via `GET /users/me/calendarList`, sync events from all non-declined calendars → `calendar_events.calendar_id`
7. **Attendee Counts** — Computed: `attendee_count`, `accepted_count`, `declined_count` stored on event row

### Calendar Discovery
```python
# Pull all calendars user has access to
calendars = service.calendarList().list().execute()
for cal in calendars.get("items", []):
    if cal.get("accessRole") in ("owner", "writer", "reader"):
        # Sync events from this calendar
        sync_calendar_events(cal["id"])
```

### Recurrence Handling
- Store raw RRULE on the event
- Expand recurring events using Google's `singleEvents=True` parameter
- Each instance gets its own row with `recurringEventId` linking to parent

## Validation
- [ ] Attendee responses match Google Calendar UI for sampled events
- [ ] Video call URLs captured for Meet/Zoom/Teams events
- [ ] Recurrence rules stored, recurring events expanded to instances
- [ ] Focus time and OOO events identified by event_type
- [ ] Secondary calendars discovered and synced
- [ ] Organizer field populated on all events
- [ ] Attendee counts computed correctly

## Files Modified
- `lib/collectors/calendar.py` — major expansion (~200 lines added)

## Estimated Effort
Medium-Large — multiple new API fields + calendar discovery logic
