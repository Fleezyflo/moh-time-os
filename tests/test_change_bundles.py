"""
Tests for change_bundles module.

Covers:
- Bundle creation and persistence
- Bundle status transitions (pending → applied → rolled_back/failed)
- Rollback step generation
- BundleManager lifecycle
- list_bundles with filters
- Pruning old bundles
- Domain-specific bundle helpers
"""

import json
from datetime import datetime, timedelta, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

import pytest

from lib.change_bundles import (
    BundleManager,
    BundleStatus,
    ChangeType,
    _generate_rollback_steps,
    cleanup_old_bundles,
    create_bundle,
    create_calendar_bundle,
    create_status_change_bundle,
    create_task_bundle,
    get_bundle,
    list_bundles,
    list_pending_bundles,
    list_rollbackable_bundles,
    mark_applied,
    mark_failed,
    rollback_bundle,
)


@pytest.fixture
def temp_bundles_dir(tmp_path, monkeypatch):
    """Create temporary bundles directory for testing."""
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    monkeypatch.setattr("lib.change_bundles.BUNDLES_DIR", bundles_dir)
    return bundles_dir


# =============================================================================
# BUNDLE CREATION TESTS
# =============================================================================


class TestBundleCreation:
    """Tests for create_bundle function."""

    def test_create_simple_bundle(self, temp_bundles_dir):
        """Should create a bundle with basic info."""
        changes = [
            {
                "type": ChangeType.CREATE.value,
                "id": "task1",
                "target": "tasks",
                "data": {"title": "New Task"},
            }
        ]

        bundle = create_bundle(domain="tasks", description="Create new task", changes=changes)

        assert bundle["id"] is not None
        assert bundle["domain"] == "tasks"
        assert bundle["description"] == "Create new task"
        assert bundle["status"] == BundleStatus.PENDING.value
        assert bundle["created_at"] is not None
        assert bundle["changes"] == changes

    def test_bundle_id_unique(self, temp_bundles_dir):
        """Each bundle should have unique ID."""
        bundle1 = create_bundle("tasks", "desc1", [])
        bundle2 = create_bundle("tasks", "desc2", [])

        assert bundle1["id"] != bundle2["id"]

    def test_bundle_persisted_to_disk(self, temp_bundles_dir):
        """Bundle should be saved to disk."""
        bundle = create_bundle(domain="calendar", description="Create event", changes=[])

        bundle_file = temp_bundles_dir / f"{bundle['id']}.json"
        assert bundle_file.exists()

        # Verify content
        saved = json.loads(bundle_file.read_text())
        assert saved["id"] == bundle["id"]
        assert saved["domain"] == "calendar"

    def test_bundle_with_pre_images(self, temp_bundles_dir):
        """Should store pre-images for rollback."""
        pre_images = {"task1": {"title": "Old Title", "status": "open"}}

        bundle = create_bundle(
            domain="tasks", description="Update task", changes=[], pre_images=pre_images
        )

        assert bundle["pre_images"] == pre_images

    def test_bundle_initial_status_pending(self, temp_bundles_dir):
        """New bundle should be in PENDING status."""
        bundle = create_bundle("tasks", "desc", [])
        assert bundle["status"] == BundleStatus.PENDING.value
        assert bundle["applied_at"] is None
        assert bundle["rolled_back_at"] is None

    def test_bundle_without_pre_images_defaults_empty(self, temp_bundles_dir):
        """Bundle without pre_images should default to empty dict."""
        bundle = create_bundle("tasks", "desc", [])
        assert bundle["pre_images"] == {}

    def test_bundle_rollback_steps_generated(self, temp_bundles_dir):
        """Bundle should have rollback_steps generated."""
        changes = [
            {
                "type": ChangeType.CREATE.value,
                "id": "task1",
                "target": "tasks",
                "data": {"title": "New"},
            }
        ]

        bundle = create_bundle("tasks", "desc", changes)

        assert "rollback_steps" in bundle
        assert isinstance(bundle["rollback_steps"], list)


# =============================================================================
# ROLLBACK STEP GENERATION TESTS
# =============================================================================


class TestRollbackStepGeneration:
    """Tests for _generate_rollback_steps function."""

    def test_create_change_generates_delete_rollback(self):
        """CREATE change should generate DELETE rollback."""
        changes = [{"type": ChangeType.CREATE.value, "id": "task1", "target": "tasks"}]

        rollback = _generate_rollback_steps(changes, {})

        assert len(rollback) == 1
        assert rollback[0]["type"] == ChangeType.DELETE.value
        assert rollback[0]["id"] == "task1"

    def test_update_change_generates_restore_rollback(self):
        """UPDATE change should generate UPDATE rollback with pre-image."""
        pre_images = {"task1": {"title": "Old Title", "status": "open"}}

        changes = [
            {
                "type": ChangeType.UPDATE.value,
                "id": "task1",
                "target": "tasks",
                "data": {"title": "New Title"},
            }
        ]

        rollback = _generate_rollback_steps(changes, pre_images)

        assert len(rollback) == 1
        assert rollback[0]["type"] == ChangeType.UPDATE.value
        assert rollback[0]["data"] == pre_images["task1"]

    def test_delete_change_generates_recreate_rollback(self):
        """DELETE change should generate CREATE rollback with pre-image."""
        pre_images = {"task1": {"title": "Old Title"}}

        changes = [{"type": ChangeType.DELETE.value, "id": "task1", "target": "tasks"}]

        rollback = _generate_rollback_steps(changes, pre_images)

        assert len(rollback) == 1
        assert rollback[0]["type"] == ChangeType.CREATE.value
        assert rollback[0]["data"] == pre_images["task1"]

    def test_status_change_generates_restore_status_rollback(self):
        """STATUS_CHANGE should generate rollback restoring previous status."""
        pre_images = {"task1": {"status": "open"}}

        changes = [
            {
                "type": ChangeType.STATUS_CHANGE.value,
                "id": "task1",
                "target": "tasks",
                "data": {"status": "closed"},
            }
        ]

        rollback = _generate_rollback_steps(changes, pre_images)

        assert len(rollback) == 1
        assert rollback[0]["type"] == ChangeType.STATUS_CHANGE.value
        assert rollback[0]["data"]["status"] == "open"

    def test_multiple_changes_reversed_order(self):
        """Rollback steps should be in reverse order."""
        changes = [
            {"type": ChangeType.CREATE.value, "id": "task1", "target": "tasks"},
            {"type": ChangeType.CREATE.value, "id": "task2", "target": "tasks"},
        ]

        rollback = _generate_rollback_steps(changes, {})

        # Should be reversed - delete task2 before task1
        assert rollback[0]["id"] == "task2"
        assert rollback[1]["id"] == "task1"

    def test_missing_pre_image_skips_rollback_for_update(self):
        """UPDATE without pre-image should not generate rollback."""
        changes = [{"type": ChangeType.UPDATE.value, "id": "task1", "target": "tasks"}]

        rollback = _generate_rollback_steps(changes, {})

        # Should skip if pre-image missing
        assert len(rollback) == 0


# =============================================================================
# BUNDLE STATUS TRANSITION TESTS
# =============================================================================


class TestBundleStatusTransitions:
    """Tests for bundle status changes."""

    def test_mark_bundle_applied(self, temp_bundles_dir):
        """Should transition bundle to APPLIED."""
        bundle = create_bundle("tasks", "desc", [])
        bundle_id = bundle["id"]

        updated = mark_applied(bundle_id)

        assert updated["status"] == BundleStatus.APPLIED.value
        assert updated["applied_at"] is not None

    def test_mark_bundle_failed(self, temp_bundles_dir):
        """Should transition bundle to FAILED with error."""
        bundle = create_bundle("tasks", "desc", [])
        bundle_id = bundle["id"]

        error_msg = "Database connection timeout"
        updated = mark_failed(bundle_id, error_msg)

        assert updated["status"] == BundleStatus.FAILED.value
        assert updated["error"] == error_msg

    def test_marked_status_persisted_to_disk(self, temp_bundles_dir):
        """Status changes should persist to disk."""
        bundle = create_bundle("tasks", "desc", [])
        bundle_id = bundle["id"]

        mark_applied(bundle_id)

        # Reload from disk
        reloaded = get_bundle(bundle_id)
        assert reloaded["status"] == BundleStatus.APPLIED.value

    def test_mark_applied_sets_timestamp(self, temp_bundles_dir):
        """mark_applied should set applied_at timestamp."""
        bundle = create_bundle("tasks", "desc", [])
        updated = mark_applied(bundle["id"])

        assert updated["applied_at"] is not None
        # Should be valid ISO format
        datetime.fromisoformat(updated["applied_at"])

    def test_mark_failed_on_nonexistent_bundle_raises(self, temp_bundles_dir):
        """Marking nonexistent bundle should raise ValueError."""
        with pytest.raises(ValueError):
            mark_failed("nonexistent_id", "error")

    def test_mark_applied_on_nonexistent_bundle_raises(self, temp_bundles_dir):
        """Marking nonexistent bundle should raise ValueError."""
        with pytest.raises(ValueError):
            mark_applied("nonexistent_id")


# =============================================================================
# ROLLBACK TESTS
# =============================================================================


class TestBundleRollback:
    """Tests for rollback_bundle function."""

    def test_rollback_applied_bundle(self, temp_bundles_dir):
        """Should rollback an APPLIED bundle."""
        bundle = create_bundle("tasks", "desc", [])
        mark_applied(bundle["id"])

        rolled_back = rollback_bundle(bundle["id"])

        assert rolled_back["status"] == BundleStatus.ROLLED_BACK.value
        assert rolled_back["rolled_back_at"] is not None

    def test_rollback_sets_timestamp(self, temp_bundles_dir):
        """Rollback should set rolled_back_at timestamp."""
        bundle = create_bundle("tasks", "desc", [])
        mark_applied(bundle["id"])

        rolled_back = rollback_bundle(bundle["id"])

        assert rolled_back["rolled_back_at"] is not None
        datetime.fromisoformat(rolled_back["rolled_back_at"])

    def test_rollback_records_steps(self, temp_bundles_dir):
        """Rollback should record rollback steps attempted."""
        bundle = create_bundle(
            "tasks", "desc", [{"type": ChangeType.CREATE.value, "id": "task1", "target": "tasks"}]
        )
        mark_applied(bundle["id"])

        rolled_back = rollback_bundle(bundle["id"])

        assert "rollback_results" in rolled_back
        assert isinstance(rolled_back["rollback_results"], list)

    def test_rollback_on_pending_bundle_raises(self, temp_bundles_dir):
        """Cannot rollback PENDING bundle."""
        bundle = create_bundle("tasks", "desc", [])

        with pytest.raises(ValueError):
            rollback_bundle(bundle["id"])

    def test_rollback_on_failed_bundle_raises(self, temp_bundles_dir):
        """Cannot rollback FAILED bundle."""
        bundle = create_bundle("tasks", "desc", [])
        mark_failed(bundle["id"], "error")

        with pytest.raises(ValueError):
            rollback_bundle(bundle["id"])

    def test_rollback_on_nonexistent_bundle_raises(self, temp_bundles_dir):
        """Rollback nonexistent bundle should raise."""
        with pytest.raises(ValueError):
            rollback_bundle("nonexistent_id")


# =============================================================================
# BUNDLE RETRIEVAL TESTS
# =============================================================================


class TestGetBundle:
    """Tests for get_bundle function."""

    def test_get_existing_bundle(self, temp_bundles_dir):
        """Should retrieve existing bundle."""
        created = create_bundle("tasks", "desc", [])

        retrieved = get_bundle(created["id"])

        assert retrieved is not None
        assert retrieved["id"] == created["id"]

    def test_get_nonexistent_bundle_returns_none(self, temp_bundles_dir):
        """Should return None for nonexistent bundle."""
        result = get_bundle("nonexistent_id")
        assert result is None

    def test_get_corrupt_bundle_returns_none(self, temp_bundles_dir):
        """Should return None for corrupt bundle file."""
        bundle = create_bundle("tasks", "desc", [])
        bundle_file = temp_bundles_dir / f"{bundle['id']}.json"

        # Corrupt the file
        bundle_file.write_text("invalid json{")

        result = get_bundle(bundle["id"])
        assert result is None


# =============================================================================
# LIST BUNDLES TESTS
# =============================================================================


class TestListBundles:
    """Tests for list_bundles function."""

    def test_list_all_bundles(self, temp_bundles_dir):
        """Should list all bundles."""
        bundle1 = create_bundle("tasks", "desc1", [])
        bundle2 = create_bundle("calendar", "desc2", [])
        bundle3 = create_bundle("tasks", "desc3", [])

        bundles = list_bundles(limit=10)

        assert len(bundles) >= 3
        ids = [b["id"] for b in bundles]
        assert bundle1["id"] in ids
        assert bundle2["id"] in ids
        assert bundle3["id"] in ids

    def test_list_bundles_by_domain(self, temp_bundles_dir):
        """Should filter bundles by domain."""
        create_bundle("tasks", "desc1", [])
        create_bundle("calendar", "desc2", [])

        tasks_bundles = list_bundles(domain="tasks", limit=10)

        assert all(b["domain"] == "tasks" for b in tasks_bundles)

    def test_list_bundles_by_status(self, temp_bundles_dir):
        """Should filter bundles by status."""
        create_bundle("tasks", "desc1", [])
        bundle2 = create_bundle("tasks", "desc2", [])
        mark_applied(bundle2["id"])

        pending = list_bundles(status=BundleStatus.PENDING.value, limit=10)
        applied = list_bundles(status=BundleStatus.APPLIED.value, limit=10)

        assert len(pending) > 0
        assert len(applied) > 0
        assert all(b["status"] == BundleStatus.PENDING.value for b in pending)
        assert all(b["status"] == BundleStatus.APPLIED.value for b in applied)

    def test_list_bundles_respects_limit(self, temp_bundles_dir):
        """Should respect limit parameter."""
        for i in range(5):
            create_bundle("tasks", f"desc{i}", [])

        limited = list_bundles(limit=3)
        assert len(limited) <= 3

    def test_list_pending_bundles(self, temp_bundles_dir):
        """list_pending_bundles should return only PENDING bundles."""
        bundle1 = create_bundle("tasks", "desc1", [])
        bundle2 = create_bundle("tasks", "desc2", [])
        mark_applied(bundle2["id"])

        pending = list_pending_bundles()

        assert all(b["status"] == BundleStatus.PENDING.value for b in pending)
        ids = [b["id"] for b in pending]
        assert bundle1["id"] in ids
        assert bundle2["id"] not in ids

    def test_list_rollbackable_bundles(self, temp_bundles_dir):
        """list_rollbackable_bundles should return only APPLIED bundles."""
        bundle1 = create_bundle("tasks", "desc1", [])
        bundle2 = create_bundle("tasks", "desc2", [])
        mark_applied(bundle2["id"])

        rollbackable = list_rollbackable_bundles()

        assert all(b["status"] == BundleStatus.APPLIED.value for b in rollbackable)
        ids = [b["id"] for b in rollbackable]
        assert bundle1["id"] not in ids
        assert bundle2["id"] in ids


# =============================================================================
# CLEANUP TESTS
# =============================================================================


class TestCleanupOldBundles:
    """Tests for cleanup_old_bundles function."""

    def test_cleanup_removes_old_bundles(self, temp_bundles_dir):
        """Should remove bundles older than N days."""
        old_bundle = create_bundle("tasks", "old", [])
        new_bundle = create_bundle("tasks", "new", [])

        # Manually set old_bundle's created_at to past
        old_file = temp_bundles_dir / f"{old_bundle['id']}.json"
        old_data = json.loads(old_file.read_text())
        old_data["created_at"] = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        old_file.write_text(json.dumps(old_data))

        removed = cleanup_old_bundles(days=30)

        assert removed >= 1
        # Old bundle should be gone
        assert get_bundle(old_bundle["id"]) is None
        # New bundle should exist
        assert get_bundle(new_bundle["id"]) is not None

    def test_cleanup_keeps_recent_bundles(self, temp_bundles_dir):
        """Should not remove bundles newer than N days."""
        bundle = create_bundle("tasks", "new", [])

        cleanup_old_bundles(days=30)

        # Should still exist
        assert get_bundle(bundle["id"]) is not None


# =============================================================================
# DOMAIN-SPECIFIC BUNDLE HELPERS
# =============================================================================


class TestTaskBundle:
    """Tests for create_task_bundle helper."""

    def test_create_task_bundle_with_creates(self, temp_bundles_dir):
        """Should create task bundle with creates."""
        tasks = [{"id": "t1", "title": "New Task"}]

        bundle = create_task_bundle("Create tasks", creates=tasks)

        assert bundle["domain"] == "tasks"
        assert len(bundle["changes"]) == 1
        assert bundle["changes"][0]["type"] == ChangeType.CREATE.value

    def test_create_task_bundle_with_updates(self, temp_bundles_dir):
        """Should create task bundle with updates."""
        tasks = [{"id": "t1", "title": "Updated"}]

        bundle = create_task_bundle(
            "Update tasks", updates=tasks, pre_images={"t1": {"title": "Old"}}
        )

        assert len(bundle["changes"]) == 1
        assert bundle["changes"][0]["type"] == ChangeType.UPDATE.value

    def test_create_task_bundle_with_deletes(self, temp_bundles_dir):
        """Should create task bundle with deletes."""
        bundle = create_task_bundle(
            "Delete tasks", deletes=["t1", "t2"], pre_images={"t1": {}, "t2": {}}
        )

        assert len(bundle["changes"]) == 2
        assert all(c["type"] == ChangeType.DELETE.value for c in bundle["changes"])


class TestCalendarBundle:
    """Tests for create_calendar_bundle helper."""

    def test_create_calendar_bundle(self, temp_bundles_dir):
        """Should create calendar bundle."""
        events = [{"id": "e1", "title": "Meeting"}]

        bundle = create_calendar_bundle("Add events", creates=events)

        assert bundle["domain"] == "calendar"
        assert len(bundle["changes"]) == 1


class TestStatusChangeBundle:
    """Tests for create_status_change_bundle helper."""

    def test_create_status_change_bundle(self, temp_bundles_dir):
        """Should create status change bundle."""
        bundle = create_status_change_bundle(
            item_id="task1", old_status="open", new_status="closed", reason="Completed"
        )

        assert bundle["domain"] == "tasks"
        assert len(bundle["changes"]) == 1
        assert bundle["changes"][0]["type"] == ChangeType.STATUS_CHANGE.value
        assert bundle["pre_images"]["task1"]["status"] == "open"


# =============================================================================
# BUNDLE MANAGER TESTS
# =============================================================================


class TestBundleManager:
    """Tests for BundleManager class."""

    def test_bundle_manager_initialization(self, temp_bundles_dir):
        """Should initialize BundleManager."""
        manager = BundleManager()

        assert manager is not None
        assert hasattr(manager, "active_bundles")
        assert manager.active_bundles == {}

    def test_bundle_manager_start_bundle(self, temp_bundles_dir):
        """Should start and track a bundle."""
        manager = BundleManager()

        bundle_id = manager.start_bundle(
            cycle_id="cycle1", domain="tasks", description="Test bundle", changes=[]
        )

        assert bundle_id is not None
        assert "cycle1" in manager.active_bundles
        assert bundle_id in manager.active_bundles["cycle1"]

    def test_bundle_manager_apply_bundle(self, temp_bundles_dir):
        """Should apply a bundle."""
        manager = BundleManager()

        bundle_id = manager.start_bundle(
            cycle_id="cycle1", domain="tasks", description="Test", changes=[]
        )

        applied = manager.apply_bundle(bundle_id)

        assert applied["status"] == BundleStatus.APPLIED.value

    def test_bundle_manager_fail_bundle(self, temp_bundles_dir):
        """Should mark bundle as failed."""
        manager = BundleManager()

        bundle_id = manager.start_bundle(
            cycle_id="cycle1", domain="tasks", description="Test", changes=[]
        )

        failed = manager.fail_bundle(bundle_id, "DB error")

        assert failed["status"] == BundleStatus.FAILED.value
        assert failed["error"] == "DB error"

    def test_bundle_manager_rollback_cycle(self, temp_bundles_dir):
        """Should rollback all bundles from a cycle."""
        manager = BundleManager()

        bid1 = manager.start_bundle("cycle1", "tasks", "desc1", [])
        bid2 = manager.start_bundle("cycle1", "tasks", "desc2", [])

        manager.apply_bundle(bid1)
        manager.apply_bundle(bid2)

        result = manager.rollback_cycle("cycle1")

        assert result["cycle_id"] == "cycle1"
        assert result["bundles_processed"] == 2
        assert result["bundles_rolled_back"] >= 1

    def test_bundle_manager_rollback_nonexistent_cycle(self, temp_bundles_dir):
        """Should handle rollback of nonexistent cycle gracefully."""
        manager = BundleManager()

        result = manager.rollback_cycle("nonexistent")

        assert result["cycle_id"] == "nonexistent"
        assert result["bundles_processed"] == 0

    def test_bundle_manager_list_bundles_for_status(self, temp_bundles_dir):
        """Should list bundles filtered by status."""
        manager = BundleManager()

        bid1 = manager.start_bundle("cycle1", "tasks", "desc1", [])
        manager.start_bundle("cycle1", "tasks", "desc2", [])

        manager.apply_bundle(bid1)

        pending = manager.list_bundles_for_status(status=BundleStatus.PENDING.value)
        applied = manager.list_bundles_for_status(status=BundleStatus.APPLIED.value)

        assert len(pending) > 0
        assert len(applied) > 0

    def test_bundle_manager_list_bundles_with_since_filter(self, temp_bundles_dir):
        """Should filter bundles by creation timestamp."""
        manager = BundleManager()

        manager.start_bundle("cycle1", "tasks", "desc1", [])

        since = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        bundles = manager.list_bundles_for_status(since=since)

        assert len(bundles) > 0

    def test_bundle_manager_prune_bundles(self, temp_bundles_dir):
        """Should prune old bundles."""
        manager = BundleManager()

        manager.start_bundle("cycle1", "tasks", "desc1", [])

        removed = manager.prune_bundles(keep_days=30)

        # Should return count
        assert isinstance(removed, int)

    def test_bundle_manager_get_cycle_summary(self, temp_bundles_dir):
        """Should get summary of cycle bundles."""
        manager = BundleManager()

        bid1 = manager.start_bundle("cycle1", "tasks", "desc1", [])
        bid2 = manager.start_bundle("cycle1", "tasks", "desc2", [])

        manager.apply_bundle(bid1)
        manager.fail_bundle(bid2, "error")

        summary = manager.get_cycle_summary("cycle1")

        assert summary["cycle_id"] == "cycle1"
        assert summary["bundles_created"] == 2
        assert summary["bundles_applied"] == 1
        assert summary["bundles_failed"] == 1

    def test_bundle_manager_multiple_cycles(self, temp_bundles_dir):
        """Should handle multiple cycles independently."""
        manager = BundleManager()

        bid1 = manager.start_bundle("cycle1", "tasks", "desc1", [])
        bid2 = manager.start_bundle("cycle2", "tasks", "desc2", [])

        assert "cycle1" in manager.active_bundles
        assert "cycle2" in manager.active_bundles
        assert bid1 in manager.active_bundles["cycle1"]
        assert bid2 in manager.active_bundles["cycle2"]
