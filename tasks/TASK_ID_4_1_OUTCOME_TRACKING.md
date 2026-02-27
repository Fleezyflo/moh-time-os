# ID-4.1: Outcome Tracking
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 4 | Sequence: 4.1 | Status: PENDING

## Objective

Record what happens when signals clear so we can measure the effectiveness of intelligence and understand whether action or time resolved detected issues. When a signal transitions from active → cleared in signal_state, capture the context and outcome for retrospective analysis.

## Implementation

### New Table: `signal_outcomes`

```sql
CREATE TABLE signal_outcomes (
    id TEXT PRIMARY KEY,
    signal_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    cleared_at TEXT NOT NULL,
    duration_days REAL NOT NULL,
    health_before REAL,
    health_after REAL,
    health_improved INTEGER,
    actions_taken TEXT,
    resolution_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_signal_outcomes_entity ON signal_outcomes(entity_type, entity_id);
CREATE INDEX idx_signal_outcomes_type ON signal_outcomes(signal_type, resolution_type);
CREATE INDEX idx_signal_outcomes_time ON signal_outcomes(cleared_at DESC);
```

### Field Definitions

- `id`: Unique outcome record ID (ulid or uuid)
- `signal_key`: Original signal key from signal_state
- `entity_type`: 'client' | 'project' | 'engagement' | 'invoice'
- `entity_id`: ID of the entity
- `signal_type`: Original signal type (e.g., 'health_declining', 'cost_overrun')
- `detected_at`: When signal first transitioned to active
- `cleared_at`: When signal transitioned from active to cleared
- `duration_days`: How long signal was active
- `health_before`: Entity health score when signal detected
- `health_after`: Entity health score when signal cleared
- `health_improved`: 1 if health_after > health_before, 0 otherwise
- `actions_taken`: JSON or delimited list of action IDs taken while signal active (nullable)
- `resolution_type`: 'natural' | 'addressed' | 'expired' | 'unknown'
  - **natural**: Signal cleared due to underlying condition improving (health went up)
  - **addressed**: Action was taken while signal was active and signal then cleared
  - **expired**: Signal clearing rules evaluated to false (threshold no longer met) without action
  - **unknown**: Signal cleared but no health change and no recorded actions
- `created_at`: When this outcome record was created

### New File: `lib/intelligence/outcome_tracker.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal

@dataclass
class SignalOutcome:
    """Record of what happened when a signal cleared."""
    id: str
    signal_key: str
    entity_type: str
    entity_id: str
    signal_type: str
    detected_at: datetime
    cleared_at: datetime
    duration_days: float
    health_before: Optional[float]
    health_after: Optional[float]
    health_improved: bool
    actions_taken: Optional[List[str]]
    resolution_type: Literal['natural', 'addressed', 'expired', 'unknown']
    created_at: datetime


class OutcomeTracker:
    """Records and analyzes signal outcomes for intelligence effectiveness."""

    def __init__(self, db):
        """Initialize with database connection."""
        self.db = db

    def record_outcome(
        self,
        signal_key: str,
        entity_type: str,
        entity_id: str,
        signal_type: str,
        detected_at: datetime,
        cleared_at: datetime,
        health_before: Optional[float],
        health_after: Optional[float],
        actions_taken: Optional[List[str]] = None
    ) -> SignalOutcome:
        """
        Record a signal outcome when it clears.
        
        Automatically determines resolution_type based on:
        - If health_after > health_before: 'natural' (condition improved)
        - If actions_taken not empty: 'addressed' (action was taken)
        - If threshold rules evaluate false: 'expired' (no longer meets criteria)
        - Otherwise: 'unknown'
        
        Called by signal_state transition logic when signal moves to cleared.
        """

    def get_outcomes_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 90,
        limit: int = 100
    ) -> List[SignalOutcome]:
        """Retrieve outcomes for an entity in past N days."""

    def get_outcomes_by_type(
        self,
        signal_type: str,
        days: int = 90,
        limit: int = 100
    ) -> List[SignalOutcome]:
        """Retrieve outcomes for a signal type across all entities."""

    def get_outcomes_by_resolution(
        self,
        resolution_type: str,
        days: int = 90,
        limit: int = 100
    ) -> List[SignalOutcome]:
        """Get outcomes filtered by how they were resolved."""

    def get_effectiveness_metrics(
        self,
        days: int = 90
    ) -> dict:
        """
        Aggregate metrics on signal resolution.
        
        Returns:
        {
            'total_outcomes': int,
            'avg_duration_days': float,
            'resolution_type_breakdown': {
                'natural': count,
                'addressed': count,
                'expired': count,
                'unknown': count
            },
            'improvement_rate': float,  # fraction where health_improved
            'action_success_rate': float,  # among 'addressed', fraction with health_improved
            'by_signal_type': {
                'health_declining': {...},
                'cost_overrun': {...},
                ...
            }
        }
        """

    def _determine_resolution_type(
        self,
        health_before: Optional[float],
        health_after: Optional[float],
        actions_taken: Optional[List[str]]
    ) -> str:
        """Classify how signal was resolved."""
```

### Migration File: `migrations/v32_intelligence_depth.sql`

```sql
-- Create signal_outcomes table for tracking signal lifecycle
CREATE TABLE signal_outcomes (
    id TEXT PRIMARY KEY,
    signal_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    cleared_at TEXT NOT NULL,
    duration_days REAL NOT NULL,
    health_before REAL,
    health_after REAL,
    health_improved INTEGER,
    actions_taken TEXT,
    resolution_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_signal_outcomes_entity ON signal_outcomes(entity_type, entity_id);
CREATE INDEX idx_signal_outcomes_type ON signal_outcomes(signal_type, resolution_type);
CREATE INDEX idx_signal_outcomes_time ON signal_outcomes(cleared_at DESC);
```

### Integration

In signal_state transition logic (whenever a signal moves to cleared state):
```python
# When signal cleared:
self.outcome_tracker.record_outcome(
    signal_key=signal['key'],
    entity_type=signal['entity_type'],
    entity_id=signal['entity_id'],
    signal_type=signal['type'],
    detected_at=signal['detected_at'],
    cleared_at=datetime.now(),
    health_before=signal.get('health_before_score'),
    health_after=current_entity_health_score,
    actions_taken=get_actions_linked_to_signal(signal['id'])
)
```

## Validation

- [ ] Outcome table schema matches specification exactly
- [ ] Outcome records created when signal clears (transition to cleared state)
- [ ] duration_days calculated correctly (cleared_at - detected_at)
- [ ] resolution_type logic: natural for health improvement, addressed for action-taken
- [ ] get_outcomes_for_entity() returns correct signal history for an entity
- [ ] effectiveness_metrics correctly aggregates outcome data
- [ ] health_improved flag matches (health_after > health_before)
- [ ] Actions taken correctly linked and stored
- [ ] Indexes exist and query performance acceptable (< 100ms for entity outcome query)
- [ ] Migration applies cleanly to existing databases

## Files Created
- New: `lib/intelligence/outcome_tracker.py`
- New: `migrations/v32_intelligence_depth.sql`

## Files Modified
- Modified: Signal state transition logic (where signals move to cleared) to call outcome_tracker.record_outcome()

## Estimated Effort
~150 lines — outcome recording logic, resolution_type classification, aggregation queries
