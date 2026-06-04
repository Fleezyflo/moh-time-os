"""Write-path migration tests for the 'truth' helper modules.

These modules routed UPDATE/DELETE statements through store.query() (a read-only
method once the StateStore guard lands). Each is migrated to store.execute_write().

Covered modules (write sites):
- lib/capacity_truth/debt_tracker.py        resolve_debt (1 UPDATE)
- lib/client_truth/linker.py                link_project_to_client (1 UPDATE), unlink_project (1 DELETE)
- lib/commitment_truth/commitment_manager.py  link/unlink/mark_done/mark_broken (4 UPDATE)
- lib/state_tracker.py                      mark_collected (1 UPDATE)
- lib/time_truth/block_manager.py           schedule_task (1 UPDATE), unschedule_task (1 UPDATE)

Each module gets a structural test (uses execute_write, no write-via-query) and a
behavioral test (the write persists on a real temp-DB StateStore). Tables are built
explicitly to match the columns each code path actually uses, so the behavioral tests
exercise the real SQL the daemon runs.
"""

import inspect
import tempfile
from pathlib import Path

import pytest

from lib.capacity_truth.debt_tracker import DebtTracker
from lib.client_truth.linker import ClientLinker
from lib.commitment_truth.commitment_manager import CommitmentManager
from lib.state_store import StateStore
from lib.time_truth.block_manager import BlockManager


@pytest.fixture
def store():
    """A real StateStore on a throwaway temp DB (tables created per-test)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = f.name
    StateStore._instance = None
    s = StateStore(db_file)
    yield s
    StateStore._instance = None
    Path(db_file).unlink(missing_ok=True)


# ----------------------------------------------------------------------------
# debt_tracker.resolve_debt
# ----------------------------------------------------------------------------


def test_S_resolve_debt_uses_execute_write():
    """[S] DebtTracker.resolve_debt writes via execute_write, not query()."""
    src = inspect.getsource(DebtTracker.resolve_debt)
    assert "execute_write" in src
    assert "UPDATE time_debt" in src
    assert 'query(\n            "UPDATE' not in src and 'query("UPDATE' not in src


def test_B_resolve_debt_persists(store):
    """[B] resolve_debt sets resolved_at on the row."""
    store.execute_write(
        "CREATE TABLE time_debt (id TEXT PRIMARY KEY, lane TEXT, amount_min INTEGER, "
        "reason TEXT, source_task_id TEXT, incurred_at TEXT, resolved_at TEXT)"
    )
    store.execute_write(
        "INSERT INTO time_debt (id, lane, amount_min, incurred_at, resolved_at) "
        "VALUES ('d1', 'ops', 30, datetime('now'), NULL)"
    )
    tracker = DebtTracker(store=store)
    ok, msg = tracker.resolve_debt("d1")
    assert ok is True, msg
    rows = store.query("SELECT resolved_at FROM time_debt WHERE id = 'd1'")
    assert rows[0]["resolved_at"] is not None


def test_B_resolve_debt_unknown_id(store):
    """[B] resolve_debt returns (False, ...) for a missing debt id."""
    store.execute_write(
        "CREATE TABLE time_debt (id TEXT PRIMARY KEY, lane TEXT, amount_min INTEGER, "
        "reason TEXT, source_task_id TEXT, incurred_at TEXT, resolved_at TEXT)"
    )
    tracker = DebtTracker(store=store)
    ok, _ = tracker.resolve_debt("nope")
    assert ok is False


# ----------------------------------------------------------------------------
# linker: link_project_to_client (UPDATE) + unlink_project (DELETE)
# ----------------------------------------------------------------------------


def test_S_linker_uses_execute_write():
    """[S] ClientLinker write methods use execute_write, not query()."""
    update_src = inspect.getsource(ClientLinker.link_project_to_client)
    delete_src = inspect.getsource(ClientLinker.unlink_project)
    assert "execute_write" in update_src
    assert "execute_write" in delete_src
    assert "UPDATE client_projects" in update_src
    assert "DELETE FROM client_projects" in delete_src


def _seed_linker(store):
    store.execute_write("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, client_id TEXT)")
    store.execute_write("CREATE TABLE clients (id TEXT PRIMARY KEY, name TEXT)")
    store.execute_write(
        "CREATE TABLE client_projects (client_id TEXT, project_id TEXT, linked_at TEXT)"
    )
    store.execute_write("INSERT INTO projects (id, name) VALUES ('p1', 'Acme Q1')")
    store.execute_write("INSERT INTO clients (id, name) VALUES ('c1', 'Acme')")
    store.execute_write("INSERT INTO clients (id, name) VALUES ('c2', 'Beta')")


def test_B_link_project_update_persists(store):
    """[B] Re-linking a project updates client_projects.client_id via execute_write."""
    _seed_linker(store)
    linker = ClientLinker(store=store)
    ok, _ = linker.link_project_to_client("p1", "c1")
    assert ok
    ok, msg = linker.link_project_to_client("p1", "c2")  # triggers the UPDATE branch
    assert ok, msg
    rows = store.query("SELECT client_id FROM client_projects WHERE project_id = 'p1'")
    assert len(rows) == 1
    assert rows[0]["client_id"] == "c2"


def test_B_unlink_project_delete_persists(store):
    """[B] unlink_project removes the client_projects row via execute_write."""
    _seed_linker(store)
    linker = ClientLinker(store=store)
    linker.link_project_to_client("p1", "c1")
    ok, _ = linker.unlink_project("p1")
    assert ok
    rows = store.query("SELECT * FROM client_projects WHERE project_id = 'p1'")
    assert rows == []


# ----------------------------------------------------------------------------
# commitment_manager: link / unlink / mark_done / mark_broken (4 UPDATEs)
# ----------------------------------------------------------------------------


def test_S_commitment_manager_uses_execute_write():
    """[S] All four commitment state-change methods use execute_write."""
    for method in (
        CommitmentManager.link_commitment_to_task,
        CommitmentManager.unlink_commitment,
        CommitmentManager.mark_done,
        CommitmentManager.mark_broken,
    ):
        src = inspect.getsource(method)
        assert "execute_write" in src, f"{method.__name__} must use execute_write"
        assert "UPDATE commitments" in src
        assert 'query(\n            "UPDATE' not in src


def _seed_commitments(store):
    # Match the LIVE daemon DB commitments shape (commitment_id PK), which is the
    # schema the commitment_manager SQL is written for (it diverges from the
    # canonical fixture schema — see VERIFICATION_LOG note).
    store.execute_write(
        "CREATE TABLE commitments ("
        "commitment_id TEXT PRIMARY KEY, scope_ref_type TEXT, scope_ref_id TEXT, "
        "commitment_text TEXT, due_at TEXT, status TEXT DEFAULT 'open', "
        "task_id TEXT, created_at TEXT, updated_at TEXT)"
    )
    store.execute_write("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT)")
    store.execute_write("INSERT INTO tasks (id, title) VALUES ('t1', 'Do it')")
    store.execute_write(
        "INSERT INTO commitments (commitment_id, status, task_id, created_at) "
        "VALUES ('cm1', 'open', NULL, datetime('now'))"
    )


def test_B_link_commitment_persists(store):
    """[B] link_commitment_to_task sets task_id + status='linked'."""
    _seed_commitments(store)
    mgr = CommitmentManager(store=store)
    ok, msg = mgr.link_commitment_to_task("cm1", "t1")
    assert ok, msg
    rows = store.query("SELECT task_id, status FROM commitments WHERE commitment_id = 'cm1'")
    assert rows[0]["task_id"] == "t1"
    assert rows[0]["status"] == "linked"


def test_B_unlink_commitment_persists(store):
    """[B] unlink_commitment clears task_id + status='open'."""
    _seed_commitments(store)
    mgr = CommitmentManager(store=store)
    mgr.link_commitment_to_task("cm1", "t1")
    ok, _ = mgr.unlink_commitment("cm1")
    assert ok
    rows = store.query("SELECT task_id, status FROM commitments WHERE commitment_id = 'cm1'")
    assert rows[0]["task_id"] is None
    assert rows[0]["status"] == "open"


def test_B_mark_done_and_broken_persist(store):
    """[B] mark_done and mark_broken update status."""
    _seed_commitments(store)
    mgr = CommitmentManager(store=store)
    ok, _ = mgr.mark_done("cm1")
    assert ok
    assert (
        store.query("SELECT status FROM commitments WHERE commitment_id = 'cm1'")[0]["status"]
        == "done"
    )
    ok, _ = mgr.mark_broken("cm1")
    assert ok
    assert (
        store.query("SELECT status FROM commitments WHERE commitment_id = 'cm1'")[0]["status"]
        == "broken"
    )


# ----------------------------------------------------------------------------
# state_tracker.mark_collected
# ----------------------------------------------------------------------------


def test_S_mark_collected_uses_execute_write():
    """[S] state_tracker.mark_collected writes via execute_write, not query()."""
    from lib import state_tracker

    src = inspect.getsource(state_tracker.mark_collected)
    assert "execute_write" in src
    assert "UPDATE sync_state" in src
    assert 'query(\n        "UPDATE' not in src


def test_B_mark_collected_persists(store, monkeypatch):
    """[B] mark_collected updates only last_sync, leaving other columns intact."""
    from lib import state_tracker

    store.execute_write(
        "CREATE TABLE sync_state (source TEXT PRIMARY KEY, last_sync TEXT, "
        "last_success TEXT, items_synced INTEGER, error TEXT, error_type TEXT, status TEXT)"
    )
    store.execute_write(
        "INSERT INTO sync_state (source, last_sync, items_synced, status) "
        "VALUES ('asana', '2020-01-01T00:00:00', 7, 'success')"
    )
    # mark_collected resolves the store via module-level get_store()
    monkeypatch.setattr(state_tracker, "get_store", lambda: store)
    state_tracker.mark_collected("asana")
    rows = store.query(
        "SELECT last_sync, items_synced, status FROM sync_state WHERE source = 'asana'"
    )
    assert rows[0]["last_sync"] != "2020-01-01T00:00:00"  # updated
    assert rows[0]["items_synced"] == 7  # untouched
    assert rows[0]["status"] == "success"  # untouched


# ----------------------------------------------------------------------------
# block_manager: schedule_task + unschedule_task (2 UPDATEs)
# ----------------------------------------------------------------------------


def test_S_block_manager_uses_execute_write():
    """[S] BlockManager schedule/unschedule write via execute_write, not query()."""
    sched = inspect.getsource(BlockManager.schedule_task)
    unsched = inspect.getsource(BlockManager.unschedule_task)
    assert "execute_write" in sched
    assert "execute_write" in unsched
    assert "UPDATE time_blocks" in sched
    assert "UPDATE time_blocks" in unsched
    assert 'query(\n            "UPDATE' not in sched
    assert 'query(\n            "UPDATE' not in unsched


def _seed_blocks(store):
    store.execute_write(
        "CREATE TABLE time_blocks (id TEXT PRIMARY KEY, date TEXT, start_time TEXT, "
        "end_time TEXT, lane TEXT, task_id TEXT, is_protected INTEGER DEFAULT 0, "
        "is_buffer INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)"
    )
    store.execute_write(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, lane TEXT, "
        "scheduled_block_id TEXT, updated_at TEXT)"
    )
    store.execute_write(
        "INSERT INTO time_blocks (id, date, start_time, end_time, lane) "
        "VALUES ('b1', '2026-06-04', '09:00', '10:00', 'ops')"
    )
    store.execute_write("INSERT INTO tasks (id, title, lane) VALUES ('t1', 'Task', 'ops')")


def test_B_schedule_task_persists(store):
    """[B] schedule_task sets time_blocks.task_id via execute_write."""
    _seed_blocks(store)
    bm = BlockManager(store=store)
    ok, msg = bm.schedule_task("t1", "b1")  # signature is (task_id, block_id)
    assert ok, msg
    rows = store.query("SELECT task_id FROM time_blocks WHERE id = 'b1'")
    assert rows[0]["task_id"] == "t1"


def test_B_unschedule_task_persists(store):
    """[B] unschedule_task clears time_blocks.task_id via execute_write."""
    _seed_blocks(store)
    bm = BlockManager(store=store)
    bm.schedule_task("t1", "b1")  # signature is (task_id, block_id)
    ok, _ = bm.unschedule_task("t1")
    assert ok
    rows = store.query("SELECT task_id FROM time_blocks WHERE id = 'b1'")
    assert rows[0]["task_id"] is None
