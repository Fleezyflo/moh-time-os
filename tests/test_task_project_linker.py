"""Tests for task-project linker.

The linker routes all DB access through the ``StateStore`` singleton
(lib/state_store.py:94-101). ``StateStore.__init__`` early-returns on
``self._initialized`` (line 104-105), so the ``db_path`` passed to a *second*
construction is ignored — the singleton stays bound to whichever DB it first saw.

Because of that, these tests must NOT pass a bare ``db_path`` string positionally
to the linker functions: in a full-file run the first test binds the singleton and
every later call silently writes to that first DB instead of the per-test fixture
DB. Instead each test drives the linker via an explicit ``store=`` bound to its own
temp DB (singleton reset first) and inspects results through that same store —
mirroring the working pattern in tests/test_audit_remediation_v3_behavioral.py
(``_fresh_store``, lines 30-34).
"""

import os
import sqlite3
import tempfile

import pytest

from lib.state_store import StateStore
from lib.task_project_linker import (
    cascade_client_ids,
    link_all,
    link_by_asana_gid,
    link_by_map,
    link_by_name,
)


@pytest.fixture
def store():
    """StateStore bound to a fresh temp DB seeded with tasks/projects/map.

    Yields a StateStore (not a path) so callers pass ``store=`` to the linker and
    read back through the same store — the linker and the assertions then target
    the same DB regardless of singleton run-order.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    # Reset the singleton and bind a fresh store to this test's DB. Construction
    # runs ensure_migrations() on the empty file; it does NOT create the
    # projects/tasks/asana_project_map tables, so the seed below is collision-free.
    StateStore._instance = None
    s = StateStore(tmp.name)

    conn = sqlite3.connect(tmp.name)
    conn.executescript("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            name_normalized TEXT,
            client_id TEXT,
            asana_project_id TEXT
        );

        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            project TEXT,
            project_id TEXT,
            project_link_status TEXT DEFAULT 'unlinked',
            client_id TEXT,
            source TEXT,
            source_id TEXT,
            updated_at TEXT
        );

        CREATE TABLE asana_project_map (
            asana_gid TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            asana_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Projects
        INSERT INTO projects VALUES ('p1', 'Website Build', 'website-build', 'c1', 'asana_gid_1');
        INSERT INTO projects VALUES ('p2', 'App Design', 'app-design', 'c2', 'asana_gid_2');
        INSERT INTO projects VALUES ('p3', 'Internal Ops', 'internal-ops', 'c3', NULL);

        -- Orphaned tasks
        INSERT INTO tasks VALUES ('t1', 'Fix header', 'Website Build', NULL, 'unlinked', NULL, 'asana', 's1', '');
        INSERT INTO tasks VALUES ('t2', 'Design logo', 'App Design', NULL, 'unlinked', NULL, 'asana', 's2', '');
        INSERT INTO tasks VALUES ('t3', 'Update docs', 'Internal Ops', NULL, 'unlinked', NULL, 'manual', 's3', '');
        INSERT INTO tasks VALUES ('t4', 'Random task', 'Unknown Project', NULL, 'unlinked', NULL, 'asana', 's4', '');

        -- Task already linked (should not be touched)
        INSERT INTO tasks VALUES ('t5', 'Linked task', 'Website Build', 'p1', 'linked', 'c1', 'asana', 's5', '');

        -- Task with project_id but no client_id
        INSERT INTO tasks VALUES ('t6', 'No client', 'Website Build', 'p1', 'linked', NULL, 'asana', 's6', '');

        -- Project map
        INSERT INTO asana_project_map (asana_gid, project_id, asana_name) VALUES ('asana_gid_1', 'p1', 'Mapped Project');
        INSERT INTO tasks VALUES ('t7', 'Mapped task', 'Mapped Project', NULL, 'unlinked', NULL, 'asana', 's7', '');
    """)
    conn.commit()
    conn.close()

    try:
        yield s
    finally:
        StateStore._instance = None
        os.unlink(tmp.name)


class TestLinkByAsanaGid:
    def test_links_asana_tasks_by_name(self, store):
        count = link_by_asana_gid(store=store)
        assert count >= 1  # t1 and t2 should match

    def test_dry_run_no_changes(self, store):
        link_by_asana_gid(dry_run=True, store=store)
        unlinked = store.query("SELECT COUNT(*) AS c FROM tasks WHERE project_id IS NULL")[0]["c"]
        assert unlinked == 5  # All still unlinked


class TestLinkByMap:
    def test_links_via_map(self, store):
        count = link_by_map(store=store)
        assert count >= 1  # t7 should match via map


class TestLinkByName:
    def test_links_by_name(self, store):
        count = link_by_name(store=store)
        assert count >= 1  # t3 should match (non-asana source)


class TestCascadeClientIds:
    def test_cascades_client_id(self, store):
        count = cascade_client_ids(store=store)
        assert count >= 1  # t6 should get client_id from p1

    def test_correct_client_id(self, store):
        cascade_client_ids(store=store)
        row = store.query("SELECT client_id FROM tasks WHERE id = 't6'")
        assert row[0]["client_id"] == "c1"


class TestLinkAll:
    def test_link_all_runs_all_strategies(self, store):
        result = link_all(store=store)
        assert result["tasks_linked_after"] > result["tasks_linked_before"]

    def test_link_all_dry_run(self, store):
        result = link_all(dry_run=True, store=store)
        assert result["dry_run"] is True
        assert result["tasks_linked_after"] == result["tasks_linked_before"]

    def test_unmatched_tasks_stay_unlinked(self, store):
        link_all(store=store)
        row = store.query("SELECT project_id FROM tasks WHERE id = 't4'")
        assert row[0]["project_id"] is None  # 'Unknown Project' has no match
