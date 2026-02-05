"""
Time Truth Module (Tier 0)

The foundation layer of Time OS. All other tiers depend on this.

Objects:
- Task (with lane, scheduled_block_id, duration_min)
- TimeBlock (scheduled time slots)
- CalendarEvent (external calendar events)

Invariants:
- Every scheduled task maps to exactly one time block
- Calendar is execution truth
- Time blocks cannot overlap within a lane
- Protected blocks (meetings) are immutable by system
"""

from .block_manager import BlockManager
from .calendar_sync import CalendarSync
from .scheduler import Scheduler
from .rollover import Rollover
from .brief import generate_time_brief, get_time_truth_status

__all__ = ['BlockManager', 'CalendarSync', 'Scheduler', 'Rollover', 'generate_time_brief', 'get_time_truth_status']
