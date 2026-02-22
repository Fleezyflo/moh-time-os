# SM-1.1: Decision Journal

## Objective
Build a persistent decision log that captures every meaningful interaction you have with the system — signal dismissed, draft approved, recommendation modified, action scrapped. This is the memory foundation that all other Brief 22 features build on.

## Implementation

### New Tables
```sql
CREATE TABLE decision_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    -- 'signal_dismissed' | 'signal_escalated' | 'signal_acknowledged'
    -- 'draft_approved' | 'draft_modified' | 'draft_scrapped'
    -- 'recommendation_followed' | 'recommendation_ignored'
    -- 'entity_reviewed' | 'manual_note'
    entity_type TEXT,               -- 'client' | 'project' | 'engagement' | 'invoice'
    entity_id TEXT,
    presented_context TEXT,          -- JSON: what the system showed you
    action_taken TEXT NOT NULL,      -- what you decided
    user_notes TEXT,                 -- optional annotation you add
    outcome TEXT,                    -- filled retrospectively: what happened after
    outcome_recorded_at TEXT,
    source_type TEXT,                -- 'signal' | 'prepared_action' | 'recommendation' | 'manual'
    source_id TEXT                   -- FK to signal/prepared_action/etc.
);

CREATE INDEX idx_decision_log_entity ON decision_log(entity_type, entity_id, timestamp DESC);
CREATE INDEX idx_decision_log_type ON decision_log(decision_type, timestamp DESC);
CREATE INDEX idx_decision_log_time ON decision_log(timestamp DESC);
```

### DecisionJournal (`lib/memory/decision_journal.py`)
```python
class DecisionJournal:
    """Persistent log of every decision made through the system."""

    def record(self, decision_type: str, entity_type: str, entity_id: str,
               presented_context: dict, action_taken: str,
               user_notes: str = None, source_type: str = None,
               source_id: str = None) -> DecisionEntry:
        """Record a decision. Called automatically on any system interaction."""

    def get_entity_history(self, entity_type: str, entity_id: str,
                           limit: int = 20) -> List[DecisionEntry]:
        """All decisions related to an entity, most recent first."""

    def get_recent(self, limit: int = 50) -> List[DecisionEntry]:
        """Recent decisions across all entities."""

    def record_outcome(self, decision_id: str, outcome: str) -> None:
        """Retrospectively record what happened after a decision."""

    def get_by_type(self, decision_type: str, days: int = 30) -> List[DecisionEntry]:
        """All decisions of a type within a time window."""

    def annotate(self, decision_id: str, notes: str) -> None:
        """Add or update notes on a past decision."""
```

### Integration Points
Every system interaction that represents a decision should call `decision_journal.record()`:
```python
# Signal dismissed from UI
decision_journal.record(
    decision_type='signal_dismissed',
    entity_type='client', entity_id='cli_123',
    presented_context={'signal': 'health_declining', 'severity': 'high', 'health_score': 58},
    action_taken='dismissed',
    source_type='signal', source_id='sig_456'
)

# Email draft approved and sent
decision_journal.record(
    decision_type='draft_approved',
    entity_type='client', entity_id='cli_123',
    presented_context={'draft_type': 'follow_up_email', 'subject': 'Checking in...'},
    action_taken='approved_as_is',
    source_type='prepared_action', source_id='pa_789'
)
```

### API Endpoints
```
GET  /api/v2/memory/decisions?entity_type=client&entity_id=...&limit=20
GET  /api/v2/memory/decisions/recent?limit=50
POST /api/v2/memory/decisions              (manual entries / notes)
PATCH /api/v2/memory/decisions/:id/outcome
PATCH /api/v2/memory/decisions/:id/notes
```

## Validation
- [ ] Decisions recorded on signal dismiss/escalate/acknowledge
- [ ] Decisions recorded on draft approve/modify/scrap
- [ ] Entity history returns correct chronological entries
- [ ] Outcome recording links back to original decision
- [ ] Manual notes can be added and updated
- [ ] All decision types represented in the enum
- [ ] Journal doesn't duplicate entries for same interaction

## Files Created
- `lib/memory/decision_journal.py`
- `api/memory_router.py`
- `tests/test_decision_journal.py`

## Estimated Effort
Medium — ~500 lines
