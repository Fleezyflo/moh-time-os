"""Tests for Asana collector — verifies completed task sync and full project coverage."""

import importlib
import sys
import types
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest


def _get_asana_collector_class():
    """Load AsanaCollector with a mocked BaseCollector to avoid import chain issues."""
    # Create a fake base module to satisfy `from .base import BaseCollector`
    fake_base = types.ModuleType("lib.collectors.base")

    class FakeBaseCollector:
        def __init__(self, config=None, store=None):
            self.config = config or {}
            self.store = store
            self.logger = MagicMock()

    fake_base.BaseCollector = FakeBaseCollector

    # Register fake package and base
    pkg = types.ModuleType("lib.collectors")
    pkg.__path__ = ["lib/collectors"]
    pkg.__package__ = "lib.collectors"

    saved = {}
    for key in ("lib.collectors", "lib.collectors.base", "lib.collectors.asana"):
        saved[key] = sys.modules.pop(key, None)

    sys.modules["lib.collectors"] = pkg
    sys.modules["lib.collectors.base"] = fake_base

    try:
        spec = importlib.util.spec_from_file_location(
            "lib.collectors.asana",
            "lib/collectors/asana.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["lib.collectors.asana"] = mod
        spec.loader.exec_module(mod)
        return mod.AsanaCollector
    finally:
        # Restore originals to avoid polluting other tests
        for key, val in saved.items():
            if val is not None:
                sys.modules[key] = val


# Cache the class
_AsanaCollector = _get_asana_collector_class()


@pytest.fixture
def collector():
    """Create an AsanaCollector with mocked store."""
    store = MagicMock()
    return _AsanaCollector(config={}, store=store)


@pytest.fixture
def sample_tasks():
    """Sample Asana API response data."""
    return {
        "tasks": [
            {
                "gid": "1001",
                "name": "Design homepage",
                "completed": False,
                "completed_at": None,
                "due_on": "2026-12-31",
                "assignee": {"name": "Ahmed Salah"},
                "tags": [{"name": "design"}],
                "notes": "Homepage redesign task",
                "created_at": "2026-01-01T00:00:00Z",
                "modified_at": "2026-01-15T00:00:00Z",
                "_project_name": "Website Redesign",
                "_project_gid": "proj_1",
            },
            {
                "gid": "1002",
                "name": "Write copy",
                "completed": True,
                "completed_at": "2026-01-20T14:30:00Z",
                "due_on": "2026-01-15",
                "assignee": {"name": "Noura El Rakaiby"},
                "tags": [],
                "notes": "Copy for landing page",
                "created_at": "2026-01-01T00:00:00Z",
                "modified_at": "2026-01-20T14:30:00Z",
                "_project_name": "Website Redesign",
                "_project_gid": "proj_1",
            },
            {
                "gid": "1003",
                "name": "Overdue task",
                "completed": False,
                "completed_at": None,
                "due_on": "2025-06-01",
                "assignee": None,
                "tags": [],
                "notes": "",
                "created_at": "2025-05-01T00:00:00Z",
                "modified_at": "2025-06-02T00:00:00Z",
                "_project_name": "Old Project",
                "_project_gid": "proj_2",
            },
            {
                "gid": "1004",
                "name": "No due date task",
                "completed": False,
                "completed_at": None,
                "due_on": None,
                "assignee": {"name": "Fady"},
                "tags": [{"name": "urgent"}, {"name": "client"}],
                "notes": None,
                "created_at": "2026-02-01T00:00:00Z",
                "modified_at": "2026-02-10T00:00:00Z",
                "_project_name": "Retainer Work",
                "_project_gid": "proj_3",
            },
        ]
    }


class TestAsanaTransform:
    """Tests for the transform method."""

    def test_completed_task_has_completed_status(self, collector, sample_tasks):
        """Completed tasks must have status='completed'."""
        result = collector.transform(sample_tasks)
        completed_task = next(t for t in result if t["source_id"] == "1002")
        assert completed_task["status"] == "completed"

    def test_completed_task_has_completed_at(self, collector, sample_tasks):
        """Completed tasks must have completed_at populated."""
        result = collector.transform(sample_tasks)
        completed_task = next(t for t in result if t["source_id"] == "1002")
        assert completed_task["completed_at"] == "2026-01-20T14:30:00Z"

    def test_active_task_no_completed_at(self, collector, sample_tasks):
        """Active tasks must have completed_at=None."""
        result = collector.transform(sample_tasks)
        active_task = next(t for t in result if t["source_id"] == "1001")
        assert active_task["status"] == "active"
        assert active_task["completed_at"] is None

    def test_overdue_task_detected(self, collector, sample_tasks):
        """Past-due incomplete tasks must have status='overdue'."""
        result = collector.transform(sample_tasks)
        overdue_task = next(t for t in result if t["source_id"] == "1003")
        assert overdue_task["status"] == "overdue"
        assert overdue_task["priority"] == "high"

    def test_no_due_date_is_active(self, collector, sample_tasks):
        """Tasks without due date should be 'active'."""
        result = collector.transform(sample_tasks)
        no_due = next(t for t in result if t["source_id"] == "1004")
        assert no_due["status"] == "active"

    def test_all_tasks_transformed(self, collector, sample_tasks):
        """All valid tasks should be transformed."""
        result = collector.transform(sample_tasks)
        assert len(result) == 4

    def test_skips_tasks_without_gid(self, collector):
        """Tasks without gid should be skipped."""
        data = {"tasks": [{"name": "No GID task"}]}
        result = collector.transform(data)
        assert len(result) == 0

    def test_assignee_name_extracted(self, collector, sample_tasks):
        """Assignee name should be extracted from nested object."""
        result = collector.transform(sample_tasks)
        task = next(t for t in result if t["source_id"] == "1001")
        assert task["assignee"] == "Ahmed Salah"

    def test_null_assignee_handled(self, collector, sample_tasks):
        """Null assignee should not crash."""
        result = collector.transform(sample_tasks)
        task = next(t for t in result if t["source_id"] == "1003")
        assert task["assignee"] is None

    def test_tags_serialized_as_json(self, collector, sample_tasks):
        """Tags should be JSON-serialized list of names."""
        import json

        result = collector.transform(sample_tasks)
        task = next(t for t in result if t["source_id"] == "1004")
        tags = json.loads(task["tags"])
        assert tags == ["urgent", "client"]


class TestAsanaCollect:
    """Tests for the collect method — no project limit."""

    def test_collect_no_project_limit(self):
        """Collector should process all projects, not just 15."""
        import inspect

        source = inspect.getsource(_AsanaCollector.collect)
        assert "[:15]" not in source, "Project limit [:15] still present in collector"
        assert "completed=False" not in source, "completed=False filter still present"

    def test_collect_source_has_no_completed_filter(self):
        """Collector source must not filter out completed tasks."""
        import inspect

        source = inspect.getsource(_AsanaCollector.collect)
        assert "completed=False" not in source
        assert "completed=True" not in source
