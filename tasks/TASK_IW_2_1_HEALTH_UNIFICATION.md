# IW-2.1: Unify Health Scoring

## Objective
Consolidate three parallel health scoring systems into a single authoritative source. Currently scorecard.py (5 dimensions), agency_snapshot (custom weighted formula), and client_truth/health_calculator.py (separate calculation) exist in parallel with inconsistent results. Designate scorecard.py as the authoritative health source and adapt the other systems to consume its output.

## Implementation

### Current State Analysis
- **scorecard.py**: Computes 5-dimension health (delivery, comms, cash, relationships, technical) with weighted scores
- **agency_snapshot**: Computes health as delivery 35% + comms 25% + cash 25% + relationship 15%
- **client_truth/health_calculator.py**: Separate calculation with different logic

### Authoritative Source: scorecard.py
scorecard.py becomes the single source of truth. Its score_history table grows by one row per client per cycle containing final health scores.

```sql
CREATE TABLE IF NOT EXISTS score_history (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    delivery_score REAL,
    comms_score REAL,
    cash_score REAL,
    relationship_score REAL,
    technical_score REAL,
    composite_health REAL NOT NULL,
    cycle_id TEXT
);

CREATE INDEX idx_score_history_entity ON score_history(entity_type, entity_id, computed_at DESC);
CREATE INDEX idx_score_history_time ON score_history(computed_at DESC);
```

### HealthUnifier Adapter (`lib/intelligence/health_unifier.py`)
```python
from dataclasses import dataclass
from typing import Optional
from lib.query_engine import QueryEngine

@dataclass
class HealthScore:
    entity_type: str
    entity_id: str
    computed_at: str
    delivery_score: Optional[float]
    comms_score: Optional[float]
    cash_score: Optional[float]
    relationship_score: Optional[float]
    technical_score: Optional[float]
    composite_health: float

class HealthUnifier:
    """Adapter that provides unified health scores from scorecard.py."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def get_latest_health(self, entity_type: str, 
                         entity_id: str) -> Optional[HealthScore]:
        """Get the most recent health score for an entity."""
        # Query score_history table for latest row

    def get_health_at_time(self, entity_type: str, entity_id: str,
                          computed_at: str) -> Optional[HealthScore]:
        """Get health score at a specific time."""

    def get_health_trend(self, entity_type: str, entity_id: str,
                        days: int = 30) -> list[HealthScore]:
        """Get health scores over time, ordered chronologically."""

    def calculate_weighted_health(self, delivery: float, comms: float,
                                  cash: float, relationship: float,
                                  technical: float = None) -> float:
        """
        Unified formula: delivery 35% + comms 25% + cash 25% + relationship 15%
        Optional technical score can be used for additional analysis.
        """
        weights = {
            'delivery': 0.35,
            'comms': 0.25,
            'cash': 0.25,
            'relationship': 0.15
        }
        return (delivery * weights['delivery'] +
                comms * weights['comms'] +
                cash * weights['cash'] +
                relationship * weights['relationship'])
```

### Modified: agency_snapshot Integration
**File: `lib/agency_snapshot/aggregator.py` or relevant location**

```python
# Before: compute own health scores
# After: read from score_history via HealthUnifier

from lib.intelligence.health_unifier import HealthUnifier

class AgencySnapshot:
    def __init__(self, query_engine: QueryEngine, ...):
        self.health_unifier = HealthUnifier(query_engine)

    def compute_snapshot(self) -> dict:
        # Instead of computing health locally:
        # health_score = self.compute_health_internal(...)
        
        # Now consume unified scores:
        clients = self.get_all_clients()
        for client in clients:
            latest_health = self.health_unifier.get_latest_health(
                entity_type='client',
                entity_id=client.id
            )
            if latest_health:
                client_data['health'] = latest_health.composite_health
            
        return agency_snapshot_dict
```

### Modified: client_truth/health_calculator.py Integration
**File: `lib/client_truth/health_calculator.py`**

```python
from lib.intelligence.health_unifier import HealthUnifier

class HealthCalculator:
    def __init__(self, query_engine: QueryEngine, ...):
        self.health_unifier = HealthUnifier(query_engine)

    def calculate_health(self, client_id: str) -> float:
        """
        Delegate to scorecard via unifier.
        If scorecard hasn't run yet this cycle, fall back to last cycle.
        """
        latest_health = self.health_unifier.get_latest_health(
            entity_type='client',
            entity_id=client_id
        )
        if latest_health:
            return latest_health.composite_health
        # Fall back to previous cycle if current not available
        return None

    def get_health_trend(self, client_id: str, days: int = 30) -> list:
        """Retrieve health trend from unifier."""
        return self.health_unifier.get_health_trend(
            entity_type='client',
            entity_id=client_id,
            days=days
        )

    def persist_health(self, client_id: str, health_data: dict) -> None:
        """
        Call scorecard.score_client() and let it persist to score_history.
        This class reads only, scorecard writes.
        """
```

### Integration Points

**In `lib/scorecard.py`:**
```python
# scorecard already computes health; ensure it persists to score_history
class ScorecardEngine:
    def __init__(self, query_engine: QueryEngine, ...):
        self.query_engine = query_engine

    def score_client(self, client_id: str) -> HealthScore:
        # Existing scoring logic
        delivery = self.calculate_delivery_score(...)
        comms = self.calculate_comms_score(...)
        cash = self.calculate_cash_score(...)
        relationship = self.calculate_relationship_score(...)
        technical = self.calculate_technical_score(...)
        
        # Calculate composite health
        composite = self.unifier.calculate_weighted_health(
            delivery, comms, cash, relationship, technical
        )
        
        # Persist to score_history
        score_record = HealthScore(...)
        self.persist_to_score_history(score_record)
        
        return score_record
```

### Migration File
Add to `migrations/v31_intelligence_wiring.sql`:
```sql
CREATE TABLE IF NOT EXISTS score_history (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    delivery_score REAL,
    comms_score REAL,
    cash_score REAL,
    relationship_score REAL,
    technical_score REAL,
    composite_health REAL NOT NULL,
    cycle_id TEXT
);

CREATE INDEX idx_score_history_entity ON score_history(entity_type, entity_id, computed_at DESC);
CREATE INDEX idx_score_history_time ON score_history(computed_at DESC);
```

## Validation
- [ ] score_history table created and indexed
- [ ] scorecard.py persists health scores to score_history after each calculation
- [ ] HealthUnifier class implements all read methods
- [ ] HealthUnifier.calculate_weighted_health() uses correct formula (delivery 35%, comms 25%, cash 25%, relationship 15%)
- [ ] agency_snapshot reads from HealthUnifier instead of computing its own scores
- [ ] client_truth/health_calculator.py reads from HealthUnifier instead of computing its own scores
- [ ] Composite health scores in score_history match scorecard calculations within 1 point
- [ ] Health trend queries return chronologically ordered results
- [ ] Fall-back logic works if scorecard hasn't run yet in current cycle
- [ ] No queries use f-strings; all parameterized

## Files Created
- `lib/intelligence/health_unifier.py`

## Files Modified
- `lib/scorecard.py` — persist results to score_history
- `lib/agency_snapshot/aggregator.py` (or relevant) — consume HealthUnifier
- `lib/client_truth/health_calculator.py` — consume HealthUnifier

## Estimated Effort
Medium — ~200 lines
