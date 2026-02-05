"""
Finance Truth Module

Per MASTER_SPEC.md §10:
- AR Definition: status IN ('sent', 'overdue') AND paid_date IS NULL
- Valid AR: AR AND due_date IS NOT NULL AND client_id IS NOT NULL
- Aging buckets: current, 1-30, 31-60, 61-90, 90+
"""

from .ar_calculator import ARCalculator, FinanceTruth

__all__ = ['ARCalculator', 'FinanceTruth']
