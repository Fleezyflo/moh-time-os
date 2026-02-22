"""Tests for capacity lane bootstrap."""

import sqlite3
import tempfile

import pytest

from lib.capacity_truth.lane_bootstrap import (
    assign_tasks_to_lanes,
    bootstrap_lanes,
    full_bootstrap,
    lane_load_report,
)


@pytest.fixture
def test_db():
    """Create test DB with capacity_lanes, team_members, and tasks tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name)

    conn.executescript("""
        CREATE TABLE capacity_lanes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            owner TEXT,
            weekly_hours INTEGER DEFAULT 40,
            buffer_pct REAL DEFAULT 0.2,
            color TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE team_members (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            asana_gid TEXT,
            default_lane TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE tasks (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            name TEXT,
            assignee TEXT,
            status TEXT DEFAULT 'active',
            due_date TEXT,
            project_name TEXT
        );

        -- Team members in different lanes
        INSERT INTO team_members (id, name, default_lane) VALUES
            ('tm1', 'Ahmed Salah', 'client'),
            ('tm2', 'Fady', 'client'),
            ('tm3', 'Molham Homsi', 'growth'),
            ('tm4', 'Sara Finance', 'finance'),
            ('tm5', 'No Lane Person', NULL);

        -- Tasks with various assignees
        INSERT INTO tasks (source_id, name, assignee, status) VALUES
            ('t1', 'Design homepage', 'Ahmed Salah', 'active'),
            ('t2', 'Fix bug', 'Ahmed Salah', 'overdue'),
            ('t3', 'Write copy', 'Fady', 'active'),
            ('t4', 'Strategy review', 'Molham Homsi', 'active'),
            ('t5', 'Budget report', 'Sara Finance', 'completed'),
            ('t6', 'Unassigned task', NULL, 'active'),
            ('t7', 'External person', 'Unknown Person', 'active');
    """)

    conn.commit()
    conn.close()
    return tmp.name


class TestBootstrapLanes:
    """Tests for lane creation."""

    def test_creates_lanes_from_team_members(self, test_db):
        result = bootstrap_lanes(test_db)
        assert result["created"] == 3  # client, growth, finance
        assert result["dry_run"] is False

    def test_growth_lane_has_custom_config(self, test_db):
        bootstrap_lanes(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT weekly_hours, buffer_pct FROM capacity_lanes WHERE name = 'growth'"
        ).fetchone()
        conn.close()
        assert row[0] == 45
        assert abs(row[1] - 0.15) < 0.01

    def test_client_lane_has_default_hours(self, test_db):
        bootstrap_lanes(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT weekly_hours FROM capacity_lanes WHERE name = 'client'"
        ).fetchone()
        conn.close()
        assert row[0] == 40

    def test_skips_existing_lanes(self, test_db):
        # Pre-insert a lane
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO capacity_lanes (id, name, display_name) VALUES ('lane_client', 'client', 'Existing')"
        )
        conn.commit()
        conn.close()

        result = bootstrap_lanes(test_db)
        assert result["skipped"] == 1  # client already exists
        assert result["created"] == 2  # growth, finance

    def test_dry_run_no_inserts(self, test_db):
        result = bootstrap_lanes(test_db, dry_run=True)
        assert result["dry_run"] is True
        assert result["created"] == 3

        conn = sqlite3.connect(test_db)
        count = conn.execute("SELECT COUNT(*) FROM capacity_lanes").fetchone()[0]
        conn.close()
        assert count == 0  # Nothing actually inserted

    def test_null_lanes_skipped(self, test_db):
        """Team members with NULL default_lane should not create lanes."""
        result = bootstrap_lanes(test_db)
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT COUNT(*) FROM capacity_lanes WHERE name IS NULL"
        ).fetchone()
        conn.close()
        assert row[0] == 0

    def test_idempotent(self, test_db):
        r1 = bootstrap_lanes(test_db)
        r2 = bootstrap_lanes(test_db)
        assert r1["created"] == 3
        assert r2["created"] == 0
        assert r2["skipped"] == 3


class TestAssignTasksToLanes:
    """Tests for task-to-lane assignment."""

    def test_assigns_matching_tasks(self, test_db):
        bootstrap_lanes(test_db)
        result = assign_tasks_to_lanes(test_db)
        assert result["assigned"] == 5  # t1,t2→client, t3→client, t4→growth, t5→finance

    def test_unmatched_tasks_counted(self, test_db):
        bootstrap_lanes(test_db)
        result = assign_tasks_to_lanes(test_db)
        assert result["unmatched"] == 1  # 'Unknown Person' not in team_members

    def test_creates_lane_id_column(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)

        conn = sqlite3.connect(test_db)
        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        conn.close()
        assert "lane_id" in columns

    def test_lane_id_set_correctly(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)

        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT lane_id FROM tasks WHERE source_id = 't4'"
        ).fetchone()
        conn.close()
        assert row[0] == "lane_growth"

    def test_dry_run_no_changes(self, test_db):
        bootstrap_lanes(test_db)
        result = assign_tasks_to_lanes(test_db, dry_run=True)
        assert result["dry_run"] is True

        # lane_id column should not exist
        conn = sqlite3.connect(test_db)
        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        conn.close()
        assert "lane_id" not in columns


class TestLaneLoadReport:
    """Tests for lane workload report."""

    def test_report_structure(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)
        report = lane_load_report(test_db)

        assert "lanes" in report
        assert "summary" in report
        assert report["summary"]["total_lanes"] == 3

    def test_client_lane_has_members(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)
        report = lane_load_report(test_db)

        client = next(l for l in report["lanes"] if l["name"] == "client")
        assert client["team_count"] == 2  # Ahmed + Fady
        assert client["total_tasks"] == 3  # t1, t2, t3

    def test_member_details_present(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)
        report = lane_load_report(test_db)

        client = next(l for l in report["lanes"] if l["name"] == "client")
        ahmed = next(m for m in client["members"] if m["name"] == "Ahmed Salah")
        assert ahmed["task_count"] == 2
        assert ahmed["overdue_count"] == 1  # t2 is overdue

    def test_overdue_counted_correctly(self, test_db):
        bootstrap_lanes(test_db)
        assign_tasks_to_lanes(test_db)
        report = lane_load_report(test_db)

        client = next(l for l in report["lanes"] if l["name"] == "client")
        assert client["overdue_tasks"] == 1  # Only t2


class TestFullBootstrap:
    """Tests for combined bootstrap."""

    def test_creates_lanes_and_assigns(self, test_db):
        result = full_bootstrap(test_db)
        assert result["lanes"]["created"] == 3
        assert result["assignments"]["assigned"] == 5
        assert result["dry_run"] is False
