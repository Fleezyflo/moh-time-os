"""
Thread-safe background task manager for MOH TIME OS API.

Features:
- TaskManager: Submit and track background tasks
- TaskStatus: Task state with lifecycle tracking
- Thread-safe execution using ThreadPoolExecutor
- Configurable max workers and history retention
- Task history cleanup after 1 hour
"""

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from lib.compat import StrEnum

logger = logging.getLogger(__name__)


class TaskStatusEnum(StrEnum):
    """Task status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStatus:
    """Immutable task status snapshot."""

    id: str
    name: str
    status: TaskStatusEnum
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None


class TaskManager:
    """
    Thread-safe background task manager.

    Submits tasks to a thread pool, tracks status, and cleans up history.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize TaskManager.

        Args:
            max_workers: Maximum number of concurrent worker threads
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.RLock()
        self._history_ttl = timedelta(hours=1)

    def submit(self, func: Callable, *args: Any, **kwargs: Any) -> str:
        """
        Submit a background task for execution.

        Args:
            func: Callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Task ID (UUID)
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()

        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "name": getattr(func, "__name__", "task"),
                "status": TaskStatusEnum.PENDING,
                "submitted_at": now,
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "func": func,
                "args": args,
                "kwargs": kwargs,
            }

            # Submit to executor with wrapper that updates status
            future = self._executor.submit(self._run_task, task_id)
            self._futures[task_id] = future

            # Cleanup old history
            self._cleanup_old_tasks()

            logger.info(f"Task {task_id} ({self._tasks[task_id]['name']}) submitted")

        return task_id

    def _run_task(self, task_id: str) -> Any:
        """Execute a task and update its status."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            task["status"] = TaskStatusEnum.RUNNING
            task["started_at"] = datetime.now()

        try:
            result = task["func"](*task["args"], **task["kwargs"])
            with self._lock:
                self._tasks[task_id]["result"] = result
                self._tasks[task_id]["status"] = TaskStatusEnum.COMPLETED
                self._tasks[task_id]["completed_at"] = datetime.now()
            logger.info(f"Task {task_id} completed successfully")
            return result
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["status"] = TaskStatusEnum.FAILED
                self._tasks[task_id]["completed_at"] = datetime.now()
            logger.error(f"Task {task_id} failed: {e}")
            raise

    def get_status(self, task_id: str) -> TaskStatus | None:
        """
        Get status of a task.

        Args:
            task_id: Task ID returned from submit()

        Returns:
            TaskStatus snapshot, or None if task not found
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            return TaskStatus(
                id=task["id"],
                name=task["name"],
                status=task["status"],
                submitted_at=task["submitted_at"],
                started_at=task["started_at"],
                completed_at=task["completed_at"],
                result=task["result"],
                error=task["error"],
            )

    def list_tasks(self) -> list[TaskStatus]:
        """
        Get status of all tasks (including expired history).

        Returns:
            List of TaskStatus snapshots
        """
        with self._lock:
            return [
                TaskStatus(
                    id=task["id"],
                    name=task["name"],
                    status=task["status"],
                    submitted_at=task["submitted_at"],
                    started_at=task["started_at"],
                    completed_at=task["completed_at"],
                    result=task["result"],
                    error=task["error"],
                )
                for task in self._tasks.values()
            ]

    def cancel(self, task_id: str) -> bool:
        """
        Attempt to cancel a running task.

        Note: ThreadPoolExecutor can only cancel tasks that haven't started.
        Once running, cancellation is not possible.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if already running or not found
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            future = self._futures.get(task_id)
            if future is None:
                return False

            cancelled = future.cancel()
            if cancelled:
                self._tasks[task_id]["status"] = TaskStatusEnum.CANCELLED
                self._tasks[task_id]["completed_at"] = datetime.now()
                logger.info(f"Task {task_id} cancelled")

            return cancelled

    def _cleanup_old_tasks(self) -> None:
        """Remove completed tasks older than TTL. Must be called with lock held."""
        now = datetime.now()
        expired = [
            task_id
            for task_id, task in self._tasks.items()
            if task["completed_at"] is not None and (now - task["completed_at"]) > self._history_ttl
        ]

        for task_id in expired:
            del self._tasks[task_id]
            self._futures.pop(task_id, None)
            logger.debug(f"Cleaned up expired task {task_id}")

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor and wait for pending tasks.

        Args:
            wait: If True, wait for all tasks to complete
        """
        self._executor.shutdown(wait=wait)
        logger.info("TaskManager executor shutdown")


# Global task manager instance
_task_manager: TaskManager | None = None
_task_manager_lock = threading.Lock()


def get_task_manager() -> TaskManager:
    """Get or create global TaskManager instance."""
    global _task_manager
    if _task_manager is None:
        with _task_manager_lock:
            if _task_manager is None:
                _task_manager = TaskManager()
    return _task_manager
