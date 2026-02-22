# PI-5.1: Contextual Surfaces & Pre-Meeting Briefs

## Objective
Wire prepared actions into entity pages so they surface WHERE they're relevant. When viewing Client X, see pending drafts and suggested actions for that client. Before a meeting, get a pre-meeting brief with client status, open items, and talking points. Build the dispatch mechanism. Validate end-to-end: trigger → prepare → present → approve → dispatch.

## Implementation

### Contextual Surface Manager (`lib/intelligence/contextual_surfaces.py`)
```python
class ContextualSurfaceManager:
    """Surface prepared actions and intelligence where they're relevant."""

    def get_entity_surface(self, entity_type: str, entity_id: str) -> EntitySurface:
        """
        Everything relevant to show on an entity page:
        - Pending prepared actions for this entity
        - Recent decision history (Brief 22)
        - Active signals (filtered through lifecycle)
        - Entity memory summary
        - Quick-draft options (buttons: "Draft email", "Create task", "Schedule meeting")
        """

    def get_pre_meeting_brief(self, calendar_event_id: str) -> PreMeetingBrief:
        """
        Compile a meeting brief:
        1. Identify attendees → match to MOH entities (clients/contacts)
        2. For each matched entity:
           - Current health score + trend
           - Outstanding invoices
           - Active project status
           - Recent communications (last 3 touchpoints)
           - Open signals and predictions
           - Decision history (last 3 decisions you made about this entity)
        3. Suggested talking points based on open items
        4. Any prepared actions related to these entities
        """

    def get_post_meeting_actions(self, calendar_event_id: str) -> List[PreparedAction]:
        """
        After a meeting ends, prepare:
        - Follow-up email draft (referencing meeting)
        - Task creation if action items were discussed
        - Calendar event for next meeting if recurring
        """

    def get_upcoming_meetings_needing_briefs(self, hours_ahead: int = 24) -> List[dict]:
        """Meetings in the next N hours that have entity matches and warrant a brief."""
```

### Pre-Meeting Brief Schema
```python
@dataclass
class PreMeetingBrief:
    meeting_id: str
    meeting_title: str
    meeting_time: str
    duration_minutes: int
    attendees: List[AttendeeContext]
    talking_points: List[str]
    prepared_actions: List[PreparedAction]
    overall_context: str              # 1-paragraph executive summary

@dataclass
class AttendeeContext:
    name: str
    email: str
    entity_type: str | None           # matched MOH entity
    entity_id: str | None
    health_score: float | None
    health_trend: str | None          # 'improving' | 'stable' | 'declining'
    outstanding_ar: float | None
    active_projects: List[str]
    last_contact_date: str | None
    last_contact_channel: str | None
    open_signals: List[str]           # signal summaries
    recent_decisions: List[str]       # decision summaries
```

### Entity Surface Schema
```python
@dataclass
class EntitySurface:
    entity_type: str
    entity_id: str
    entity_name: str
    prepared_actions: List[PreparedAction]  # pending for this entity
    recent_decisions: List[dict]            # last 5 from decision journal
    active_signals: List[dict]              # filtered through lifecycle
    memory_summary: str                     # from entity memory
    attention_level: str                    # high/normal/low/stale
    quick_actions: List[QuickAction]        # available draft buttons

@dataclass
class QuickAction:
    action_type: str       # 'email_draft' | 'asana_task' | 'calendar_event' | 'chat_message'
    label: str             # 'Draft follow-up email'
    default_intent: str    # pre-selected intent based on entity state
    available: bool        # False if no contact email, no project link, etc.
```

### Dispatch Mechanism
```python
class DispatchManager:
    """Route approved actions to the correct Brief 15 writer."""

    def dispatch(self, action: PreparedAction) -> DispatchResult:
        """
        Route based on action_type:
          'email_draft' → GmailWriter.send()
          'asana_task' → AsanaWriter.create_task()
          'asana_update' → AsanaWriter.update_task()
          'calendar_event' → CalendarWriter.create_event()
          'chat_message' → ChatWriter.send_message()

        On success: update action status to 'dispatched', record external_id.
        On failure: keep status as 'approved', record error, surface retry option.
        Always: record in decision journal.
        """

    def get_dispatch_history(self, entity_type: str = None,
                              entity_id: str = None,
                              days: int = 30) -> List[DispatchRecord]:
        """Historical dispatch results for review."""
```

### UI Integration
```typescript
// EntitySurfacePanel.tsx — sidebar or section on entity pages
// Shows:
//   PreparedActionsSection — pending actions for this entity
//     Each card: type icon, context summary, Approve/Edit/Dismiss
//   RecentDecisions — last 5 decisions (collapsed by default)
//   QuickActions — buttons: "Draft email" | "Create task" | "Schedule meeting"
//     Each opens a minimal form with pre-filled context

// PreMeetingBrief.tsx — expandable brief before meetings
// Shows:
//   Meeting header: time, attendees, duration
//   Per-attendee cards: health, projects, invoices, last contact
//   Talking points: bulleted suggestions
//   Prepared actions: related staged items

// Dispatch flow:
//   Tap "Approve" → spinner → success/failure toast
//   Tap "Edit" → inline editor → "Send" button
//   Tap "Dismiss" → confirmation → removed from view
```

### API Endpoints
```
GET  /api/v2/surfaces/entity/:type/:id         (entity surface data)
GET  /api/v2/surfaces/meeting/:event_id/brief   (pre-meeting brief)
GET  /api/v2/surfaces/meetings/upcoming?hours=24 (meetings needing briefs)
POST /api/v2/dispatch/:action_id                 (dispatch an approved action)
GET  /api/v2/dispatch/history?entity_type=...&days=30
```

### End-to-End Validation Suite
```python
class PreparedIntelligenceValidation:
    """Validate the entire Brief 24 pipeline end-to-end."""

    def test_signal_to_preparation(self):
        """Signal raised → preparation rule matches → action staged."""

    def test_prediction_to_preparation(self):
        """Prediction generated → preparation rule matches → action staged."""

    def test_schedule_to_meeting_brief(self):
        """Calendar event approaching → pre-meeting brief generated."""

    def test_on_demand_preparation(self):
        """User requests draft → correct action staged with full context."""

    def test_approve_to_dispatch(self):
        """Staged action approved → dispatched via correct writer → result recorded."""

    def test_modify_then_approve(self):
        """Staged action modified → modifications preserved → dispatched on approve."""

    def test_dismiss_feeds_journal(self):
        """Action dismissed → recorded in decision journal → feeds behavioral patterns."""

    def test_entity_surface_complete(self):
        """Entity page shows actions + decisions + signals + memory."""

    def test_briefing_includes_predictions(self):
        """Daily briefing pulls from Brief 23 predictions."""

    def test_behavioral_filtering(self):
        """Consistently dismissed action types deprioritized in briefing."""

    def test_dispatch_failure_recovery(self):
        """Failed dispatch → error recorded → retry option available."""

    def test_expiry_cleanup(self):
        """Expired staged actions don't appear in surfaces or briefing."""
```

## Validation
- [ ] Entity surfaces show correct prepared actions per entity
- [ ] Pre-meeting briefs compile attendee context from all data sources
- [ ] Post-meeting actions prepared automatically
- [ ] Quick actions available with correct pre-filled context
- [ ] Dispatch routes to correct Brief 15 writer
- [ ] Dispatch success records external ID and updates status
- [ ] Dispatch failure preserves action for retry
- [ ] End-to-end: signal → prepare → present on entity page → approve → dispatch → record
- [ ] End-to-end: calendar event → meeting brief → talking points → post-meeting follow-up
- [ ] Behavioral filtering reduces noise in repeated interactions
- [ ] Stale prepared actions expire and don't clutter surfaces

## Files Created
- `lib/intelligence/contextual_surfaces.py`
- `lib/intelligence/dispatch_manager.py`
- `time-os-ui/src/components/EntitySurfacePanel.tsx`
- `time-os-ui/src/components/PreMeetingBrief.tsx`
- `api/surfaces_router.py`
- `tests/test_contextual_surfaces.py`
- `tests/test_dispatch_manager.py`
- `tests/test_prepared_intelligence_e2e.py`

## Estimated Effort
Very Large — ~1,100 lines (surfaces + dispatch + meeting briefs + validation suite + UI components)
