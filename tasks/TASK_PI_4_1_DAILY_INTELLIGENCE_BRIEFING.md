# PI-4.1: Daily Intelligence Briefing

## Objective
Build the morning view. When you open the system, you see: what changed since you last looked, what's predicted to need attention this week, and the highest-priority prepared actions ready for review. This is the 5-minute morning scan. The briefing adapts based on your behavior (Brief 22) — things you always dismiss stop appearing.

## Implementation

### DailyBriefingEngine (`lib/intelligence/daily_briefing.py`)
```python
class DailyBriefingEngine:
    """Generate the daily intelligence briefing."""

    def generate_briefing(self) -> DailyBriefing:
        """
        Assemble the full morning briefing:
        1. Changes since last session
        2. This week's predicted concerns
        3. Top prepared actions
        4. Stale entities needing attention
        5. Key metrics snapshot
        """

    def get_changes_since_last_session(self) -> ChangesSummary:
        """
        What happened since you last looked:
        - New signals raised (filtered through lifecycle — Brief 22)
        - Signals resolved
        - Payments received
        - Invoices newly overdue
        - Health score changes (significant only: ±10+ points)
        - Asana task completions and new overdue items
        - New communications received (count by channel)
        """

    def get_week_ahead(self) -> WeekAheadSummary:
        """
        What's predicted for this week:
        - Deadlines approaching (from Asana + predictions)
        - Meetings requiring briefs (from calendar)
        - Cash flow projections (from Brief 23)
        - Capacity concerns (from Brief 23)
        - Clients predicted to need attention (from trajectories)
        """

    def get_priority_actions(self, limit: int = 5) -> List[PreparedAction]:
        """
        Top N prepared actions by priority.
        Filters out action types you consistently dismiss (from behavioral analysis).
        """

    def get_stale_entities(self) -> List[StaleEntitySummary]:
        """
        Entities not reviewed in 14+ days with active signals.
        From entity memory (Brief 22).
        """

    def get_metrics_snapshot(self) -> MetricsSnapshot:
        """
        Key numbers at a glance:
        - Total AR outstanding
        - Active clients / projects
        - Average health score
        - Utilization rate
        - Cash in / cash out this month
        """

    def record_briefing_viewed(self) -> None:
        """Mark that you've seen today's briefing. Updates session timestamp."""
```

### Data Schemas
```python
@dataclass
class DailyBriefing:
    generated_at: str
    last_session_at: str | None
    changes: ChangesSummary
    week_ahead: WeekAheadSummary
    priority_actions: List[PreparedAction]
    stale_entities: List[StaleEntitySummary]
    metrics: MetricsSnapshot

@dataclass
class ChangesSummary:
    new_signals: List[dict]          # signal summaries
    resolved_signals: List[dict]
    payments_received: List[dict]    # amount, client, invoice
    new_overdue_invoices: List[dict]
    health_changes: List[dict]       # entity, old_score, new_score, direction
    asana_completions: int
    asana_new_overdue: int
    communications_received: Dict[str, int]  # channel → count
    total_change_count: int

@dataclass
class WeekAheadSummary:
    deadlines: List[dict]            # task/milestone, date, risk_level
    meetings_needing_briefs: List[dict]  # event, date, attendees, entity_link
    cashflow_projection: dict        # expected_in, expected_out, net
    capacity_alerts: List[dict]      # date_range, utilization, concern
    clients_needing_attention: List[dict]  # client, reason, predicted_concern

@dataclass
class StaleEntitySummary:
    entity_type: str
    entity_id: str
    entity_name: str
    days_since_review: int
    active_signal_count: int
    last_action: str | None
    suggested_action: str | None     # from behavioral analysis

@dataclass
class MetricsSnapshot:
    ar_outstanding: float
    active_clients: int
    active_projects: int
    avg_health_score: float
    utilization_pct: float
    cash_in_this_month: float
    cash_out_this_month: float
    net_cash_this_month: float
```

### Briefing Table
```sql
CREATE TABLE briefing_sessions (
    id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    viewed_at TEXT,
    briefing_data TEXT NOT NULL,      -- JSON: full briefing snapshot
    actions_taken INTEGER DEFAULT 0,  -- how many prepared actions you acted on
    time_spent_seconds INTEGER        -- how long you spent on the briefing
);

CREATE INDEX idx_briefing_sessions_date ON briefing_sessions(generated_at DESC);
```

### UI Component Structure
```typescript
// DailyBriefing.tsx — morning intelligence view
// Sections:
//   1. ChangesBanner — compact summary: "12 changes since yesterday"
//      Expandable: categorized list of changes
//   2. WeekAhead — timeline view of upcoming deadlines, meetings, concerns
//   3. ActionCards — top 5 prepared actions, each with:
//      - Action type icon (email/task/event/message)
//      - Entity name and context summary
//      - One-tap: Approve | Edit | Dismiss
//   4. StaleEntities — entities needing your attention, with suggested action
//   5. MetricsBar — key numbers in a compact row at the bottom

// Design principle: scannable in 5 minutes.
// Priority actions are the main focus.
// Everything else is expandable detail.
```

### API Endpoints
```
GET  /api/v2/briefing/today                    (generate or return cached briefing)
GET  /api/v2/briefing/changes?since=...        (changes since timestamp)
GET  /api/v2/briefing/week-ahead
GET  /api/v2/briefing/metrics-snapshot
POST /api/v2/briefing/viewed                   (record that you've seen it)
GET  /api/v2/briefing/history?limit=7          (past briefings)
```

## Validation
- [ ] Briefing generates correctly with all sections populated
- [ ] Changes correctly detected since last session timestamp
- [ ] Week ahead pulls from calendar, predictions, and Asana deadlines
- [ ] Priority actions filtered through behavioral patterns (dismissed types deprioritized)
- [ ] Stale entities correctly identified from entity memory
- [ ] Metrics snapshot matches actual data from existing aggregation engines
- [ ] Briefing viewed timestamp updates correctly
- [ ] Empty states handled gracefully (new system with no history)
- [ ] Briefing generation completes in under 3 seconds
- [ ] Historical briefings accessible for reference

## Files Created
- `lib/intelligence/daily_briefing.py`
- `time-os-ui/src/pages/briefing/DailyBriefing.tsx`
- `time-os-ui/src/pages/briefing/components/ActionCard.tsx`
- `api/briefing_router.py`
- `tests/test_daily_briefing.py`

## Estimated Effort
Large — ~900 lines (briefing engine + UI components + API + change detection)
