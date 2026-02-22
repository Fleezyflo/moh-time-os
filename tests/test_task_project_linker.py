"""Tests for task-project linker."""

import sqlite3
import tempfile

import pytest

from lib.task_project_linker import (
    cascade_client_ids,
    link_all,
    link_by_asana_gid,
    link_by_map,
    link_by_name,
)


@pytest.fixture
def test_db():
    """Create test DB with tasks, projects, and asana_project_map."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
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
    return tmp.name


class TestLinkByAsanaGid:
    def test_links_asana_tasks_by_name(self, test_db):
        count = link_by_asana_gid(test_db)
        assert count >= 1  # t1 and t2 should match

    def test_dry_run_no_changes(self, test_db):
        link_by_asana_gid(test_db, dry_run=True)
        conn = sqlite3.connect(test_db)
        unlinked = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id IS NULL").fetchone()[0]
        conn.close()
        assert unlinked == 5  # All still unlinked


class TestLinkByMap:
    def test_links_via_map(self, test_db):
        count = link_by_map(test_db)
        assert count >= 1  # t7 should match via map


class TestLinkByName:
    def test_links_by_name(self, test_db):
        count = link_by_name(test_db)
        assert count >= 1  # t3 should match (non-asana source)


class TestCascadeClientIds:
    def test_cascades_client_id(self, test_db):
        count = cascade_client_ids(test_db)
        assert count >= 1  # t6 should get client_id from p1

    def test_correct_client_id(self, test_db):
        cascade_client_ids(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT client_id FROM tasks WHERE id = 't6'").fetchone()
        conn.close()
        assert row[0] == "c1"


class TestLinkAll:
    def test_link_all_runs_all_strategies(self, test_db):
        result = link_all(test_db)
        assert result["tasks_linked_after"] > result["tasks_linked_before"]

    def test_link_all_dry_run(self, test_db):
        result = link_all(test_db, dry_run=True)
        assert result["dry_run"] is True
        assert result["tasks_linked_after"] == result["tasks_linked_before"]

    def test_unmatched_tasks_stay_unlinked(self, test_db):
        link_all(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT project_id FROM tasks WHERE id = 't4'").fetchone()
        conn.close()
        assert row[0] is None  # 'Unknown Project' has no match
