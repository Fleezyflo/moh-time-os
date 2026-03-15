"""Tests for Tasks collector — verifies Google Tasks transformation and priority logic."""

import importlib
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest


def _get_tasks_collector_class():
    """Load TasksCollector with a mocked BaseCollector to avoid import chain issues."""
    fake_base = types.ModuleType("lib.collectors.base")

    class FakeBaseCollector:
        def __init__(self, config=None, store=None):
            self.config = config or {}
            self.store = store
            self.logger = MagicMock()

        def _run_command(self, cmd):
            return ""

        def _parse_json_output(self, output):
            return json.loads(output)

    fake_base.BaseCollector = FakeBaseCollector

    pkg = types.ModuleType("lib.collectors")
    pkg.__path__ = ["lib/collectors"]
    pkg.__package__ = "lib.collectors"

    saved = {}
    for key in ("lib.collectors", "lib.collectors.base", "lib.collectors.tasks"):
        saved[key] = sys.modules.pop(key, None)

    sys.modules["lib.collectors"] = pkg
    sys.modules["lib.collectors.base"] = fake_base

    try:
        spec = importlib.util.spec_from_file_location(
            "lib.collectors.tasks",
            "lib/collectors/tasks.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["lib.collectors.tasks"] = mod
        spec.loader.exec_module(mod)
        return mod.TasksCollector
    finally:
        for key, val in saved.items():
            if val is not None:
                sys.modules[key] = val


_TasksCollector = _get_tasks_collector_class()


@pytest.fixture
def collector():
    """Create a TasksCollector with mocked store."""
    store = MagicMock()
    return _TasksCollector(config={}, store=store)


@pytest.fixture
def sample_raw_data():
    """Sample raw data from Google Tasks."""
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    return {
        "tasks": [
            {
                "id": "t001",
                "title": "Review proposal",
                "status": "needsAction",
                "due": tomorrow,
                "notes": "Important client",
                "updated": "2026-03-01T10:00:00Z",
                "_list_name": "Work",
                "_list_id": "list_1",
            },
            {
                "id": "t002",
                "title": "Send invoice",
                "status": "completed",
                "due": yesterday,
                "notes": "",
                "updated": "2026-03-01T10:00:00Z",
                "_list_name": "Work",
                "_list_id": "list_1",
            },
            {
                "id": "t003",
                "title": "Overdue task",
                "status": "needsAction",
                "due": yesterday,
                "notes": None,
                "updated": "2026-02-20T10:00:00Z",
                "_list_name": "Personal",
                "_list_id": "list_2",
            },
            {
                "id": "t004",
                "title": "No due date",
                "status": "needsAction",
                "due": None,
                "notes": "Some notes",
                "updated": "2026-03-01T10:00:00Z",
                "_list_name": "Work",
                "_list_id": "list_1",
            },
        ],
        "lists": [
            {"id": "list_1", "title": "Work"},
            {"id": "list_2", "title": "Personal"},
        ],
    }


class TestTasksTransform:
    """Tests for the transform method."""

    def test_completed_tasks_skipped(self, collector, sample_raw_data):
        """Completed tasks should not appear in output."""
        result = collector.transform(sample_raw_data)
        ids = [t["source_id"] for t in result]
        assert "t002" not in ids

    def test_active_tasks_included(self, collector, sample_raw_data):
        result = collector.transform(sample_raw_data)
        ids = [t["source_id"] for t in result]
        assert "t001" in ids
        assert "t003" in ids
        assert "t004" in ids

    def test_task_count(self, collector, sample_raw_data):
        result = collector.transform(sample_raw_data)
        assert len(result) == 3

    def test_source_is_google_tasks(self, collector, sample_raw_data):
        result = collector.transform(sample_raw_data)
        for task in result:
            assert task["source"] == "google_tasks"

    def test_id_prefix(self, collector, sample_raw_data):
        result = collector.transform(sample_raw_data)
        task = next(t for t in result if t["source_id"] == "t001")
        assert task["id"] == "gtask_t001"

    def test_project_from_list_name(self, collector, sample_raw_data):
        result = collector.transform(sample_raw_data)
        task = next(t for t in result if t["source_id"] == "t001")
        assert task["project"] == "Work"

    def test_no_assignee(self, collector, sample_raw_data):
        """Google Tasks doesn't have assignees."""
        result = collector.transform(sample_raw_data)
        for task in result:
            assert task["assignee"] is None

    def test_tasks_without_id_skipped(self, collector):
        data = {"tasks": [{"title": "No ID task", "status": "needsAction"}]}
        result = collector.transform(data)
        assert len(result) == 0

    def test_empty_tasks(self, collector):
        result = collector.transform({"tasks": []})
        assert result == []


class TestMapStatus:
    """Tests for status mapping."""

    def test_completed(self, collector):
        assert collector._map_status({"status": "completed"}) == "done"

    def test_needs_action(self, collector):
        assert collector._map_status({"status": "needsAction"}) == "pending"

    def test_unknown_status(self, collector):
        assert collector._map_status({"status": "unknown"}) == "pending"

    def test_empty_status(self, collector):
        assert collector._map_status({}) == "pending"


class TestExtractDueDate:
    """Tests for due date extraction."""

    def test_valid_due_date(self, collector):
        result = collector._extract_due_date({"due": "2026-03-15T00:00:00.000Z"})
        assert result == "2026-03-15"

    def test_no_due_date(self, collector):
        assert collector._extract_due_date({}) is None

    def test_none_due_date(self, collector):
        assert collector._extract_due_date({"due": None}) is None


class TestComputePriority:
    """Tests for priority computation."""

    def test_base_score_no_due(self, collector):
        score = collector._compute_priority({})
        assert score == 50

    def test_notes_add_priority(self, collector):
        score = collector._compute_priority({"notes": "Important"})
        assert score == 55

    def test_overdue_high_priority(self, collector):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT00:00:00.000Z"
        )
        score = collector._compute_priority({"due": yesterday})
        assert score > 80

    def test_due_today_high_priority(self, collector):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")
        score = collector._compute_priority({"due": today})
        assert score >= 85

    def test_priority_capped_at_100(self, collector):
        long_overdue = (datetime.now(timezone.utc) - timedelta(days=100)).strftime(
            "%Y-%m-%dT00:00:00.000Z"
        )
        score = collector._compute_priority({"due": long_overdue, "notes": "Urgent"})
        assert score <= 100
