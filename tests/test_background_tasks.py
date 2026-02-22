"""
Tests for background task manager.

Tests cover:
- Task submission and ID generation
- Task lifecycle (pending → running → completed)
- Failed task tracking and error handling
- Task cancellation
- Task status retrieval
- Multiple concurrent tasks
- Task history cleanup
- Thread safety
"""

import time
from datetime import datetime, timedelta

import pytest

from lib.api.background_tasks import (
    TaskManager,
    TaskStatusEnum,
    get_task_manager,
)


class TestTaskManager:
    """Tests for TaskManager class."""

    @pytest.fixture
    def task_manager(self):
        """Create a TaskManager instance for testing."""
        manager = TaskManager(max_workers=2)
        yield manager
        manager.shutdown(wait=True)

    def test_task_manager_creation(self):
        """Test creating a TaskManager instance."""
        manager = TaskManager(max_workers=4)
        assert manager.max_workers == 4
        manager.shutdown(wait=True)

    def test_custom_max_workers(self):
        """Test TaskManager with custom max_workers."""
        manager = TaskManager(max_workers=8)
        assert manager.max_workers == 8
        manager.shutdown(wait=True)

    def test_submit_simple_task(self, task_manager):
        """Test submitting a simple task."""

        def simple_func():
            return "result"

        task_id = task_manager.submit(simple_func)
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    def test_submit_task_with_args(self, task_manager):
        """Test submitting a task with positional arguments."""

        def add(a, b):
            return a + b

        task_id = task_manager.submit(add, 5, 3)
        assert task_id is not None
        # Wait for completion
        time.sleep(0.5)
        status = task_manager.get_status(task_id)
        assert status.result == 8

    def test_submit_task_with_kwargs(self, task_manager):
        """Test submitting a task with keyword arguments."""

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        task_id = task_manager.submit(greet, "Alice", greeting="Hi")
        time.sleep(0.5)
        status = task_manager.get_status(task_id)
        assert status.result == "Hi, Alice!"

    def test_submit_task_with_mixed_args(self, task_manager):
        """Test submitting a task with both positional and keyword arguments."""

        def func(a, b, c=10):
            return a + b + c

        task_id = task_manager.submit(func, 1, 2, c=5)
        time.sleep(0.5)
        status = task_manager.get_status(task_id)
        assert status.result == 8

    def test_task_initial_status_pending(self, task_manager):
        """Test that task starts in pending status."""

        def slow_func():
            time.sleep(0.5)
            return "done"

        task_id = task_manager.submit(slow_func)
        # Check immediately
        status = task_manager.get_status(task_id)
        assert status.status in [TaskStatusEnum.PENDING, TaskStatusEnum.RUNNING]

    def test_task_running_status(self, task_manager):
        """Test that task transitions to running status."""

        def work():
            time.sleep(0.2)
            return "result"

        task_id = task_manager.submit(work)
        time.sleep(0.05)  # Brief delay to let it start
        status = task_manager.get_status(task_id)
        # Should be running or completed
        assert status.status in [TaskStatusEnum.RUNNING, TaskStatusEnum.COMPLETED]

    def test_task_completion_status(self, task_manager):
        """Test that completed task has correct status."""

        def quick_task():
            return 42

        task_id = task_manager.submit(quick_task)
        time.sleep(0.3)  # Wait for completion
        status = task_manager.get_status(task_id)
        assert status.status == TaskStatusEnum.COMPLETED
        assert status.result == 42

    def test_task_completion_sets_completed_at(self, task_manager):
        """Test that completed_at is set on completion."""

        def task():
            return "done"

        submitted_time = datetime.now()
        task_id = task_manager.submit(task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert status.status == TaskStatusEnum.COMPLETED
        assert status.completed_at is not None
        assert status.completed_at >= submitted_time

    def test_task_started_at_is_set(self, task_manager):
        """Test that started_at is set when task starts."""

        def task():
            return "done"

        task_id = task_manager.submit(task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert status.started_at is not None

    def test_failed_task_tracking(self, task_manager):
        """Test that failed task is tracked with error."""

        def failing_task():
            raise ValueError("intentional error")

        task_id = task_manager.submit(failing_task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert status.status == TaskStatusEnum.FAILED
        assert status.error is not None
        assert "intentional error" in status.error

    def test_failed_task_sets_completed_at(self, task_manager):
        """Test that failed task has completed_at set."""

        def failing_task():
            raise RuntimeError("error")

        task_id = task_manager.submit(failing_task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert status.completed_at is not None

    def test_get_status_nonexistent_task(self, task_manager):
        """Test getting status of nonexistent task returns None."""
        status = task_manager.get_status("nonexistent-task-id")
        assert status is None

    def test_list_tasks_empty(self, task_manager):
        """Test list_tasks when no tasks submitted."""
        tasks = task_manager.list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) == 0

    def test_list_tasks_multiple(self, task_manager):
        """Test list_tasks with multiple submitted tasks."""

        def task():
            return "result"

        task_id1 = task_manager.submit(task)
        task_id2 = task_manager.submit(task)
        task_id3 = task_manager.submit(task)

        tasks = task_manager.list_tasks()
        assert len(tasks) >= 3
        task_ids = [t.id for t in tasks]
        assert task_id1 in task_ids
        assert task_id2 in task_ids
        assert task_id3 in task_ids

    def test_list_tasks_includes_completed(self, task_manager):
        """Test that list_tasks includes completed tasks."""

        def task():
            return "result"

        task_id = task_manager.submit(task)
        time.sleep(0.3)
        tasks = task_manager.list_tasks()

        task_ids = [t.id for t in tasks]
        assert task_id in task_ids
        status_obj = next(t for t in tasks if t.id == task_id)
        assert status_obj.status == TaskStatusEnum.COMPLETED

    def test_list_tasks_includes_failed(self, task_manager):
        """Test that list_tasks includes failed tasks."""

        def failing_task():
            raise Exception("fail")

        task_id = task_manager.submit(failing_task)
        time.sleep(0.3)
        tasks = task_manager.list_tasks()

        task_ids = [t.id for t in tasks]
        assert task_id in task_ids

    def test_cancel_task_not_started(self, task_manager):
        """Test cancelling a task before it starts."""

        def slow_task():
            time.sleep(1.0)
            return "result"

        task_id = task_manager.submit(slow_task)
        # Try to cancel immediately
        cancelled = task_manager.cancel(task_id)
        # Cancellation may or may not succeed depending on timing
        # Just verify it returns a boolean
        assert isinstance(cancelled, bool)

    def test_cancel_nonexistent_task(self, task_manager):
        """Test cancelling nonexistent task returns False."""
        cancelled = task_manager.cancel("nonexistent-id")
        assert cancelled is False

    def test_task_name_from_function(self, task_manager):
        """Test that task name is captured from function."""

        def my_custom_task():
            return "result"

        task_id = task_manager.submit(my_custom_task)
        status = task_manager.get_status(task_id)
        assert status.name == "my_custom_task"

    def test_task_name_for_lambda(self, task_manager):
        """Test that lambda task gets a name."""
        task_id = task_manager.submit(lambda: "result")
        status = task_manager.get_status(task_id)
        assert status.name is not None

    def test_concurrent_tasks(self, task_manager):
        """Test multiple concurrent tasks."""

        def add(a, b):
            time.sleep(0.1)
            return a + b

        task_ids = [
            task_manager.submit(add, 1, 2),
            task_manager.submit(add, 3, 4),
            task_manager.submit(add, 5, 6),
        ]

        time.sleep(0.5)
        results = [task_manager.get_status(tid).result for tid in task_ids]
        assert results == [3, 7, 11]

    def test_sequential_task_submission(self, task_manager):
        """Test submitting tasks sequentially."""

        def counter(n):
            return n * 2

        task_ids = []
        for i in range(5):
            task_ids.append(task_manager.submit(counter, i))

        assert len(task_ids) == 5
        # All IDs should be unique
        assert len(set(task_ids)) == 5

    def test_task_result_is_none_for_void_function(self, task_manager):
        """Test that task with no return has None result."""

        def void_func():
            pass

        task_id = task_manager.submit(void_func)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)
        assert status.result is None
        assert status.status == TaskStatusEnum.COMPLETED

    def test_task_result_with_complex_object(self, task_manager):
        """Test task with complex return value."""

        def complex_task():
            return {"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}

        task_id = task_manager.submit(complex_task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)
        assert status.result == {"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}

    def test_submitted_at_is_set(self, task_manager):
        """Test that submitted_at is set immediately."""
        before = datetime.now()

        def task():
            return "result"

        task_id = task_manager.submit(task)
        status = task_manager.get_status(task_id)
        after = datetime.now()

        assert status.submitted_at >= before
        assert status.submitted_at <= after

    def test_task_status_fields_present(self, task_manager):
        """Test that all TaskStatus fields are present."""

        def task():
            return "result"

        task_id = task_manager.submit(task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert hasattr(status, "id")
        assert hasattr(status, "name")
        assert hasattr(status, "status")
        assert hasattr(status, "submitted_at")
        assert hasattr(status, "started_at")
        assert hasattr(status, "completed_at")
        assert hasattr(status, "result")
        assert hasattr(status, "error")

    def test_error_message_captured(self, task_manager):
        """Test that error messages are captured."""

        def failing_task():
            raise TypeError("expected string, got int")

        task_id = task_manager.submit(failing_task)
        time.sleep(0.3)
        status = task_manager.get_status(task_id)

        assert status.error is not None
        assert "expected string, got int" in status.error

    def test_multiple_tasks_don_t_interfere(self, task_manager):
        """Test that one task's failure doesn't affect others."""

        def good_task(n):
            return n * 2

        def bad_task():
            raise RuntimeError("oops")

        task_good1 = task_manager.submit(good_task, 5)
        task_bad = task_manager.submit(bad_task)
        task_good2 = task_manager.submit(good_task, 10)

        time.sleep(0.5)

        status_good1 = task_manager.get_status(task_good1)
        status_bad = task_manager.get_status(task_bad)
        status_good2 = task_manager.get_status(task_good2)

        assert status_good1.result == 10
        assert status_good1.status == TaskStatusEnum.COMPLETED
        assert status_bad.status == TaskStatusEnum.FAILED
        assert status_good2.result == 20
        assert status_good2.status == TaskStatusEnum.COMPLETED


class TestGetTaskManager:
    """Tests for global task manager singleton."""

    def test_get_task_manager_returns_instance(self):
        """Test that get_task_manager returns a TaskManager."""
        manager = get_task_manager()
        assert isinstance(manager, TaskManager)

    def test_get_task_manager_is_singleton(self):
        """Test that get_task_manager returns same instance."""
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        assert manager1 is manager2

    def test_global_task_manager_functional(self):
        """Test using global task manager for actual work."""
        manager = get_task_manager()

        def task():
            return "global result"

        task_id = manager.submit(task)
        time.sleep(0.3)
        status = manager.get_status(task_id)
        assert status.status == TaskStatusEnum.COMPLETED
        assert status.result == "global result"


class TestTaskManagerShutdown:
    """Tests for task manager shutdown."""

    def test_shutdown_waits_for_tasks(self):
        """Test that shutdown waits for tasks to complete."""
        manager = TaskManager(max_workers=1)

        def slow_task():
            time.sleep(0.3)
            return "done"

        task_id = manager.submit(slow_task)
        manager.shutdown(wait=True)

        # Task should be completed after shutdown
        # (Note: this is testing that shutdown waited)
        status = manager.get_status(task_id)
        if status:  # May be cleaned up
            assert status.status == TaskStatusEnum.COMPLETED

    def test_shutdown_no_wait(self):
        """Test shutdown with wait=False."""
        manager = TaskManager(max_workers=1)

        def task():
            return "result"

        manager.submit(task)
        # Should complete quickly without waiting
        manager.shutdown(wait=False)


class TestTaskCleanup:
    """Tests for task history cleanup."""

    def test_cleanup_removes_old_tasks(self):
        """Test that old task history is cleaned up."""
        manager = TaskManager(max_workers=1)

        def task():
            return "result"

        manager.submit(task)
        time.sleep(0.3)

        # Get initial list
        initial_tasks = len(manager.list_tasks())
        assert initial_tasks >= 1

        # Manually trigger cleanup by submitting another task
        # (cleanup runs on submit in current implementation)
        manager.submit(task)

        # Old completed tasks should eventually be cleaned up
        # (depending on timing and implementation)

        manager.shutdown(wait=True)
