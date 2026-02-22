# IW-1.1: Create Missing Tables & Fix Persistence

## Objective
Create the core persistence layer for the intelligence system. Wire signal state management, pattern detection, and cost-to-serve snapshots to persist data to the database. This is the foundation that intelligence wiring builds on.

## Implementation

### New Tables
```sql
CREATE TABLE signal_state (
    signal_key TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    first_detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    escalated_at TEXT,
    cleared_at TEXT,
    detection_count INTEGER DEFAULT 1,
    cooldown_until TEXT,
    state TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE pattern_snapshots (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    pattern_id TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    entities_involved TEXT NOT NULL,
    evidence TEXT NOT NULL,
    cycle_id TEXT
);

CREATE TABLE cost_snapshots (
    id TEXT PRIMARY KEY,
    computed_at TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    entity_id TEXT,
    data TEXT NOT NULL
);

CREATE INDEX idx_signal_state_entity ON signal_state(entity_type, entity_id);
CREATE INDEX idx_signal_state_active ON signal_state(state, severity);
CREATE INDEX idx_pattern_snapshots_time ON pattern_snapshots(detected_at DESC);
CREATE INDEX idx_pattern_snapshots_pattern ON pattern_snapshots(pattern_id);
CREATE INDEX idx_cost_snapshots_time ON cost_snapshots(computed_at DESC);
CREATE INDEX idx_cost_snapshots_entity ON cost_snapshots(entity_id, computed_at DESC);
```

### Persistence Classes (`lib/intelligence/persistence.py`)
```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from lib.query_engine import QueryEngine

@dataclass
class SignalStateRecord:
    signal_key: str
    entity_type: str
    entity_id: str
    signal_type: str
    severity: str
    first_detected_at: str
    last_detected_at: str
    escalated_at: Optional[str]
    cleared_at: Optional[str]
    detection_count: int
    cooldown_until: Optional[str]
    state: str

class SignalStatePersistence:
    """Persist and retrieve signal state from database."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def upsert(self, signal: SignalStateRecord) -> None:
        """Insert or update a signal state record."""
        # Use INSERT OR REPLACE or appropriate upsert pattern

    def get_active_signals(self, entity_type: str = None, 
                          entity_id: str = None) -> List[SignalStateRecord]:
        """Retrieve active signals, optionally filtered by entity."""

    def get_signal(self, signal_key: str) -> Optional[SignalStateRecord]:
        """Retrieve a single signal by key."""

    def mark_escalated(self, signal_key: str, escalated_at: str) -> None:
        """Mark a signal as escalated."""

    def mark_cleared(self, signal_key: str, cleared_at: str) -> None:
        """Mark a signal as cleared."""

    def increment_detection_count(self, signal_key: str) -> None:
        """Increment the detection count for a signal."""

    def set_cooldown(self, signal_key: str, cooldown_until: str) -> None:
        """Set cooldown period for a signal."""

@dataclass
class PatternSnapshot:
    id: str
    detected_at: str
    pattern_id: str
    pattern_name: str
    severity: str
    entities_involved: str  # JSON array
    evidence: str  # JSON object
    cycle_id: Optional[str]

class PatternPersistence:
    """Persist and retrieve pattern detection snapshots."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def record_pattern(self, pattern: PatternSnapshot) -> None:
        """Record a detected pattern snapshot."""

    def get_patterns_by_entity(self, entity_type: str, 
                               entity_id: str) -> List[PatternSnapshot]:
        """Retrieve all patterns involving an entity."""

    def get_patterns_in_cycle(self, cycle_id: str) -> List[PatternSnapshot]:
        """Retrieve all patterns detected in a cycle."""

    def get_recent_patterns(self, days: int = 7) -> List[PatternSnapshot]:
        """Retrieve patterns from the last N days."""

@dataclass
class CostSnapshot:
    id: str
    computed_at: str
    snapshot_type: str  # 'daily_summary', 'entity_breakdown', 'service_breakdown'
    entity_id: Optional[str]
    data: str  # JSON object with cost data

class CostPersistence:
    """Persist and retrieve cost-to-serve snapshots."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def record_snapshot(self, snapshot: CostSnapshot) -> None:
        """Record a cost snapshot."""

    def get_latest_daily_summary(self) -> Optional[CostSnapshot]:
        """Get the most recent daily cost summary."""

    def get_entity_cost_history(self, entity_id: str, 
                                days: int = 30) -> List[CostSnapshot]:
        """Get cost history for an entity."""

    def get_daily_summaries(self, days: int = 30) -> List[CostSnapshot]:
        """Get daily cost summaries for a time period."""
```

### Integration Points

**In `lib/intelligence/signals.py`:**
```python
# Wire SignalGenerator to persist state on detection
class SignalGenerator:
    def __init__(self, persistence: SignalStatePersistence, ...):
        self.persistence = persistence

    def detect(self, signal_type: str, entity_type: str, 
               entity_id: str, severity: str) -> None:
        # Detect logic
        state_record = SignalStateRecord(...)
        self.persistence.upsert(state_record)
```

**In `lib/engine.py` (pattern detection):**
```python
# Wire pattern detection to persist snapshots
class IntelligenceEngine:
    def __init__(self, pattern_persistence: PatternPersistence, ...):
        self.pattern_persistence = pattern_persistence

    def detect_patterns(self, cycle_id: str) -> List[Pattern]:
        patterns = [...]
        for pattern in patterns:
            snapshot = PatternSnapshot(...)
            self.pattern_persistence.record_pattern(snapshot)
        return patterns
```

**In `lib/cost_to_serve/calculator.py`:**
```python
# Wire daily cost computation to persist snapshots
class CostCalculator:
    def __init__(self, cost_persistence: CostPersistence, ...):
        self.cost_persistence = cost_persistence

    def compute_daily_snapshot(self) -> None:
        daily_cost = self.calculate_costs()
        snapshot = CostSnapshot(...)
        self.cost_persistence.record_snapshot(snapshot)
```

### Migration File
Create `migrations/v31_intelligence_wiring.sql` with the full schema above.

## Validation
- [ ] signal_state table created and indexed
- [ ] pattern_snapshots table created and indexed
- [ ] cost_snapshots table created and indexed
- [ ] SignalStatePersistence class implements all methods
- [ ] PatternPersistence class implements all methods
- [ ] CostPersistence class implements all methods
- [ ] signals.py integrates SignalStatePersistence and persists on detection
- [ ] engine.py integrates PatternPersistence and persists detected patterns
- [ ] cost_to_serve.py integrates CostPersistence and persists daily snapshots
- [ ] All persistence classes return typed results, no empty dicts/lists on failure
- [ ] Database queries are parameterized (no f-strings)

## Files Created
- `lib/intelligence/persistence.py`
- `migrations/v31_intelligence_wiring.sql`
- `tests/test_intelligence_persistence.py`

## Estimated Effort
Medium — ~300 lines
