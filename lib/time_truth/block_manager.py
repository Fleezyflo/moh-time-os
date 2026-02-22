"""
Block Manager - Core time block operations for Time Truth.

Manages the creation, assignment, and validation of time blocks.
Enforces invariants:
- No overlapping blocks within a lane
- Every scheduled task has exactly one block
- Blocks respect work hours and lane capacity
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from lib.state_store import get_store

logger = logging.getLogger(__name__)


@dataclass
class TimeBlock:
    id: str
    date: str
    start_time: str
    end_time: str
    lane: str
    task_id: str | None = None
    is_protected: bool = False
    is_buffer: bool = False
    created_at: str = None
    updated_at: str = None

    @property
    def duration_min(self) -> int:
        """Calculate block duration in minutes."""
        start = datetime.strptime(self.start_time, "%H:%M")
        end = datetime.strptime(self.end_time, "%H:%M")
        return int((end - start).total_seconds() / 60)

    @property
    def is_available(self) -> bool:
        """Block is available if not protected and has no task."""
        return not self.is_protected and self.task_id is None


@dataclass
class Conflict:
    block_a_id: str
    block_b_id: str
    overlap_start: str
    overlap_end: str
    lane: str


class BlockManager:
    """
    Manages time blocks - the atomic unit of scheduled time.

    Responsibilities:
    - Create blocks from calendar gaps
    - Assign tasks to blocks
    - Detect and prevent conflicts
    - Query available blocks
    """

    # Default work hours
    WORK_START = "09:00"
    WORK_END = "21:00"

    # Default block size (minutes)
    DEFAULT_BLOCK_SIZE = 60

    # Default lanes
    LANES = ["ops", "creative", "client_comms", "admin", "deep_work"]

    def __init__(self, store=None, db_path=None):
        if isinstance(store, str):
            # Handle case where store is actually a db_path (from TruthCycle)
            db_path = store
            store = None
        self.store = store or get_store(db_path)

    def get_available_blocks(self, date: str, lane: str = None) -> list[TimeBlock]:
        """
        Get unassigned, non-protected blocks for a date.

        Args:
            date: Date string YYYY-MM-DD
            lane: Optional lane filter

        Returns:
            List of available TimeBlock objects
        """
        query = """
            SELECT * FROM time_blocks
            WHERE date = ?
            AND is_protected = 0
            AND task_id IS NULL
        """
        params = [date]

        if lane:
            query += " AND lane = ?"
            params.append(lane)

        query += " ORDER BY start_time"

        rows = self.store.query(query, params)
        return [self._row_to_block(row) for row in rows]

    def get_all_blocks(self, date: str, lane: str = None) -> list[TimeBlock]:
        """Get all blocks for a date, optionally filtered by lane."""
        query = "SELECT * FROM time_blocks WHERE date = ?"
        params = [date]

        if lane:
            query += " AND lane = ?"
            params.append(lane)

        query += " ORDER BY start_time"

        rows = self.store.query(query, params)
        return [self._row_to_block(row) for row in rows]

    def schedule_task(self, task_id: str, block_id: str) -> tuple[bool, str]:
        """
        Assign a task to a time block.

        Enforces invariants:
        - Block must be available
        - Task must not already be scheduled
        - Lane must match

        Returns:
            (success, message)
        """
        # Get block
        block_row = self.store.query("SELECT * FROM time_blocks WHERE id = ?", [block_id])
        if not block_row:
            return False, "Block not found"

        block = self._row_to_block(block_row[0])

        # Check block is available
        if block.is_protected:
            return False, "Block is protected"
        if block.task_id:
            return False, f"Block already assigned to task {block.task_id}"

        # Get task
        task = self.store.get("tasks", task_id)
        if not task:
            return False, "Task not found"

        # Check task not already scheduled
        if task.get("scheduled_block_id"):
            return (
                False,
                f"Task already scheduled in block {task['scheduled_block_id']}",
            )

        # Check lane match
        task_lane = task.get("lane", "ops")
        if task_lane != block.lane:
            return False, f"Lane mismatch: task is {task_lane}, block is {block.lane}"

        # All checks passed - assign
        now = datetime.now().isoformat()

        self.store.query(
            "UPDATE time_blocks SET task_id = ?, updated_at = ? WHERE id = ?",
            [task_id, now, block_id],
        )

        self.store.update("tasks", task_id, {"scheduled_block_id": block_id, "updated_at": now})

        return True, f"Task scheduled in block {block_id}"

    def unschedule_task(self, task_id: str) -> tuple[bool, str]:
        """Remove task from its scheduled block."""
        task = self.store.get("tasks", task_id)
        if not task:
            return False, "Task not found"

        block_id = task.get("scheduled_block_id")
        if not block_id:
            return False, "Task not scheduled"

        now = datetime.now().isoformat()

        # Clear block
        self.store.query(
            "UPDATE time_blocks SET task_id = NULL, updated_at = ? WHERE id = ?",
            [now, block_id],
        )

        # Clear task
        self.store.update("tasks", task_id, {"scheduled_block_id": None, "updated_at": now})

        return True, f"Task unscheduled from block {block_id}"

    def create_block(
        self,
        date: str,
        start_time: str,
        end_time: str,
        lane: str,
        is_protected: bool = False,
        is_buffer: bool = False,
    ) -> tuple[TimeBlock | None, str]:
        """
        Create a new time block.

        Validates:
        - No overlap with existing blocks in same lane
        - Within work hours (unless protected)
        - Valid time format

        Returns:
            (TimeBlock or None, message)
        """
        # Validate times
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
        except ValueError:
            return None, "Invalid time format (use HH:MM)"

        if end <= start:
            return None, "End time must be after start time"

        # Check for conflicts
        conflicts = self._check_overlap(date, start_time, end_time, lane)
        if conflicts:
            return None, f"Overlaps with existing block: {conflicts[0].id}"

        # Check work hours (skip for protected blocks like meetings)
        if not is_protected:
            work_start = datetime.strptime(self.WORK_START, "%H:%M")
            work_end = datetime.strptime(self.WORK_END, "%H:%M")
            if start < work_start or end > work_end:
                return None, f"Outside work hours ({self.WORK_START}-{self.WORK_END})"

        # Create block
        now = datetime.now().isoformat()
        block_id = f"block_{uuid.uuid4().hex[:12]}"

        self.store.insert(
            "time_blocks",
            {
                "id": block_id,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "lane": lane,
                "is_protected": 1 if is_protected else 0,
                "is_buffer": 1 if is_buffer else 0,
                "created_at": now,
                "updated_at": now,
            },
        )

        block = TimeBlock(
            id=block_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            lane=lane,
            is_protected=is_protected,
            is_buffer=is_buffer,
            created_at=now,
            updated_at=now,
        )

        return block, "Block created"

    def create_blocks_from_calendar(
        self, date: str, events: list[dict], lane: str = "ops"
    ) -> list[TimeBlock]:
        """
        Generate available time blocks around calendar events.

        Takes calendar events and creates blocks in the gaps.
        Events become protected blocks.

        Args:
            date: Date string YYYY-MM-DD
            events: List of calendar events with start_time, end_time
            lane: Lane for the available blocks

        Returns:
            List of created blocks (both protected and available)
        """
        created_blocks = []

        # Sort events by start time
        sorted_events = sorted(events, key=lambda e: e.get("start_time", ""))

        # Create protected blocks for events
        for event in sorted_events:
            start = event.get("start_time", "")
            end = event.get("end_time", "")

            if not start or not end:
                continue

            # Extract time portion if full datetime
            if "T" in start:
                start = start.split("T")[1][:5]
            if "T" in end:
                end = end.split("T")[1][:5]

            block, msg = self.create_block(
                date=date, start_time=start, end_time=end, lane=lane, is_protected=True
            )
            if block:
                created_blocks.append(block)

        # Now create available blocks in gaps
        work_start = datetime.strptime(self.WORK_START, "%H:%M")
        work_end = datetime.strptime(self.WORK_END, "%H:%M")

        # Get all blocks for this date/lane to find gaps
        existing = self.get_all_blocks(date, lane)

        # Find gaps
        current = work_start
        for block in sorted(existing, key=lambda b: b.start_time):
            block_start = datetime.strptime(block.start_time, "%H:%M")
            block_end = datetime.strptime(block.end_time, "%H:%M")

            # Gap before this block
            if current < block_start:
                (block_start - current).total_seconds() / 60

                # Create blocks in the gap
                while current < block_start:
                    block_size = min(
                        self.DEFAULT_BLOCK_SIZE,
                        (block_start - current).total_seconds() / 60,
                    )
                    if block_size < 30:  # Skip tiny gaps
                        break

                    end_time = current + timedelta(minutes=block_size)
                    new_block, msg = self.create_block(
                        date=date,
                        start_time=current.strftime("%H:%M"),
                        end_time=end_time.strftime("%H:%M"),
                        lane=lane,
                        is_protected=False,
                    )
                    if new_block:
                        created_blocks.append(new_block)

                    current = end_time

            # Move past this block
            current = max(current, block_end)

        # Gap after last block until work end
        while current < work_end:
            block_size = min(self.DEFAULT_BLOCK_SIZE, (work_end - current).total_seconds() / 60)
            if block_size < 30:
                break

            end_time = current + timedelta(minutes=block_size)
            new_block, msg = self.create_block(
                date=date,
                start_time=current.strftime("%H:%M"),
                end_time=end_time.strftime("%H:%M"),
                lane=lane,
                is_protected=False,
            )
            if new_block:
                created_blocks.append(new_block)

            current = end_time

        return created_blocks

    def get_conflicts(self, date: str, lane: str = None) -> list[Conflict]:
        """
        Detect overlapping blocks (should never happen if invariants hold).

        Returns list of conflicts found.
        """
        blocks = self.get_all_blocks(date, lane)
        conflicts = []

        for i, a in enumerate(blocks):
            for b in blocks[i + 1 :]:
                if a.lane != b.lane:
                    continue

                # Check overlap
                a_start = datetime.strptime(a.start_time, "%H:%M")
                a_end = datetime.strptime(a.end_time, "%H:%M")
                b_start = datetime.strptime(b.start_time, "%H:%M")
                b_end = datetime.strptime(b.end_time, "%H:%M")

                # Overlap exists if one starts before the other ends
                if a_start < b_end and b_start < a_end:
                    overlap_start = max(a_start, b_start).strftime("%H:%M")
                    overlap_end = min(a_end, b_end).strftime("%H:%M")

                    conflicts.append(
                        Conflict(
                            block_a_id=a.id,
                            block_b_id=b.id,
                            overlap_start=overlap_start,
                            overlap_end=overlap_end,
                            lane=a.lane,
                        )
                    )

        return conflicts

    def _check_overlap(
        self, date: str, start_time: str, end_time: str, lane: str
    ) -> list[TimeBlock]:
        """Check if a potential block would overlap with existing blocks."""
        existing = self.get_all_blocks(date, lane)

        new_start = datetime.strptime(start_time, "%H:%M")
        new_end = datetime.strptime(end_time, "%H:%M")

        overlapping = []
        for block in existing:
            block_start = datetime.strptime(block.start_time, "%H:%M")
            block_end = datetime.strptime(block.end_time, "%H:%M")

            if new_start < block_end and block_start < new_end:
                overlapping.append(block)

        return overlapping

    def _row_to_block(self, row: dict) -> TimeBlock:
        """Convert database row to TimeBlock object."""
        return TimeBlock(
            id=row["id"],
            date=row["date"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            lane=row["lane"],
            task_id=row.get("task_id"),
            is_protected=bool(row.get("is_protected", 0)),
            is_buffer=bool(row.get("is_buffer", 0)),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


# Quick test
if __name__ == "__main__":
    bm = BlockManager()
    today = date.today().isoformat()

    logger.info(f"Testing BlockManager for {today}")
    logger.info("-" * 40)
    # Create a test block
    block, msg = bm.create_block(today, "10:00", "11:00", "ops")
    logger.info(f"Create block: {msg}")
    if block:
        logger.info(f"  Block ID: {block.id}")
    # Get available blocks
    available = bm.get_available_blocks(today, "ops")
    logger.info(f"Available blocks in ops: {len(available)}")
    # Check for conflicts
    conflicts = bm.get_conflicts(today)
    logger.info(f"Conflicts: {len(conflicts)}")
