"""
Capacity Truth Module (Tier 2)

Tracks lane capacity, time debt, and workload distribution.

Dependencies:
- Tier 0 (Time Truth) must be stable
- Tier 1 (Commitment Truth) must be stable

Objects:
- Lane (capacity allocation unit)
- TimeDebt (accumulated unfulfilled time)

Invariants:
- sum(scheduled) <= capacity * (1 - buffer)
- Time debt accrues on rollover
- Alerts fire at 90%+ utilization
"""

from .calculator import CapacityCalculator
from .debt_tracker import DebtTracker

__all__ = ["CapacityCalculator", "DebtTracker"]
