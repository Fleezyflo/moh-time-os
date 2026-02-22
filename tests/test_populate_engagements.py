"""Tests for engagement population migration."""

import sqlite3
import tempfile

import pytest

from lib.migrations.populate_engagements import populate_engagements


@pytest.fixture
def test_db():
    """Create test DB with projects and empty engagements tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name)

    conn.executescript("""
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name TEXT
        );

        CREATE TABLE engagements (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            brand_id TEXT,
            name TEXT,
            type TEXT,
            state TEXT,
            asana_project_gid TEXT,
            asana_url TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            client_id TEXT,
            brand_id TEXT,
            engagement_type TEXT,
            status TEXT,
            asana_project_id TEXT,
            start_date TEXT
        );

        INSERT INTO clients VALUES ('c1', 'Client A');
        INSERT INTO clients VALUES ('c2', 'Client B');

        -- Regular projects
        INSERT INTO projects VALUES ('p1', 'Website Build', 'c1', NULL, 'project', 'active', 'asana1', '2025-01-01');
        INSERT INTO projects VALUES ('p2', 'App Design', 'c1', 'b1', 'project', 'active', 'asana2', '2025-02-01');
        INSERT INTO projects VALUES ('p3', 'Campaign X', 'c2', NULL, 'campaign', 'active', 'asana3', '2025-03-01');

        -- Retainer projects (same client+brand = grouped)
        INSERT INTO projects VALUES ('p4', 'Monthly Design', 'c2', 'b2', 'retainer', 'active', 'asana4', '2025-01-01');
        INSERT INTO projects VALUES ('p5', 'Monthly Dev', 'c2', 'b2', 'retainer', 'active', 'asana5', '2025-02-01');

        -- Retainer for different client
        INSERT INTO projects VALUES ('p6', 'Support Plan', 'c1', NULL, 'retainer', 'active', 'asana6', '2025-04-01');
    """)

    conn.commit()
    conn.close()
    return tmp.name


class TestPopulateEngagements:
    """Tests for the populate_engagements migration."""

    def test_creates_engagements(self, test_db):
        result = populate_engagements(test_db)
        assert result["engagements_created"] > 0

    def test_all_projects_linked(self, test_db):
        result = populate_engagements(test_db)
        assert result["projects_unlinked"] == 0

    def test_project_count_correct(self, test_db):
        result = populate_engagements(test_db)
        assert result["projects_linked"] == 6

    def test_retainers_grouped(self, test_db):
        populate_engagements(test_db)
        # p4 and p5 should be in one retainer engagement (same client+brand)
        # p6 is a separate retainer (different client)
        conn = sqlite3.connect(test_db)
        retainers = conn.execute(
            "SELECT COUNT(*) FROM engagements WHERE type = 'retainer'"
        ).fetchone()[0]
        conn.close()
        assert retainers == 2  # c2+b2 group and c1+NULL group

    def test_campaigns_mapped_to_project_type(self, test_db):
        populate_engagements(test_db)
        conn = sqlite3.connect(test_db)
        # Campaign should be mapped to 'project' type
        p3_eid = conn.execute("SELECT engagement_id FROM projects WHERE id = 'p3'").fetchone()[0]
        eng_type = conn.execute("SELECT type FROM engagements WHERE id = ?", (p3_eid,)).fetchone()[
            0
        ]
        conn.close()
        assert eng_type == "project"

    def test_type_distribution(self, test_db):
        result = populate_engagements(test_db)
        dist = result["type_distribution"]
        assert dist["project"] == 3  # p1, p2, p3 (campaign)
        assert dist["retainer"] == 2  # 2 retainer groups

    def test_idempotent(self, test_db):
        """Running twice should produce the same result."""
        result1 = populate_engagements(test_db)
        result2 = populate_engagements(test_db)
        assert result1["engagements_created"] == result2["engagements_created"]
        assert result1["projects_linked"] == result2["projects_linked"]

    def test_engagement_id_column_added(self, test_db):
        """engagement_id column should be added to projects if missing."""
        populate_engagements(test_db)
        conn = sqlite3.connect(test_db)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
        conn.close()
        assert "engagement_id" in cols

    def test_state_mapping(self, test_db):
        populate_engagements(test_db)
        conn = sqlite3.connect(test_db)
        states = conn.execute("SELECT state, COUNT(*) FROM engagements GROUP BY state").fetchall()
        conn.close()
        # All test projects are 'active'
        state_dict = dict(states)
        assert state_dict.get("active", 0) == 5
