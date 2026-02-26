"""
Tests for expanded Asana Collector (CS-3.1).

Tests the ~90% API coverage implementation including:
- Custom fields collection and transformation
- Subtasks collection and transformation
- Stories (comments) collection and transformation
- Dependencies collection and transformation
- Attachments collection and transformation
- Portfolios and goals collection
- Multi-table storage in sync()

All tests use mocks - NO live API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.asana import AsanaCollector
from lib.state_store import StateStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Mock StateStore for testing."""
    store = MagicMock(spec=StateStore)
    store.insert_many.return_value = 5  # Simulate inserting 5 rows
    return store


@pytest.fixture
def collector(mock_store):
    """Create an AsanaCollector with mocked store."""
    config = {"sync_interval": 300}
    collector = AsanaCollector(config=config, store=mock_store)
    return collector


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def mock_task_with_expanded_data():
    """Mock task with all expanded fields."""
    return {
        "gid": "task_123",
        "name": "Important Task",
        "completed": False,
        "completed_at": None,
        "due_on": "2026-02-28",
        "due_at": None,
        "assignee": {"gid": "user_1", "name": "John Doe"},
        "tags": [{"gid": "tag_1", "name": "urgent"}],
        "notes": "This is a task description",
        "created_at": "2026-02-01T10:00:00Z",
        "modified_at": "2026-02-21T15:30:00Z",
        "custom_fields": [
            {
                "gid": "cf_1",
                "name": "Priority",
                "type": "enum",
                "display_value": "High",
            },
            {
                "gid": "cf_2",
                "name": "Effort",
                "type": "number",
                "display_value": "5",
            },
        ],
        "memberships": [{"section": {"gid": "sec_1", "name": "In Progress"}}],
        "num_subtasks": 2,
        "_project_gid": "proj_1",
        "_project_name": "Main Project",
    }


@pytest.fixture
def mock_subtasks():
    """Mock subtasks data."""
    return [
        {
            "gid": "subtask_1",
            "name": "Subtask 1",
            "completed": False,
            "due_on": "2026-02-25",
            "assignee": {"gid": "user_1", "name": "John Doe"},
        },
        {
            "gid": "subtask_2",
            "name": "Subtask 2",
            "completed": True,
            "due_on": None,
            "assignee": None,
        },
    ]


@pytest.fixture
def mock_stories():
    """Mock stories/comments data."""
    return [
        {
            "gid": "story_1",
            "type": "comment",
            "text": "This is a comment",
            "created_by": {"gid": "user_1", "name": "John Doe"},
            "created_at": "2026-02-20T10:00:00Z",
        },
        {
            "gid": "story_2",
            "type": "system_comment",
            "text": "marked_complete",
            "created_by": None,
            "created_at": "2026-02-21T15:30:00Z",
        },
    ]


@pytest.fixture
def mock_dependencies():
    """Mock dependencies data."""
    return [
        {"gid": "task_456", "name": "Dependent Task 1", "completed": False},
        {"gid": "task_789", "name": "Dependent Task 2", "completed": False},
    ]


@pytest.fixture
def mock_attachments():
    """Mock attachments data."""
    return [
        {
            "gid": "att_1",
            "name": "document.pdf",
            "download_url": "https://example.com/file.pdf",
            "host": "dropbox",
            "size": 1024000,
        },
        {
            "gid": "att_2",
            "name": "image.jpg",
            "download_url": "https://example.com/image.jpg",
            "host": "google_drive",
            "size": 2048000,
        },
    ]


@pytest.fixture
def mock_portfolios():
    """Mock portfolios data."""
    return [
        {
            "gid": "port_1",
            "name": "Q1 Roadmap",
            "owner": {"gid": "user_1", "name": "John Doe"},
        },
        {
            "gid": "port_2",
            "name": "Q2 Roadmap",
            "owner": {"gid": "user_2", "name": "Jane Smith"},
        },
    ]


@pytest.fixture
def mock_goals():
    """Mock goals data."""
    return [
        {
            "gid": "goal_1",
            "name": "Launch new feature",
            "owner": {"gid": "user_1", "name": "John Doe"},
            "status": "in_progress",
            "due_on": "2026-03-31",
            "html_notes": "<p>This is a goal</p>",
        },
        {
            "gid": "goal_2",
            "name": "Improve performance",
            "owner": {"gid": "user_2", "name": "Jane Smith"},
            "status": "at_risk",
            "due_on": "2026-04-30",
            "html_notes": "<p>Another goal</p>",
        },
    ]


# =============================================================================
# CUSTOM FIELDS TRANSFORMATION TESTS
# =============================================================================


class TestTransformCustomFields:
    """Tests for _transform_custom_fields method."""

    def test_transform_enum_field(self, collector):
        """Should correctly transform enum custom field."""
        custom_fields = [
            {
                "gid": "cf_1",
                "name": "Priority",
                "type": "enum",
                "display_value": "High",
            }
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_cf_cf_1"
        assert row["task_id"] == "task_1"
        assert row["project_id"] == "proj_1"
        assert row["field_name"] == "Priority"
        assert row["field_type"] == "enum"
        assert row["enum_value"] == "High"
        assert row["text_value"] is None
        assert row["number_value"] is None
        assert row["date_value"] is None

    def test_transform_number_field(self, collector):
        """Should correctly transform number custom field."""
        custom_fields = [
            {
                "gid": "cf_2",
                "name": "Effort",
                "type": "number",
                "display_value": "5.5",
            }
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 1
        row = rows[0]
        assert row["field_type"] == "number"
        assert row["number_value"] == 5.5
        assert row["text_value"] is None

    def test_transform_text_field(self, collector):
        """Should correctly transform text custom field."""
        custom_fields = [
            {
                "gid": "cf_3",
                "name": "Notes",
                "type": "text",
                "display_value": "Some notes",
            }
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 1
        row = rows[0]
        assert row["field_type"] == "text"
        assert row["text_value"] == "Some notes"

    def test_transform_date_field(self, collector):
        """Should correctly transform date custom field."""
        custom_fields = [
            {
                "gid": "cf_4",
                "name": "Review Date",
                "type": "date",
                "display_value": "2026-03-15",
            }
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 1
        row = rows[0]
        assert row["field_type"] == "date"
        assert row["date_value"] == "2026-03-15"

    def test_transform_multiple_fields(self, collector):
        """Should correctly transform multiple custom fields."""
        custom_fields = [
            {"gid": "cf_1", "name": "Priority", "type": "enum", "display_value": "High"},
            {"gid": "cf_2", "name": "Effort", "type": "number", "display_value": "5"},
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 2

    def test_skip_invalid_fields(self, collector):
        """Should skip fields with missing gid."""
        custom_fields = [
            {"name": "Bad Field", "type": "text", "display_value": "value"},
            {"gid": "cf_1", "name": "Good Field", "type": "text", "display_value": "value"},
        ]

        rows = collector._transform_custom_fields("task_1", "proj_1", custom_fields)

        assert len(rows) == 1
        assert rows[0]["field_name"] == "Good Field"


# =============================================================================
# SUBTASKS TRANSFORMATION TESTS
# =============================================================================


class TestTransformSubtasks:
    """Tests for _transform_subtasks method."""

    def test_transform_subtask_with_assignee(self, collector):
        """Should correctly transform subtask with assignee."""
        subtasks = [
            {
                "gid": "st_1",
                "name": "Subtask 1",
                "completed": False,
                "due_on": "2026-02-25",
                "assignee": {"gid": "user_1", "name": "John Doe"},
            }
        ]

        rows = collector._transform_subtasks("task_1", subtasks)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_st_st_1"
        assert row["parent_task_id"] == "task_1"
        assert row["name"] == "Subtask 1"
        assert row["completed"] == 0
        assert row["due_on"] == "2026-02-25"
        assert row["assignee_id"] == "user_1"
        assert row["assignee_name"] == "John Doe"

    def test_transform_completed_subtask(self, collector):
        """Should mark completed subtasks correctly."""
        subtasks = [
            {
                "gid": "st_2",
                "name": "Completed Subtask",
                "completed": True,
                "due_on": None,
                "assignee": None,
            }
        ]

        rows = collector._transform_subtasks("task_1", subtasks)

        assert len(rows) == 1
        assert rows[0]["completed"] == 1
        assert rows[0]["assignee_id"] is None
        assert rows[0]["assignee_name"] is None

    def test_transform_multiple_subtasks(self, collector, mock_subtasks):
        """Should transform multiple subtasks."""
        rows = collector._transform_subtasks("task_1", mock_subtasks)

        assert len(rows) == 2
        assert rows[0]["name"] == "Subtask 1"
        assert rows[1]["name"] == "Subtask 2"


# =============================================================================
# STORIES TRANSFORMATION TESTS
# =============================================================================


class TestTransformStories:
    """Tests for _transform_stories method."""

    def test_transform_comment_story(self, collector):
        """Should correctly transform comment story."""
        stories = [
            {
                "gid": "story_1",
                "type": "comment",
                "text": "This is a comment",
                "created_by": {"gid": "user_1", "name": "John Doe"},
                "created_at": "2026-02-20T10:00:00Z",
            }
        ]

        rows = collector._transform_stories("task_1", stories)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_story_story_1"
        assert row["task_id"] == "task_1"
        assert row["type"] == "comment"
        assert row["text"] == "This is a comment"
        assert row["created_by"] == "John Doe"
        assert row["created_at"] == "2026-02-20T10:00:00Z"

    def test_transform_system_story(self, collector):
        """Should correctly transform system event story."""
        stories = [
            {
                "gid": "story_2",
                "type": "system_comment",
                "text": "marked_complete",
                "created_by": None,
                "created_at": "2026-02-21T15:30:00Z",
            }
        ]

        rows = collector._transform_stories("task_1", stories)

        assert len(rows) == 1
        row = rows[0]
        assert row["type"] == "system_comment"
        assert row["text"] == "marked_complete"
        assert row["created_by"] is None

    def test_transform_multiple_stories(self, collector, mock_stories):
        """Should transform multiple stories."""
        rows = collector._transform_stories("task_1", mock_stories)

        assert len(rows) == 2


# =============================================================================
# DEPENDENCIES TRANSFORMATION TESTS
# =============================================================================


class TestTransformDependencies:
    """Tests for _transform_dependencies method."""

    def test_transform_dependency(self, collector):
        """Should correctly transform dependency."""
        dependencies = [{"gid": "task_456", "name": "Dependent Task", "completed": False}]

        rows = collector._transform_dependencies("task_1", dependencies)

        assert len(rows) == 1
        row = rows[0]
        assert row["task_id"] == "task_1"
        assert row["depends_on_task_id"] == "task_456"

    def test_transform_multiple_dependencies(self, collector, mock_dependencies):
        """Should transform multiple dependencies."""
        rows = collector._transform_dependencies("task_1", mock_dependencies)

        assert len(rows) == 2
        assert rows[0]["depends_on_task_id"] == "task_456"
        assert rows[1]["depends_on_task_id"] == "task_789"


# =============================================================================
# ATTACHMENTS TRANSFORMATION TESTS
# =============================================================================


class TestTransformAttachments:
    """Tests for _transform_attachments method."""

    def test_transform_attachment(self, collector):
        """Should correctly transform attachment."""
        attachments = [
            {
                "gid": "att_1",
                "name": "document.pdf",
                "download_url": "https://example.com/file.pdf",
                "host": "dropbox",
                "size": 1024000,
            }
        ]

        rows = collector._transform_attachments("task_1", attachments)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_att_att_1"
        assert row["task_id"] == "task_1"
        assert row["name"] == "document.pdf"
        assert row["download_url"] == "https://example.com/file.pdf"
        assert row["host"] == "dropbox"
        assert row["size_bytes"] == 1024000

    def test_transform_multiple_attachments(self, collector, mock_attachments):
        """Should transform multiple attachments."""
        rows = collector._transform_attachments("task_1", mock_attachments)

        assert len(rows) == 2


# =============================================================================
# PORTFOLIOS TRANSFORMATION TESTS
# =============================================================================


class TestTransformPortfolios:
    """Tests for _transform_portfolios method."""

    def test_transform_portfolio(self, collector):
        """Should correctly transform portfolio."""
        portfolios = [
            {
                "gid": "port_1",
                "name": "Q1 Roadmap",
                "owner": {"gid": "user_1", "name": "John Doe"},
            }
        ]

        rows = collector._transform_portfolios(portfolios)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_port_port_1"
        assert row["name"] == "Q1 Roadmap"
        assert row["owner_id"] == "user_1"
        assert row["owner_name"] == "John Doe"

    def test_transform_multiple_portfolios(self, collector, mock_portfolios):
        """Should transform multiple portfolios."""
        rows = collector._transform_portfolios(mock_portfolios)

        assert len(rows) == 2


# =============================================================================
# GOALS TRANSFORMATION TESTS
# =============================================================================


class TestTransformGoals:
    """Tests for _transform_goals method."""

    def test_transform_goal(self, collector):
        """Should correctly transform goal."""
        goals = [
            {
                "gid": "goal_1",
                "name": "Launch new feature",
                "owner": {"gid": "user_1", "name": "John Doe"},
                "status": "in_progress",
                "due_on": "2026-03-31",
                "html_notes": "<p>This is a goal</p>",
            }
        ]

        rows = collector._transform_goals(goals)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_goal_goal_1"
        assert row["name"] == "Launch new feature"
        assert row["owner_id"] == "user_1"
        assert row["owner_name"] == "John Doe"
        assert row["status"] == "in_progress"
        assert row["due_on"] == "2026-03-31"

    def test_transform_multiple_goals(self, collector, mock_goals):
        """Should transform multiple goals."""
        rows = collector._transform_goals(mock_goals)

        assert len(rows) == 2


# =============================================================================
# MAIN TRANSFORM METHOD TESTS
# =============================================================================


class TestMainTransform:
    """Tests for main transform method with expanded fields."""

    def test_transform_task_with_expanded_fields(self, collector, mock_task_with_expanded_data):
        """Should transform task with all expanded fields."""
        raw_data = {
            "tasks": [mock_task_with_expanded_data],
            "subtasks_by_parent": {"task_123": []},
            "stories_by_task": {},
            "dependencies_by_task": {},
            "attachments_by_task": {},
        }

        rows = collector.transform(raw_data)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "asana_task_123"
        assert row["source"] == "asana"
        assert row["title"] == "Important Task"
        assert row["section_id"] == "sec_1"
        assert row["section_name"] == "In Progress"
        assert row["subtask_count"] == 2
        assert row["custom_fields_json"] is not None

    def test_transform_includes_expanded_metadata(self, collector):
        """Should include expanded metadata in transformed tasks."""
        task = {
            "gid": "task_1",
            "name": "Task",
            "completed": False,
            "due_on": None,
            "assignee": None,
            "tags": [],
            "notes": "",
            "created_at": "2026-01-01T00:00:00Z",
            "modified_at": "2026-01-01T00:00:00Z",
            "custom_fields": [],
            "memberships": [],
            "num_subtasks": 0,
            "_project_name": "Test",
            "_project_gid": "proj_1",
        }

        raw_data = {
            "tasks": [task],
            "subtasks_by_parent": {},
            "stories_by_task": {"task_1": [{"gid": "s1"}]},
            "dependencies_by_task": {"task_1": [{"gid": "d1"}]},
            "attachments_by_task": {"task_1": [{"gid": "a1"}]},
        }

        rows = collector.transform(raw_data)

        assert len(rows) == 1
        row = rows[0]
        assert "section_id" in row
        assert "section_name" in row
        assert "subtask_count" in row
        assert "has_dependencies" in row
        assert row["has_dependencies"] == 1
        assert "attachment_count" in row
        assert row["attachment_count"] == 1
        assert "story_count" in row
        assert row["story_count"] == 1


# =============================================================================
# COLLECTION METHOD TESTS
# =============================================================================


class TestCollectionMethod:
    """Tests for collect method with expanded API calls."""

    @patch("engine.asana_client.list_projects")
    @patch("engine.asana_client.list_tasks_in_project")
    @patch("engine.asana_client.list_subtasks")
    @patch("engine.asana_client.list_stories")
    @patch("engine.asana_client.list_task_dependencies")
    @patch("engine.asana_client.list_task_attachments")
    @patch("engine.asana_client.list_portfolios")
    @patch("engine.asana_client.list_goals")
    def test_collect_pulls_expanded_data(
        self,
        mock_goals,
        mock_portfolios,
        mock_attachments,
        mock_dependencies,
        mock_stories,
        mock_subtasks,
        mock_tasks,
        mock_projects,
        collector,
    ):
        """Should pull all expanded data during collection."""
        # Setup mocks
        mock_projects.return_value = [{"gid": "proj_1", "name": "Project 1"}]
        mock_tasks.return_value = [
            {
                "gid": "task_1",
                "name": "Task 1",
                "num_subtasks": 1,
                "custom_fields": [],
                "memberships": [],
            }
        ]
        mock_subtasks.return_value = [{"gid": "st_1", "name": "Subtask"}]
        mock_stories.return_value = [{"gid": "story_1", "type": "comment"}]
        mock_dependencies.return_value = [{"gid": "task_2", "name": "Dep"}]
        mock_attachments.return_value = [{"gid": "att_1", "name": "file.pdf"}]
        mock_portfolios.return_value = [{"gid": "port_1", "name": "Portfolio"}]
        mock_goals.return_value = [{"gid": "goal_1", "name": "Goal"}]

        raw_data = collector.collect()

        # Verify structure
        assert "tasks" in raw_data
        assert "subtasks_by_parent" in raw_data
        assert "stories_by_task" in raw_data
        assert "dependencies_by_task" in raw_data
        assert "attachments_by_task" in raw_data
        assert "portfolios" in raw_data
        assert "goals" in raw_data

        # Verify counts
        assert len(raw_data["tasks"]) == 1
        assert "task_1" in raw_data["subtasks_by_parent"]
        assert "task_1" in raw_data["stories_by_task"]
        assert "task_1" in raw_data["dependencies_by_task"]
        assert "task_1" in raw_data["attachments_by_task"]
        assert len(raw_data["portfolios"]) == 1
        assert len(raw_data["goals"]) == 1

    @patch("engine.asana_client.list_projects")
    @patch("engine.asana_client.list_tasks_in_project")
    def test_collect_handles_subtask_pull_failures(self, mock_tasks, mock_projects, collector):
        """Should handle subtask pull failures gracefully."""
        mock_projects.return_value = [{"gid": "proj_1", "name": "Project"}]
        mock_tasks.return_value = [{"gid": "task_1", "name": "Task", "num_subtasks": 1}]

        with patch("engine.asana_client.list_subtasks") as mock_subtasks:
            mock_subtasks.side_effect = Exception("API error")
            raw_data = collector.collect()

            # Should still return task even if subtask pull fails
            assert len(raw_data["tasks"]) == 1
            assert "task_1" not in raw_data["subtasks_by_parent"]


# =============================================================================
# SYNC METHOD TESTS
# =============================================================================


class TestSyncMethod:
    """Tests for overridden sync method with multi-table storage."""

    @patch("engine.asana_client.list_projects")
    @patch("engine.asana_client.list_tasks_in_project")
    def test_sync_stores_to_multiple_tables(self, mock_tasks, mock_projects, collector, mock_store):
        """Should store data to multiple tables in sync."""
        mock_projects.return_value = [{"gid": "proj_1", "name": "Project"}]
        mock_tasks.return_value = [
            {
                "gid": "task_1",
                "name": "Task",
                "num_subtasks": 0,
                "completed": False,
                "due_on": None,
                "assignee": None,
                "tags": [],
                "notes": "",
                "created_at": "2026-01-01T00:00:00Z",
                "modified_at": "2026-01-01T00:00:00Z",
                "custom_fields": [
                    {"gid": "cf_1", "name": "Field", "type": "text", "display_value": "val"}
                ],
                "memberships": [],
            }
        ]

        result = collector.sync()

        # Should have successful sync
        assert result["success"] is True
        assert "collected" in result
        assert "transformed" in result
        assert "stored_tasks" in result
        assert "secondary_tables" in result

        # Verify store calls
        assert mock_store.insert_many.called

    @patch("engine.asana_client.list_projects")
    @patch("engine.asana_client.list_tasks_in_project")
    def test_sync_handles_secondary_table_failures_gracefully(
        self, mock_tasks, mock_projects, collector, mock_store
    ):
        """Should continue sync even if secondary table storage fails."""
        mock_projects.return_value = [{"gid": "proj_1", "name": "Project"}]
        mock_tasks.return_value = [
            {
                "gid": "task_1",
                "name": "Task",
                "num_subtasks": 0,
                "completed": False,
                "due_on": None,
                "assignee": None,
                "tags": [],
                "notes": "",
                "created_at": "2026-01-01T00:00:00Z",
                "modified_at": "2026-01-01T00:00:00Z",
                "custom_fields": [],
                "memberships": [],
            }
        ]

        # Make secondary table insert fail
        def side_effect(*args, **kwargs):
            if args[0] == "tasks":
                return 1
            raise Exception("Secondary table error")

        mock_store.insert_many.side_effect = side_effect

        result = collector.sync()

        # Should still succeed because tasks were stored
        assert result["success"] is True
