# ID-5.1: Pattern Trending
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 5 | Sequence: 5.1 | Status: PENDING

## Objective

Classify pattern direction (new, persistent, resolving, worsening) by analyzing pattern_snapshots table from Brief 17 to understand whether patterns are emerging, stable, fading, or deteriorating.

## Implementation

### Pattern Direction Classification

Using `pattern_snapshots` table (from Brief 17), compute pattern_direction for each active pattern:

- **New**: Detected in current cycle (cycle_index = 0) but NOT in any of the last 5 cycles
- **Persistent**: Detected in current cycle AND in 3 or more of the last 5 cycles
- **Resolving**: Detected in 3 or more of the last 5 cycles but NOT in current cycle
- **Worsening**: Detected in current cycle, AND (entity_count or evidence_strength increased vs average of last 5 cycles)

### New File: `lib/intelligence/pattern_trending.py`

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal

@dataclass
class PatternSnapshot:
    """Single cycle snapshot of a pattern."""
    pattern_key: str
    pattern_type: str
    cycle_index: int
    entity_count: int
    evidence_strength: float  # 0.0 to 1.0
    is_present: bool


@dataclass
class PatternTrendAnalysis:
    """Analysis of pattern trend across cycles."""
    pattern_key: str
    pattern_type: str
    current_direction: Literal['new', 'persistent', 'resolving', 'worsening']
    cycle_presence_history: List[bool]  # Most recent first, [current, -1, -2, -3, -4, -5]
    current_entity_count: int
    avg_entity_count_last_5: float
    current_evidence_strength: float
    avg_evidence_strength_last_5: float
    cycles_present_in_last_5: int


class PatternTrendAnalyzer:
    """Analyzes pattern direction from cycle-by-cycle snapshots."""

    def __init__(self, db, lookback_cycles: int = 5):
        """
        Initialize analyzer.
        
        Args:
            db: Database connection
            lookback_cycles: Number of past cycles to consider (default 5)
        """
        self.db = db
        self.lookback_cycles = lookback_cycles

    def analyze_pattern_trend(
        self,
        pattern_key: str,
        snapshots: List[PatternSnapshot]
    ) -> PatternTrendAnalysis:
        """
        Classify pattern direction based on cycle history.
        
        Args:
            pattern_key: Unique pattern identifier
            snapshots: List of snapshots across cycles (ordered: [current, -1, -2, ...])
        
        Returns:
            PatternTrendAnalysis with direction and supporting metrics
        """

    def get_entity_pattern_trends(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, PatternTrendAnalysis]:
        """
        Get pattern trends for all active patterns of an entity.
        
        Returns dict mapping pattern_key -> PatternTrendAnalysis
        """

    def get_patterns_by_direction(
        self,
        direction: Literal['new', 'persistent', 'resolving', 'worsening'],
        entity_type: Optional[str] = None
    ) -> List[PatternTrendAnalysis]:
        """
        Get all patterns matching a direction filter.
        
        Useful for portfolio-wide alerts:
        - Direction='worsening' → emerging problems
        - Direction='new' → early warning patterns
        - Direction='resolving' → positive indicators
        """

    def _classify_direction(
        self,
        presence_history: List[bool],
        current_entity_count: int,
        avg_entity_count_last_5: float,
        current_evidence_strength: float,
        avg_evidence_strength_last_5: float
    ) -> str:
        """
        Classify direction based on presence history and metrics.
        
        Logic:
        - If presence_history[0] == False: check for 'resolving'
        - If presence_history[0] == True:
          - If sum(presence_history[1:]) < 1: 'new'
          - If sum(presence_history[1:]) >= 3: 
            - If (entity_count > avg + std_dev) or (strength > avg + std_dev): 'worsening'
            - Else: 'persistent'
        """

    def _count_cycles_present(self, presence_history: List[bool]) -> int:
        """Count True values in presence history."""

    def _is_worsening(
        self,
        current_entity_count: int,
        avg_entity_count: float,
        current_strength: float,
        avg_strength: float,
        std_dev_threshold: float = 1.0
    ) -> bool:
        """
        Determine if pattern is worsening based on metrics.
        
        Returns True if current metrics exceed historical average by
        more than one standard deviation estimate.
        """

    def refresh_all_pattern_trends(self) -> Dict[str, Dict[str, PatternTrendAnalysis]]:
        """
        Refresh pattern direction for all entities and patterns.
        
        Returns nested dict: entity_type -> entity_id -> pattern_key -> analysis
        
        Performance target: < 5 seconds for full portfolio refresh
        """
```

### Database Queries

Assuming `pattern_snapshots` table (from Brief 17):
```sql
SELECT 
    pattern_key,
    pattern_type,
    cycle_index,
    entity_count,
    evidence_strength,
    is_present
FROM pattern_snapshots
WHERE pattern_key = ? AND entity_type = ? AND entity_id = ?
ORDER BY cycle_index ASC
LIMIT 6;
```

## Validation

- [ ] "New" patterns correctly identified (current cycle only, not in last 5)
- [ ] "Persistent" patterns correctly identified (current + 3+ of last 5)
- [ ] "Resolving" patterns correctly identified (not in current, but in 3+ of last 5)
- [ ] "Worsening" patterns correctly identified (current cycle AND metrics increased)
- [ ] Cycle presence history computed in correct order (most recent first)
- [ ] Entity count and evidence strength averages computed across 5 cycles
- [ ] Direction classification logic covers all cases without overlap
- [ ] get_patterns_by_direction() returns correct filtered set
- [ ] Performance: analyze_pattern_trend() < 10ms per pattern
- [ ] refresh_all_pattern_trends() completes in < 5 seconds for 1000 entities

## Files Created
- New: `lib/intelligence/pattern_trending.py`

## Files Modified
- None (this is a new module)

## Estimated Effort
~150 lines — trend classification logic, cycle history aggregation, performance-optimized queries
