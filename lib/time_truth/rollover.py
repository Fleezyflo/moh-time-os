"""
Rollover - Move incomplete tasks to the next day.

Runs nightly to:
1. Find tasks scheduled for today that aren't done
2. Unschedule them from today's blocks
3. Schedule them into tomorrow's available blocks
4. Log the rollover for reporting
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from lib.state_store import get_store
from lib.time_truth.block_manager import BlockManager
from lib.time_truth.calendar_sync import CalendarSync
from lib.time_truth.scheduler import Scheduler

logger = logging.getLogger(__name__)


@dataclass
class RolloverItem:
    task_id: str
    task_title: str
    from_date: str
    from_block_id: str
    to_date: str
    to_block_id: str | None
    success: bool
    reason: str


@dataclass
class RolloverReport:
    from_date: str
    to_date: str
    total_tasks: int
    rolled_over: int
    failed: int
    items: list[RolloverItem]
    timestamp: str


class Rollover:
    """
    Handles nightly rollover of incomplete tasks.

    This ensures tasks don't get lost when they miss their scheduled day.
    Tasks are moved to the next day's available blocks.
    """

    def __init__(self, store=None):
        self.store = store or get_store()
        self.block_manager = BlockManager(self.store)
        self.calendar_sync = CalendarSync(self.store)
        self.scheduler = Scheduler(self.store)

    def run_nightly(self, from_date: str = None, to_date: str = None) -> RolloverReport:
        """
        Execute nightly rollover.

        Args:
            from_date: Date to roll over FROM (defaults to yesterday)
            to_date: Date to roll over TO (defaults to today)

        Returns:
            RolloverReport with results
        """
        if not from_date:
            from_date = (date.today() - timedelta(days=1)).isoformat()
        if not to_date:
            to_date = date.today().isoformat()

        # Find incomplete tasks scheduled for from_date
        incomplete_tasks = self._get_incomplete_scheduled_tasks(from_date)

        # Ensure blocks exist for to_date
        self.calendar_sync.generate_available_blocks(to_date)

        items = []
        rolled_count = 0
        failed_count = 0

        for task in incomplete_tasks:
            result = self._rollover_task(task, from_date, to_date)
            items.append(result)

            if result.success:
                rolled_count += 1
            else:
                failed_count += 1

        report = RolloverReport(
            from_date=from_date,
            to_date=to_date,
            total_tasks=len(incomplete_tasks),
            rolled_over=rolled_count,
            failed=failed_count,
            items=items,
            timestamp=datetime.now().isoformat(),
        )

        # Log the rollover
        self._log_rollover(report)

        return report

    def _get_incomplete_scheduled_tasks(self, target_date: str) -> list[dict]:
        """Get tasks that were scheduled for a date but aren't done."""
        return self.store.query(
            """
            SELECT t.*, tb.id as block_id
            FROM tasks t
            JOIN time_blocks tb ON t.scheduled_block_id = tb.id
            WHERE tb.date = ?
            AND t.status != 'done'
            AND t.status != 'completed'
            AND t.status != 'archived'
        """,
            [target_date],
        )

    def _rollover_task(self, task: dict, from_date: str, to_date: str) -> RolloverItem:
        """Roll over a single task from one date to another."""
        task_id = task["id"]
        task_title = task.get("title", "")[:50]
        from_block_id = task.get("block_id") or task.get("scheduled_block_id")

        # Step 1: Unschedule from current block
        success, msg = self.block_manager.unschedule_task(task_id)

        if not success:
            return RolloverItem(
                task_id=task_id,
                task_title=task_title,
                from_date=from_date,
                from_block_id=from_block_id,
                to_date=to_date,
                to_block_id=None,
                success=False,
                reason=f"Failed to unschedule: {msg}",
            )

        # Step 2: Schedule into new date
        result = self.scheduler.schedule_specific_task(task_id, target_date=to_date)

        if result.success:
            return RolloverItem(
                task_id=task_id,
                task_title=task_title,
                from_date=from_date,
                from_block_id=from_block_id,
                to_date=to_date,
                to_block_id=result.block_id,
                success=True,
                reason="Rolled over successfully",
            )
        return RolloverItem(
            task_id=task_id,
            task_title=task_title,
            from_date=from_date,
            from_block_id=from_block_id,
            to_date=to_date,
            to_block_id=None,
            success=False,
            reason=f"Rescheduling failed: {result.message}",
        )

    def _log_rollover(self, report: RolloverReport):
        """Log rollover to the database for reporting."""
        import json

        self.store.insert(
            "cycle_logs",
            {
                "id": f"rollover_{report.from_date}_{datetime.now().strftime('%H%M%S')}",
                "cycle_number": 0,
                "phase": "rollover",
                "data": json.dumps(
                    {
                        "from_date": report.from_date,
                        "to_date": report.to_date,
                        "total": report.total_tasks,
                        "rolled": report.rolled_over,
                        "failed": report.failed,
                        "items": [
                            {
                                "task_id": i.task_id,
                                "task_title": i.task_title,
                                "success": i.success,
                                "reason": i.reason,
                            }
                            for i in report.items
                        ],
                    }
                ),
                "duration_ms": 0,
                "created_at": report.timestamp,
            },
        )

    def get_rollover_report(self, target_date: str) -> dict | None:
        """Get the most recent rollover report for a date."""
        import json

        logs = self.store.query(
            """
            SELECT * FROM cycle_logs
            WHERE phase = 'rollover'
            AND json_extract(data, '$.from_date') = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
            [target_date],
        )

        if not logs:
            return None

        log = logs[0]
        return json.loads(log["data"])

    def get_rollover_history(self, days: int = 7) -> list[dict]:
        """Get rollover history for the past N days."""
        import json

        logs = self.store.query(
            """
            SELECT * FROM cycle_logs
            WHERE phase = 'rollover'
            AND created_at >= date('now', ?)
            ORDER BY created_at DESC
        """,
            [f"-{days} days"],
        )

        return [json.loads(log["data"]) for log in logs]

    def preview_rollover(self, from_date: str = None) -> dict:
        """
        Preview what would be rolled over without executing.

        Useful for checking before running.
        """
        if not from_date:
            from_date = (date.today() - timedelta(days=1)).isoformat()

        incomplete = self._get_incomplete_scheduled_tasks(from_date)

        return {
            "from_date": from_date,
            "tasks_to_rollover": len(incomplete),
            "tasks": [
                {
                    "id": t["id"],
                    "title": t.get("title", "")[:50],
                    "status": t.get("status"),
                    "block_id": t.get("block_id") or t.get("scheduled_block_id"),
                }
                for t in incomplete
            ],
        }


# Update __init__.py to include Rollover
# This is done in the module

# Test
if __name__ == "__main__":
    rollover = Rollover()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    logger.info("Testing Rollover")
    logger.info(f"From: {yesterday}")
    logger.info(f"To: {today}")
    logger.info("-" * 40)
    # Preview
    preview = rollover.preview_rollover(yesterday)
    logger.info(f"Preview: {preview['tasks_to_rollover']} tasks would roll over")
    for task in preview["tasks"][:5]:
        logger.info(f"  - {task['title']}")
    # Only run if there are tasks to rollover
    if preview["tasks_to_rollover"] > 0:
        logger.info("\nExecuting rollover...")
        report = rollover.run_nightly(yesterday, today)
        logger.info(f"Results: {report.rolled_over} rolled, {report.failed} failed")
    else:
        logger.info("\nNo tasks to roll over")
