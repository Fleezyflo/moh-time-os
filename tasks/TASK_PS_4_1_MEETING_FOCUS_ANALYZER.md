# PS-4.1: Meeting & Focus Time Analyzer

## Objective
Build a CalendarAnalyzer that processes calendar events to calculate meeting load, fragmentation, available focus blocks, and meeting clustering opportunities. Generate focus time recommendations.

## Implementation

### CalendarAnalyzer (`lib/predictive/calendar_analyzer.py`)
```python
class CalendarAnalyzer:
    """Analyze calendar events for meeting load and focus time opportunities."""

    def analyze(self, person_id: str, range_days: int = 7) -> CalendarAnalysis:
        """
        Process calendar events to produce:
          1. Meeting load: total meeting hours / working hours
          2. Fragmentation score: number of context switches per day
             (a switch = gap < 30min between meetings)
          3. Focus blocks: uninterrupted slots ≥ 2 hours during working hours
          4. Meeting clustering: groups of meetings that could be consolidated
        """

    def analyze_team(self, team_id: str, range_days: int = 7) -> List[CalendarAnalysis]:
        """Run analysis for all members of a team."""

    def suggest_focus_holds(self, person_id: str) -> List[FocusHoldSuggestion]:
        """Identify best available slots for calendar holds (deep work)."""

    def suggest_consolidation(self, person_id: str) -> List[ConsolidationSuggestion]:
        """Suggest moving meetings to reduce fragmentation."""
```

### Analysis Output
```python
@dataclass
class CalendarAnalysis:
    person_id: str
    period_start: str
    period_end: str
    total_meeting_hours: float
    total_working_hours: float
    meeting_load_pct: float            # meeting_hours / working_hours * 100
    is_overloaded: bool                # > 60% meeting time
    fragmentation_score: float         # 0-1, higher = more fragmented
    context_switches_per_day: float    # avg switches
    focus_blocks: List[FocusBlock]     # available deep work slots
    daily_breakdown: List[DailyCalendarStats]
    recommendations: List[str]

@dataclass
class FocusBlock:
    date: str
    start_time: str
    end_time: str
    duration_hours: float
    quality: str  # 'excellent' (≥4h) | 'good' (≥2h) | 'marginal' (≥1h)

@dataclass
class DailyCalendarStats:
    date: str
    meeting_hours: float
    focus_hours: float
    meetings_count: int
    context_switches: int
    longest_focus_block_hours: float
```

### Working Hours Config
```python
WORKING_HOURS = {
    'start': '09:00',
    'end': '18:00',
    'timezone': 'Asia/Dubai',
    'exclude_days': [4, 5],  # Friday, Saturday (UAE weekend)
    'meeting_overload_threshold_pct': 60,
    'min_focus_block_hours': 2.0,
}
```

### API Endpoints
```
GET  /api/v2/predictive/calendar/analysis/:person_id?range=7
GET  /api/v2/predictive/calendar/team/:team_id?range=7
GET  /api/v2/predictive/calendar/focus-suggestions/:person_id
GET  /api/v2/predictive/calendar/overloaded?threshold=60
```

## Validation
- [ ] Meeting load percentage calculated correctly from calendar events
- [ ] Fragmentation score increases with more scattered meetings
- [ ] Focus blocks only count slots ≥2 hours within working hours
- [ ] UAE weekend (Fri/Sat) excluded from working hours
- [ ] Team analysis returns per-person breakdowns
- [ ] Overloaded flag triggers at >60% meeting time
- [ ] Empty calendar returns 0% meeting load with full focus blocks

## Files Created
- `lib/predictive/calendar_analyzer.py`
- `tests/test_calendar_analyzer.py`

## Estimated Effort
Medium — ~500 lines
