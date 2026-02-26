"""
Tests for Asana write-back integration.

Tests AsanaWriter and AsanaSyncManager without calling real Asana API.
All HTTP calls are mocked using unittest.mock.
"""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from lib.integrations.asana_sync import AsanaSyncManager, SyncResult
from lib.integrations.asana_writer import AsanaWriter, AsanaWriteResult

# ============================================================
# AsanaWriter Tests
# ============================================================


class TestAsanaWriterInit:
    """Test AsanaWriter initialization."""

    def test_init_with_token_param(self):
        """Can initialize with explicit token."""
        writer = AsanaWriter(personal_access_token="test_token_123")
        assert writer.pat == "test_token_123"
        assert writer.dry_run is False

    def test_init_with_env_var(self, monkeypatch):
        """Can initialize with ASANA_PAT env var."""
        monkeypatch.setenv("ASANA_PAT", "env_token_456")
        writer = AsanaWriter()
        assert writer.pat == "env_token_456"

    def test_init_without_token_raises(self, monkeypatch):
        """Raises if no token provided."""
        monkeypatch.delenv("ASANA_PAT", raising=False)
        with pytest.raises(ValueError, match="No Asana PAT"):
            AsanaWriter()

    def test_init_dry_run_mode(self):
        """Can enable dry-run mode."""
        writer = AsanaWriter(personal_access_token="token", dry_run=True)
        assert writer.dry_run is True


class TestAsanaWriterCreateTask:
    """Test task creation."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_create_task_basic(self, mock_request):
        """Can create a basic task."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "gid": "task_123",
                "name": "Test Task",
                "notes": "",
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task(
            project_gid="proj_123",
            name="Test Task",
        )

        assert result.success
        assert result.gid == "task_123"
        assert result.http_status == 201
        mock_request.assert_called_once()

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_create_task_with_all_fields(self, mock_request):
        """Can create task with all optional fields."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "gid": "task_456",
                "name": "Full Task",
                "notes": "Task notes",
                "assignee": {"gid": "user_123"},
                "due_on": "2026-03-01",
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task(
            project_gid="proj_123",
            name="Full Task",
            notes="Task notes",
            assignee="user_123",
            due_on="2026-03-01",
            custom_fields={"field_1": "value_1"},
        )

        assert result.success
        assert result.gid == "task_456"

        # Verify request payload
        call_args = mock_request.call_args
        payload = call_args.kwargs["json"]
        assert payload["data"]["name"] == "Full Task"
        assert payload["data"]["notes"] == "Task notes"
        assert payload["data"]["assignee"] == "user_123"
        assert payload["data"]["due_on"] == "2026-03-01"
        assert payload["data"]["custom_fields"] == {"field_1": "value_1"}

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_create_task_api_error(self, mock_request):
        """Handles API errors correctly."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"errors": [{"message": "Invalid project"}]}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task(
            project_gid="invalid_proj",
            name="Test Task",
        )

        assert not result.success
        assert result.gid is None
        assert result.error is not None
        assert "400" in result.error

    def test_create_task_dry_run(self):
        """Dry-run mode validates without sending."""
        writer = AsanaWriter(personal_access_token="token", dry_run=True)
        result = writer.create_task(
            project_gid="proj_123",
            name="Test Task",
        )

        assert result.success
        assert result.data is not None
        assert result.data.get("dry_run") is True


class TestAsanaWriterUpdateTask:
    """Test task updates."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_update_task_name(self, mock_request):
        """Can update task name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "gid": "task_123",
                "name": "Updated Name",
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.update_task(
            task_gid="task_123",
            updates={"name": "Updated Name"},
        )

        assert result.success
        assert result.gid == "task_123"

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_update_task_multiple_fields(self, mock_request):
        """Can update multiple fields at once."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"gid": "task_123"}}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.update_task(
            task_gid="task_123",
            updates={
                "name": "New Name",
                "notes": "New notes",
                "completed": True,
                "due_on": "2026-03-15",
            },
        )

        assert result.success

        call_args = mock_request.call_args
        payload = call_args.kwargs["json"]
        assert payload["data"]["name"] == "New Name"
        assert payload["data"]["notes"] == "New notes"
        assert payload["data"]["completed"] is True
        assert payload["data"]["due_on"] == "2026-03-15"

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_update_task_empty_updates(self, mock_request):
        """Rejects empty update."""
        writer = AsanaWriter(personal_access_token="token")
        result = writer.update_task(
            task_gid="task_123",
            updates={},
        )

        assert not result.success
        assert "No valid fields" in result.error


class TestAsanaWriterCompleteTask:
    """Test task completion."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_complete_task(self, mock_request):
        """Can mark task as complete."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "gid": "task_123",
                "completed": True,
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.complete_task("task_123")

        assert result.success
        assert result.gid == "task_123"


class TestAsanaWriterComment:
    """Test adding comments."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_add_comment(self, mock_request):
        """Can add comment to task."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "gid": "story_123",
                "text": "Test comment",
                "type": "comment",
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.add_comment("task_123", "Test comment")

        assert result.success
        assert result.gid == "story_123"

        call_args = mock_request.call_args
        assert "tasks/task_123/stories" in call_args[0][1]


class TestAsanaWriterSubtask:
    """Test subtask creation."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_add_subtask(self, mock_request):
        """Can create subtask."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "gid": "subtask_123",
                "name": "Subtask",
            }
        }
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.add_subtask("parent_123", "Subtask")

        assert result.success
        assert result.gid == "subtask_123"

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_add_subtask_with_assignee(self, mock_request):
        """Can create subtask with assignee."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": {"gid": "subtask_456"}}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.add_subtask(
            "parent_123",
            "Subtask",
            assignee="user_456",
        )

        assert result.success

        call_args = mock_request.call_args
        payload = call_args.kwargs["json"]
        assert payload["data"]["assignee"] == "user_456"


class TestAsanaWriterTag:
    """Test tag operations."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_add_tag(self, mock_request):
        """Can add tag to task."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"gid": "task_123"}}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.add_tag("task_123", "tag_456")

        assert result.success

        call_args = mock_request.call_args
        assert "tasks/task_123/addTag" in call_args[0][1]


class TestAsanaWriterFollower:
    """Test follower operations."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_add_follower(self, mock_request):
        """Can add follower to task."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"gid": "task_123"}}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.add_follower("task_123", "user_789")

        assert result.success


class TestAsanaWriterRateLimit:
    """Test rate limit handling."""

    @patch("lib.integrations.asana_writer.httpx.request")
    @patch("lib.integrations.asana_writer.time.sleep")
    def test_rate_limit_retry(self, mock_sleep, mock_request):
        """Handles 429 rate limit with retry."""
        # First call returns 429, second returns 201
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "2"}

        success_response = Mock()
        success_response.status_code = 201
        success_response.json.return_value = {"data": {"gid": "task_123"}}

        mock_request.side_effect = [rate_limit_response, success_response]

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("proj_123", "Test")

        assert result.success
        assert result.gid == "task_123"
        mock_sleep.assert_called_once_with(2)

    @patch("lib.integrations.asana_writer.httpx.request")
    @patch("lib.integrations.asana_writer.time.sleep")
    def test_rate_limit_failure_after_retry(self, mock_sleep, mock_request):
        """Fails if rate limit persists after retry."""
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}
        # Need to support .text for error handling
        rate_limit_response.text = "Too Many Requests"

        mock_request.side_effect = [
            rate_limit_response,
            rate_limit_response,
        ]

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("proj_123", "Test")

        assert not result.success
        assert result.http_status == 429


class TestAsanaWriterErrors:
    """Test error handling."""

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_401_unauthorized(self, mock_request):
        """Handles 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"message": "Invalid token"}]}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="invalid_token")
        result = writer.create_task("proj_123", "Test")

        assert not result.success
        assert result.http_status == 401

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_403_forbidden(self, mock_request):
        """Handles 403 Forbidden."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"errors": [{"message": "Access denied"}]}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("proj_123", "Test")

        assert not result.success
        assert result.http_status == 403

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_404_not_found(self, mock_request):
        """Handles 404 Not Found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"errors": [{"message": "Project not found"}]}
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("invalid_proj", "Test")

        assert not result.success
        assert result.http_status == 404

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_500_server_error(self, mock_request):
        """Handles 500 Server Error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_request.return_value = mock_response

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("proj_123", "Test")

        assert not result.success
        assert result.http_status == 500

    @patch("lib.integrations.asana_writer.httpx.request")
    def test_network_error(self, mock_request):
        """Handles network errors."""
        mock_request.side_effect = Exception("Network error")

        writer = AsanaWriter(personal_access_token="token")
        result = writer.create_task("proj_123", "Test")

        assert not result.success
        assert "Network error" in result.error


# ============================================================
# AsanaSyncManager Tests - focused on integration
# ============================================================


class TestAsanaSyncManagerInit:
    """Test sync manager initialization."""

    def test_init_with_writer(self):
        """Can initialize with explicit writer."""
        mock_writer = MagicMock(spec=AsanaWriter)
        manager = AsanaSyncManager(writer=mock_writer)
        assert manager.writer == mock_writer

    def test_init_without_writer(self):
        """Can initialize without writer (creates from env)."""
        with patch.dict(os.environ, {"ASANA_PAT": "test_token"}):
            manager = AsanaSyncManager()
            assert isinstance(manager.writer, AsanaWriter)


class TestAsanaSyncManagerMappingTable:
    """Test mapping table creation and operations."""

    @patch("lib.integrations.asana_sync.get_connection")
    def test_ensure_mapping_table_created(self, mock_get_conn):
        """Creates mapping table if missing."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_writer = MagicMock(spec=AsanaWriter)
        manager = AsanaSyncManager(writer=mock_writer)
        manager._ensure_mapping_table()

        # Verify CREATE TABLE was called
        mock_cursor.execute.assert_called_once()
        call_sql = mock_cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS asana_task_mappings" in call_sql

    @patch("lib.integrations.asana_sync.get_connection")
    def test_save_and_retrieve_mapping(self, mock_get_conn):
        """Can save and retrieve task mappings."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Set up mock to return mapping on get_mapping call
        mock_cursor.fetchone.return_value = ("asana_456", "proj_789", None)

        mock_writer = MagicMock(spec=AsanaWriter)
        manager = AsanaSyncManager(writer=mock_writer)

        # Save mapping
        success = manager._save_mapping(
            local_id="task_123",
            asana_gid="asana_456",
            project_gid="proj_789",
        )
        assert success
        assert mock_cursor.execute.called

        # Get mapping
        mapping = manager._get_mapping("task_123")
        assert mapping is not None
        assert mapping["asana_gid"] == "asana_456"


class TestAsanaSyncCompletion:
    """Test sync_completion method."""

    @patch("lib.integrations.asana_sync.get_connection")
    def test_complete_task_in_asana(self, mock_get_conn):
        """Can complete a mapped task in Asana."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("asana_456", "proj_789", None)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_writer = MagicMock(spec=AsanaWriter)
        mock_writer.complete_task.return_value = AsanaWriteResult(
            success=True,
            gid="asana_456",
        )

        manager = AsanaSyncManager(writer=mock_writer)
        result = manager.sync_completion("local_123")

        assert result.success
        assert result.action == "complete"
        mock_writer.complete_task.assert_called_once_with("asana_456")

    @patch("lib.integrations.asana_sync.get_connection")
    def test_complete_unmapped_task_fails(self, mock_get_conn):
        """Fails when task not mapped."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_writer = MagicMock(spec=AsanaWriter)
        manager = AsanaSyncManager(writer=mock_writer)

        result = manager.sync_completion("unmapped_123")

        assert not result.success
        assert "No Asana mapping" in result.error


class TestAsanaSyncComment:
    """Test post_status_comment method."""

    @patch("lib.integrations.asana_sync.get_connection")
    def test_post_comment_to_task(self, mock_get_conn):
        """Can post comment to mapped task."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("asana_456", "proj_789", None)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_writer = MagicMock(spec=AsanaWriter)
        mock_writer.add_comment.return_value = AsanaWriteResult(
            success=True,
            gid="story_789",
        )

        manager = AsanaSyncManager(writer=mock_writer)
        result = manager.post_status_comment("local_123", "Status update")

        assert result.success
        assert result.action == "comment"
        mock_writer.add_comment.assert_called_once_with("asana_456", "Status update")


class TestAsanaSyncBulk:
    """Test bulk_sync method."""

    @patch("lib.integrations.asana_sync.get_connection")
    def test_bulk_sync_multiple_tasks(self, mock_get_conn):
        """Can sync multiple tasks."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # For simplicity, all tasks will fail (unmapped) in bulk test
        mock_cursor.fetchone.return_value = None  # No mapping found

        mock_writer = MagicMock(spec=AsanaWriter)
        manager = AsanaSyncManager(writer=mock_writer)

        results = manager.bulk_sync(
            ["local_0", "local_1", "local_2"],
            "proj_456",
        )

        assert len(results) == 3
        # All fail because no mapping found
        assert all(not r.success for r in results)


# ============================================================
# Result Dataclass Tests
# ============================================================


class TestAsanaWriteResult:
    """Test AsanaWriteResult dataclass."""

    def test_success_result(self):
        """Success result has all required fields."""
        result = AsanaWriteResult(
            success=True,
            gid="task_123",
            data={"name": "Test"},
            http_status=201,
        )
        assert result.success
        assert result.gid == "task_123"
        assert result.error is None

    def test_error_result(self):
        """Error result has error message."""
        result = AsanaWriteResult(
            success=False,
            error="API error",
            http_status=500,
        )
        assert not result.success
        assert result.error == "API error"
        assert result.gid is None


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_success_result(self):
        """Success sync result."""
        result = SyncResult(
            success=True,
            local_id="local_123",
            asana_gid="asana_456",
            action="create",
        )
        assert result.success
        assert result.action == "create"
        assert result.conflict is False

    def test_conflict_result(self):
        """Sync with conflict."""
        result = SyncResult(
            success=False,
            local_id="local_123",
            error="Conflict detected",
            conflict=True,
        )
        assert not result.success
        assert result.conflict is True
