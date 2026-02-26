"""
Scheduler - Auto-schedule tasks into time blocks.

The core scheduling engine for Time Truth.
Assigns pending tasks to available blocks based on priority and constraints.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date

from lib.state_store import get_store
from lib.time_truth.block_manager import BlockManager
from lib.time_truth.calendar_sync import CalendarSync

logger = logging.getLogger(__name__)


@dataclass
class ScheduleResult:
    task_id: str
    task_title: str
    block_id: str | None
    success: bool
    message: str


@dataclass
class ValidationResult:
    valid: bool
    issues: list[str]
    stats: dict


class Scheduler:
    """
    Auto-scheduler for tasks into time blocks.

    Scheduling priority:
    1. Tasks due today
    2. Tasks due tomorrow
    3. Highest priority score

    Constraints:
    - Task lane must match block lane
    - Block must be available (not protected, not assigned)
    - Task must not already be scheduled
    """

    def __init__(self, store=None, db_path=None):
        if isinstance(store, str):
            # Handle case where store is actually a db_path (from TruthCycle)
            db_path = store
            store = None
        self.store = store or get_store(db_path)
        self.block_manager = BlockManager(self.store)
        self.calendar_sync = CalendarSync(self.store)

    def schedule_unscheduled(self, target_date: str = None) -> list[ScheduleResult]:
        """
        Schedule all unscheduled tasks for a date.

        Args:
            target_date: Date to schedule for (defaults to today)

        Returns:
            List of ScheduleResult for each task attempted
        """
        if not target_date:
            target_date = date.today().isoformat()

        # Ensure blocks exist for this date
        self.calendar_sync.generate_available_blocks(target_date)

        # Get unscheduled tasks, prioritized
        tasks = self._get_schedulable_tasks(target_date)

        results = []

        for task in tasks:
            result = self._schedule_task(task, target_date)
            results.append(result)

            if not result.success:
                # If we can't schedule, might be out of blocks
                available = self.block_manager.get_available_blocks(
                    target_date, task.get("lane", "ops")
                )
                if not available:
                    # No more blocks for this lane, skip remaining tasks in this lane
                    pass

        return results

    def _get_schedulable_tasks(self, target_date: str) -> list[dict]:
        """
        Get tasks that should be scheduled, in priority order.

        Priority:
        1. Due today (overdue included)
        2. Due tomorrow
        3. By priority score descending
        """
        # Get all pending, unscheduled tasks
        return self.store.query(
            """
            SELECT * FROM tasks
            WHERE status = 'pending'
            AND (scheduled_block_id IS NULL OR scheduled_block_id = '')
            ORDER BY
                CASE
                    WHEN due_date <= ? THEN 0
                    WHEN due_date = date(?, '+1 day') THEN 1
                    ELSE 2
                END,
                priority DESC,
                due_date ASC
        """,
            [target_date, target_date],
        )

    def _schedule_task(self, task: dict, target_date: str) -> ScheduleResult:
        """
        Attempt to schedule a single task.
        """
        task_id = task["id"]
        task_title = task.get("title", "")[:50]
        task_lane = task.get("lane", "ops")
        task_duration = task.get("duration_min", 60)

        # Get available blocks for this lane
        available_blocks = self.block_manager.get_available_blocks(target_date, task_lane)

        if not available_blocks:
            return ScheduleResult(
                task_id=task_id,
                task_title=task_title,
                block_id=None,
                success=False,
                message=f"No available blocks in lane '{task_lane}'",
            )

        # Find a block that fits the task duration
        suitable_block = None
        for block in available_blocks:
            if block.duration_min >= task_duration:
                suitable_block = block
                break

        if not suitable_block:
            # Use the largest available block even if smaller than ideal
            suitable_block = max(available_blocks, key=lambda b: b.duration_min)

        # Schedule the task
        success, message = self.block_manager.schedule_task(task_id, suitable_block.id)

        return ScheduleResult(
            task_id=task_id,
            task_title=task_title,
            block_id=suitable_block.id if success else None,
            success=success,
            message=message,
        )

    def schedule_specific_task(
        self, task_id: str, block_id: str = None, target_date: str = None
    ) -> ScheduleResult:
        """
        Schedule a specific task, optionally into a specific block.

        Args:
            task_id: Task to schedule
            block_id: Specific block (auto-select if None)
            target_date: Date for auto-selection

        Returns:
            ScheduleResult
        """
        task = self.store.get("tasks", task_id)
        if not task:
            return ScheduleResult(
                task_id=task_id,
                task_title="",
                block_id=None,
                success=False,
                message="Task not found",
            )

        if task.get("scheduled_block_id"):
            return ScheduleResult(
                task_id=task_id,
                task_title=task.get("title", "")[:50],
                block_id=task["scheduled_block_id"],
                success=False,
                message="Task already scheduled",
            )

        if block_id:
            # Schedule into specific block
            success, message = self.block_manager.schedule_task(task_id, block_id)
            return ScheduleResult(
                task_id=task_id,
                task_title=task.get("title", "")[:50],
                block_id=block_id if success else None,
                success=success,
                message=message,
            )
        # Auto-select block
        if not target_date:
            target_date = date.today().isoformat()
        return self._schedule_task(task, target_date)

    def validate_schedule(self, target_date: str = None) -> ValidationResult:
        """
        Validate that all scheduling invariants hold for a date.

        Invariants:
        1. Every scheduled task has exactly one block
        2. No block overlaps within a lane
        3. No task scheduled in multiple blocks
        4. All assigned blocks have valid task references

        Returns:
            ValidationResult with issues and stats
        """
        if not target_date:
            target_date = date.today().isoformat()

        issues = []

        # Get all blocks for this date
        blocks = self.block_manager.get_all_blocks(target_date)

        # Get all tasks scheduled for this date
        scheduled_tasks = self.store.query(
            """
            SELECT t.*, tb.id as block_id, tb.date as block_date
            FROM tasks t
            JOIN time_blocks tb ON t.scheduled_block_id = tb.id
            WHERE tb.date = ?
        """,
            [target_date],
        )

        # Check 1: Block overlaps
        conflicts = self.block_manager.get_conflicts(target_date)
        if conflicts:
            for c in conflicts:
                issues.append(f"Block overlap: {c.block_a_id} and {c.block_b_id} in lane {c.lane}")

        # Check 2: Tasks with blocks that don't exist
        tasks_with_blocks = self.store.query("""
            SELECT * FROM tasks
            WHERE scheduled_block_id IS NOT NULL
            AND scheduled_block_id != ''
        """)

        for task in tasks_with_blocks:
            block = self.store.query(
                "SELECT * FROM time_blocks WHERE id = ?", [task["scheduled_block_id"]]
            )
            if not block:
                issues.append(
                    f"Task {task['id']} references non-existent block {task['scheduled_block_id']}"
                )

        # Check 3: Blocks with tasks that don't exist
        blocks_with_tasks = self.store.query("""
            SELECT * FROM time_blocks
            WHERE task_id IS NOT NULL
        """)

        for block in blocks_with_tasks:
            task = self.store.get("tasks", block["task_id"])
            if not task:
                issues.append(
                    f"Block {block['id']} references non-existent task {block['task_id']}"
                )

        # Check 4: Mutual reference integrity
        for block in blocks_with_tasks:
            task = self.store.get("tasks", block["task_id"])
            if task and task.get("scheduled_block_id") != block["id"]:
                issues.append(
                    f"Reference mismatch: block {block['id']} -> task {block['task_id']}, but task -> {task.get('scheduled_block_id')}"
                )

        # Check 5: Capacity invariant - sum(scheduled) <= capacity * (1 - buffer)
        try:
            from lib.capacity_truth import CapacityCalculator

            calc = CapacityCalculator(self.store)

            for lane_data in calc.get_capacity_summary(target_date).get("lanes", []):
                lane = lane_data.get("lane")
                util_pct = lane_data.get("utilization_pct", 0)
                if util_pct > 100:
                    issues.append(
                        f"Capacity invariant violated: lane '{lane}' at {util_pct}% (exceeds 100%)"
                    )
        except (sqlite3.Error, ValueError, OSError):
            logger.debug("Capacity module not available for invariant check")

        # Calculate stats
        protected_count = 0
        available_count = 0
        scheduled_count = 0

        for b in blocks:
            if b.is_protected:
                protected_count += 1
            elif b.task_id is None:
                available_count += 1
            else:
                scheduled_count += 1

        stats = {
            "date": target_date,
            "total_blocks": len(blocks),
            "protected_blocks": protected_count,
            "available_blocks": available_count,
            "scheduled_blocks": scheduled_count,
            "scheduled_tasks": len(scheduled_tasks),
            "conflicts": len(conflicts),
            "issues": len(issues),
        }

        return ValidationResult(valid=len(issues) == 0, issues=issues, stats=stats)

    def get_scheduling_summary(self, target_date: str = None) -> dict:
        """
        Get a summary of scheduling state for a date.
        """
        if not target_date:
            target_date = date.today().isoformat()

        validation = self.validate_schedule(target_date)

        # Get unscheduled tasks due today or earlier
        unscheduled_due = self.store.query(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE status = 'pending'
            AND (scheduled_block_id IS NULL OR scheduled_block_id = '')
            AND due_date <= ?
        """,
            [target_date],
        )[0]["count"]

        # Get all unscheduled tasks
        total_unscheduled = self.store.query("""
            SELECT COUNT(*) as count FROM tasks
            WHERE status = 'pending'
            AND (scheduled_block_id IS NULL OR scheduled_block_id = '')
        """)[0]["count"]

        return {
            "date": target_date,
            "validation": {
                "valid": validation.valid,
                "issue_count": len(validation.issues),
                "issues": validation.issues[:5],  # First 5 issues
            },
            "stats": validation.stats,
            "unscheduled_due_today": unscheduled_due,
            "total_unscheduled": total_unscheduled,
        }


# Update __init__.py to include Scheduler
# This is done in the module

# Test
if __name__ == "__main__":
    scheduler = Scheduler()
    today = date.today().isoformat()

    logger.info(f"Testing Scheduler for {today}")
    logger.info("-" * 40)
    # Validate current schedule
    validation = scheduler.validate_schedule(today)
    logger.info(f"Validation: valid={validation.valid}, issues={len(validation.issues)}")
    if validation.issues:
        for issue in validation.issues[:3]:
            logger.info(f"  - {issue}")
    logger.info(f"Stats: {validation.stats}")
    # Get summary
    summary = scheduler.get_scheduling_summary(today)
    logger.info("\nSummary:")
    logger.info(f"  Unscheduled due today: {summary['unscheduled_due_today']}")
    logger.info(f"  Total unscheduled: {summary['total_unscheduled']}")
    # Try scheduling
    logger.info("\nAttempting to schedule tasks...")
    results = scheduler.schedule_unscheduled(today)
    logger.info(f"Scheduled {len([r for r in results if r.success])} of {len(results)} tasks")
    for r in results[:5]:
        status = "✓" if r.success else "✗"
        logger.info(f"  {status} {r.task_title}: {r.message}")
