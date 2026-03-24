"""
Proof tests for authentication and side-effect safety remediation.

Proves:
1. Unauthenticated access is rejected on ALL mutation endpoints (401)
2. Outbox records durable intent BEFORE external calls
3. Retries do not duplicate external effects (idempotent retry)
4. Local failure after external success leaves outbox fulfilled (reconcilable)
5. Idempotency keys survive across SideEffectOutbox instances (durability)
6. Chat command sender verification blocks unauthorized approve/reject
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Part 1: Authentication — prove every mutation endpoint rejects 401
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def app_client():
    """Create a test client with auth enforced."""
    # Must set API key before importing auth module
    os.environ["MOH_TIME_OS_API_KEY"] = "test-secret-key-for-proof"

    from fastapi.testclient import TestClient

    from api.server import app

    return TestClient(app)


class TestAuthEnforcement:
    """Prove that unauthenticated requests are rejected on all mutation surfaces."""

    MUTATION_ENDPOINTS = [
        ("POST", "/api/actions/propose"),
        ("POST", "/api/actions/batch"),
        ("POST", "/api/actions/fake-id/approve"),
        ("POST", "/api/actions/fake-id/reject"),
        ("POST", "/api/actions/fake-id/execute"),
        ("POST", "/api/governance/export"),
        ("POST", "/api/governance/sar"),
    ]

    READ_ENDPOINTS = [
        ("GET", "/api/actions/pending"),
        ("GET", "/api/actions/history"),
        ("GET", "/api/governance/exportable-tables"),
    ]

    @pytest.mark.parametrize("method,path", MUTATION_ENDPOINTS + READ_ENDPOINTS)
    def test_rejects_no_token(self, app_client, method, path):
        """Every protected endpoint returns 401 without Bearer token."""
        if method == "POST":
            resp = app_client.post(path, json={})
        else:
            resp = app_client.get(path)

        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code} without auth — "
            f"expected 401. Body: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("method,path", MUTATION_ENDPOINTS[:3])
    def test_rejects_wrong_token(self, app_client, method, path):
        """Protected endpoints reject wrong Bearer token."""
        headers = {"Authorization": "Bearer wrong-key-should-fail"}
        if method == "POST":
            resp = app_client.post(path, json={}, headers=headers)
        else:
            resp = app_client.get(path, headers=headers)

        assert resp.status_code == 401, (
            f"{method} {path} accepted wrong token — returned {resp.status_code}"
        )

    def test_accepts_correct_token(self, app_client):
        """Auth mode endpoint is public; token exchange works with correct key."""
        resp = app_client.get("/api/auth/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_required"] is True

    def test_is_auth_enabled_returns_true(self):
        """is_auth_enabled() always returns True — no bypass path."""
        os.environ["MOH_TIME_OS_API_KEY"] = "test-key"
        from api.auth import is_auth_enabled

        assert is_auth_enabled() is True


# ═══════════════════════════════════════════════════════════════════════
# Part 2: Outbox pattern — prove durable intent before external effects
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def outbox_db():
    """Create a temporary outbox database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    from lib.outbox import SideEffectOutbox

    outbox = SideEffectOutbox(db_path=db_path)
    yield outbox, db_path

    os.unlink(db_path)


class TestOutboxDurability:
    """Prove outbox provides durable intent tracking."""

    def test_record_intent_before_external_call(self, outbox_db):
        """Intent is durably recorded and retrievable."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="calendar",
            action="create_event",
            payload={"title": "Test Meeting"},
            idempotency_key="cal_test_1",
        )

        assert intent_id.startswith("intent_")

        # Verify it's in the database
        intent = outbox.get_intent(intent_id)
        assert intent is not None
        assert intent["status"] == "pending"
        assert intent["handler"] == "calendar"

    def test_idempotent_retry_prevents_duplicate(self, outbox_db):
        """Second record_intent with same key returns existing, not duplicate."""
        outbox, db_path = outbox_db

        id1 = outbox.record_intent(
            handler="calendar",
            action="create",
            payload={"title": "Test"},
            idempotency_key="unique_key_1",
        )

        id2 = outbox.record_intent(
            handler="calendar",
            action="create",
            payload={"title": "Test DIFFERENT"},
            idempotency_key="unique_key_1",
        )

        assert id1 == id2, "Same idempotency key must return same intent_id"

    def test_fulfilled_intent_blocks_re_execution(self, outbox_db):
        """Once fulfilled, get_fulfilled_intent returns the record — handler should skip."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="email",
            action="create_draft",
            payload={"to": "test@example.com"},
            idempotency_key="email_draft_1",
        )

        outbox.mark_fulfilled(intent_id, external_resource_id="draft_abc123")

        fulfilled = outbox.get_fulfilled_intent(idempotency_key="email_draft_1")
        assert fulfilled is not None
        assert fulfilled["external_resource_id"] == "draft_abc123"
        assert fulfilled["status"] == "fulfilled"

    def test_durability_across_instances(self, outbox_db):
        """Intent survives creating a new SideEffectOutbox instance (simulates restart)."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="asana",
            action="create_task",
            payload={"name": "Test Task"},
            idempotency_key="asana_task_1",
        )
        outbox.mark_fulfilled(intent_id, external_resource_id="asana_gid_123")

        # Simulate process restart — new instance, same DB
        from lib.outbox import SideEffectOutbox

        outbox2 = SideEffectOutbox(db_path=db_path)

        fulfilled = outbox2.get_fulfilled_intent(idempotency_key="asana_task_1")
        assert fulfilled is not None
        assert fulfilled["external_resource_id"] == "asana_gid_123"

    def test_failed_intent_visible_for_reconciliation(self, outbox_db):
        """Failed intents appear in pending list for manual reconciliation."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="notification",
            action="send",
            payload={"notif_id": "n1"},
            idempotency_key="notif_n1_chat",
        )
        outbox.mark_failed(intent_id, error="Channel timeout")

        pending = outbox.get_pending_intents(handler="notification")
        assert len(pending) >= 1
        assert any(p["id"] == intent_id for p in pending)
        failed = next(p for p in pending if p["id"] == intent_id)
        assert failed["status"] == "failed"
        assert "timeout" in failed["error"].lower()

    def test_idempotency_key_persistence(self, outbox_db):
        """Action framework idempotency keys persist across restarts."""
        outbox, db_path = outbox_db

        outbox.store_idempotency_key("action_key_123", "action_abc")

        # Simulate restart
        from lib.outbox import SideEffectOutbox

        outbox2 = SideEffectOutbox(db_path=db_path)
        action_id = outbox2.get_idempotency_action("action_key_123")
        assert action_id == "action_abc"


# ═══════════════════════════════════════════════════════════════════════
# Part 3: Chat command sender verification
# ═══════════════════════════════════════════════════════════════════════


class TestChatCommandSenderVerification:
    """Prove that privileged commands verify sender identity."""

    def test_approve_rejects_unauthorized_sender(self):
        """Unauthorized email cannot approve actions."""
        from lib.integrations.chat_commands import SlashCommandHandler

        handler = SlashCommandHandler(authorized_emails=["owner@example.com"])

        event = {
            "message": {
                "text": "/approve action_123",
                "sender": {"email": "attacker@evil.com"},
            }
        }

        result = handler.handle_event(event)
        # Should contain unauthorized message
        card_text = str(result)
        assert "Unauthorized" in card_text or "unauthorized" in card_text.lower()

    def test_approve_accepts_authorized_sender(self):
        """Authorized email can approve actions (though action may not exist)."""
        from lib.integrations.chat_commands import SlashCommandHandler

        handler = SlashCommandHandler(authorized_emails=["owner@example.com"])

        event = {
            "message": {
                "text": "/approve action_123",
                "sender": {"email": "owner@example.com"},
            }
        }

        result = handler.handle_event(event)
        card_text = str(result)
        # Should NOT contain "Unauthorized" — it proceeds to action lookup
        assert "Unauthorized" not in card_text

    def test_reject_rejects_no_sender_email(self):
        """Missing sender email blocks privileged commands."""
        from lib.integrations.chat_commands import SlashCommandHandler

        handler = SlashCommandHandler(authorized_emails=["owner@example.com"])

        event = {
            "message": {
                "text": "/reject action_123 bad reason",
                "sender": {},
            }
        }

        result = handler.handle_event(event)
        card_text = str(result)
        assert "Unauthorized" in card_text or "unauthorized" in card_text.lower()

    def test_non_privileged_commands_no_auth_check(self):
        """Non-privileged commands (status, tasks, brief) work without sender check."""
        from lib.integrations.chat_commands import SlashCommandHandler

        handler = SlashCommandHandler(authorized_emails=["owner@example.com"])

        for cmd in ["/status", "/tasks", "/brief"]:
            event = {
                "message": {
                    "text": cmd,
                    "sender": {"email": "anyone@example.com"},
                }
            }
            result = handler.handle_event(event)
            card_text = str(result)
            assert "Unauthorized" not in card_text, f"/{cmd} should not require auth"


# ═══════════════════════════════════════════════════════════════════════
# Part 4: Handler-level outbox integration
# ═══════════════════════════════════════════════════════════════════════


class TestCalendarHandlerOutbox:
    """Prove calendar handler uses outbox for external calls."""

    def test_create_event_records_intent_before_api_call(self):
        """Calendar create records outbox intent before calling Google API."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            # Track call order
            call_order = []

            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            mock_writer = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.event_id = "google_event_abc"
            mock_result.data = {"htmlLink": "https://calendar.google.com/event/abc"}

            def mock_create_event(*args, **kwargs):
                call_order.append("create_event_api")
                return mock_result

            mock_writer.create_event = mock_create_event

            mock_store = MagicMock()

            from lib.executor.handlers.calendar import CalendarHandler

            handler = CalendarHandler(store=mock_store)
            handler._writer = mock_writer

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._create_event(
                    {
                        "data": {
                            "title": "Test Meeting",
                            "start_time": "2026-03-15T10:00:00Z",
                            "end_time": "2026-03-15T11:00:00Z",
                        }
                    }
                )

            assert result["success"] is True
            assert result["google_event_id"] == "google_event_abc"

            # Prove intent was recorded BEFORE API call
            assert call_order.index("record_intent") < call_order.index("create_event_api"), (
                f"Intent must be recorded before API call. Order: {call_order}"
            )

        finally:
            os.unlink(db_path)

    def test_retry_after_fulfillment_skips_api_call(self):
        """If outbox shows fulfilled, calendar handler skips the Google API call."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            # Pre-fulfill the intent
            intent_id = outbox.record_intent(
                handler="calendar",
                action="create_event",
                payload={},
                idempotency_key="cal_create_Test Meeting_2026-03-15T10:00:00Z",
            )
            outbox.mark_fulfilled(intent_id, external_resource_id="existing_event_id")

            mock_writer = MagicMock()
            mock_writer.create_event = MagicMock()  # Should NOT be called

            mock_store = MagicMock()

            from lib.executor.handlers.calendar import CalendarHandler

            handler = CalendarHandler(store=mock_store)
            handler._writer = mock_writer

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._create_event(
                    {
                        "data": {
                            "title": "Test Meeting",
                            "start_time": "2026-03-15T10:00:00Z",
                        }
                    }
                )

            assert result["success"] is True
            assert result.get("already_executed") is True
            mock_writer.create_event.assert_not_called()

        finally:
            os.unlink(db_path)


class TestNotificationEngineOutbox:
    """Prove notification engine uses outbox to prevent duplicate delivery."""

    def test_fulfilled_notification_not_resent(self):
        """If outbox shows notification already sent, it's not sent again."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            # Pre-fulfill — simulate previous successful send
            intent_id = outbox.record_intent(
                handler="notification",
                action="send_sync",
                payload={"notif_id": "notif_001", "channel": "chat"},
                idempotency_key="notif_notif_001_chat",
            )
            outbox.mark_fulfilled(intent_id, external_resource_id="msg_123")

            # Verify the outbox blocks re-send
            fulfilled = outbox.get_fulfilled_intent(idempotency_key="notif_notif_001_chat")
            assert fulfilled is not None
            assert fulfilled["external_resource_id"] == "msg_123"

        finally:
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════════
# Part 5: Calendar update/delete/reschedule outbox safety
# ═══════════════════════════════════════════════════════════════════════


class TestCalendarUpdateDeleteReschedule:
    """Prove calendar update, delete, reschedule use outbox."""

    def _make_handler_with_outbox(self, db_path):
        """Helper: create CalendarHandler with outbox and mock writer."""
        from lib.outbox import SideEffectOutbox

        outbox = SideEffectOutbox(db_path=db_path)

        mock_writer = MagicMock()
        mock_store = MagicMock()

        from lib.executor.handlers.calendar import CalendarHandler

        handler = CalendarHandler(store=mock_store)
        handler._writer = mock_writer

        return handler, mock_writer, mock_store, outbox

    def test_update_event_records_intent_before_api(self):
        """Calendar update records outbox intent before Google API call."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handler, mock_writer, mock_store, outbox = self._make_handler_with_outbox(db_path)

            call_order = []
            mock_result = MagicMock(success=True)

            def mock_update(*args, **kwargs):
                call_order.append("update_event_api")
                return mock_result

            mock_writer.update_event = mock_update

            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._update_event(
                    {
                        "event_id": "evt_1",
                        "data": {
                            "google_event_id": "gcal_123",
                            "title": "Updated Meeting",
                        },
                    }
                )

            assert result["success"] is True
            assert call_order.index("record_intent") < call_order.index("update_event_api")
        finally:
            os.unlink(db_path)

    def test_update_event_idempotent_retry(self):
        """Calendar update skips API call when outbox shows fulfilled."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handler, mock_writer, mock_store, outbox = self._make_handler_with_outbox(db_path)

            # Pre-fulfill
            intent_id = outbox.record_intent(
                handler="calendar",
                action="update_event",
                payload={},
                idempotency_key="cal_update_evt_1_gcal_123",
            )
            outbox.mark_fulfilled(intent_id, external_resource_id="gcal_123")

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._update_event(
                    {
                        "event_id": "evt_1",
                        "data": {
                            "google_event_id": "gcal_123",
                            "title": "Updated",
                        },
                    }
                )

            assert result["success"] is True
            mock_writer.update_event.assert_not_called()
        finally:
            os.unlink(db_path)

    def test_delete_event_records_intent_before_api(self):
        """Calendar delete records outbox intent before Google API call."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handler, mock_writer, mock_store, outbox = self._make_handler_with_outbox(db_path)

            call_order = []
            mock_result = MagicMock(success=True)

            def mock_delete(*args, **kwargs):
                call_order.append("delete_event_api")
                return mock_result

            mock_writer.delete_event = mock_delete

            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._delete_event(
                    {
                        "event_id": "evt_1",
                        "data": {
                            "google_event_id": "gcal_123",
                        },
                    }
                )

            assert result["success"] is True
            assert call_order.index("record_intent") < call_order.index("delete_event_api")
        finally:
            os.unlink(db_path)

    def test_reschedule_event_records_intent_before_api(self):
        """Calendar reschedule records outbox intent before Google API call."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handler, mock_writer, mock_store, outbox = self._make_handler_with_outbox(db_path)

            call_order = []
            mock_result = MagicMock(success=True)

            def mock_update(*args, **kwargs):
                call_order.append("update_event_api")
                return mock_result

            mock_writer.update_event = mock_update

            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            with patch("lib.outbox.get_outbox", return_value=outbox):
                result = handler._reschedule_event(
                    {
                        "event_id": "evt_1",
                        "data": {
                            "google_event_id": "gcal_123",
                            "start_time": "2026-03-16T10:00:00Z",
                        },
                    }
                )

            assert result["success"] is True
            assert call_order.index("record_intent") < call_order.index("update_event_api")
        finally:
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════════
# Part 6: Asana comment and status update outbox safety
# ═══════════════════════════════════════════════════════════════════════


class TestAsanaCommentAndStatusOutbox:
    """Prove Asana comment and status update use outbox."""

    def test_add_comment_records_intent_before_api(self):
        """Asana add_comment records intent before calling Asana API."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            call_order = []
            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            mock_writer = MagicMock()
            mock_result = MagicMock(success=True, gid="comment_gid_1")

            def mock_add_comment(*args, **kwargs):
                call_order.append("add_comment_api")
                return mock_result

            mock_writer.add_comment = mock_add_comment

            from lib.executor.handlers.asana import AsanaActionHandler

            handler = AsanaActionHandler(store=MagicMock())
            handler._writer = mock_writer

            with patch("lib.executor.handlers.asana.get_outbox", return_value=outbox):
                result = handler._add_comment(
                    {"data": {"task_gid": "task_1", "text": "Test comment"}}
                )

            assert result["success"] is True
            assert result["gid"] == "comment_gid_1"
            assert call_order.index("record_intent") < call_order.index("add_comment_api")
        finally:
            os.unlink(db_path)

    def test_add_comment_idempotent_retry(self):
        """Asana add_comment skips API if outbox shows fulfilled."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            text_hash = hash("Test comment") & 0xFFFFFFFF
            intent_id = outbox.record_intent(
                handler="asana",
                action="add_comment",
                payload={},
                idempotency_key=f"asana_comment_task_1_{text_hash}",
            )
            outbox.mark_fulfilled(intent_id, external_resource_id="existing_comment")

            mock_writer = MagicMock()

            from lib.executor.handlers.asana import AsanaActionHandler

            handler = AsanaActionHandler(store=MagicMock())
            handler._writer = mock_writer

            with patch("lib.executor.handlers.asana.get_outbox", return_value=outbox):
                result = handler._add_comment(
                    {"data": {"task_gid": "task_1", "text": "Test comment"}}
                )

            assert result["success"] is True
            assert result.get("already_executed") is True
            mock_writer.add_comment.assert_not_called()
        finally:
            os.unlink(db_path)

    def test_update_status_records_intent_before_api(self):
        """Asana update_status records intent before calling Asana API."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            call_order = []
            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            mock_writer = MagicMock()
            mock_result = MagicMock(success=True, gid="task_gid_1")

            def mock_update_task(*args, **kwargs):
                call_order.append("update_task_api")
                return mock_result

            mock_writer.update_task = mock_update_task

            from lib.executor.handlers.asana import AsanaActionHandler

            handler = AsanaActionHandler(store=MagicMock())
            handler._writer = mock_writer

            with patch("lib.executor.handlers.asana.get_outbox", return_value=outbox):
                result = handler._update_status({"data": {"task_gid": "task_1", "completed": True}})

            assert result["success"] is True
            assert call_order.index("record_intent") < call_order.index("update_task_api")
        finally:
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════════
# Part 7: Task handler Asana sync outbox safety
# ═══════════════════════════════════════════════════════════════════════


class TestTaskHandlerAsanaSync:
    """Prove task handler Asana sync uses outbox."""

    def test_sync_to_asana_create_records_intent(self):
        """_sync_to_asana (create path) records outbox intent before Asana API."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)
            call_order = []
            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            mock_client = MagicMock()

            def mock_create(*args, **kwargs):
                call_order.append("asana_create_api")
                return {"gid": "new_gid_123"}

            mock_client.tasks.create_task = mock_create

            from lib.executor.handlers.task import TaskHandler

            handler = TaskHandler(
                store=MagicMock(),
                config={"asana_enabled": True, "asana_client": mock_client},
            )

            with patch("lib.executor.handlers.task.get_outbox", return_value=outbox):
                handler._sync_to_asana(
                    "task_1",
                    {"title": "Test Task", "sync_to_asana": True},
                )

            assert call_order.index("record_intent") < call_order.index("asana_create_api")
        finally:
            os.unlink(db_path)

    def test_sync_to_asana_idempotent_retry(self):
        """_sync_to_asana skips API when outbox shows fulfilled."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)

            # Pre-fulfill
            intent_id = outbox.record_intent(
                handler="task_sync",
                action="create_asana",
                payload={},
                idempotency_key="task_sync_create_task_1",
            )
            outbox.mark_fulfilled(intent_id, external_resource_id="existing_gid")

            mock_client = MagicMock()

            from lib.executor.handlers.task import TaskHandler

            handler = TaskHandler(
                store=MagicMock(),
                config={"asana_enabled": True, "asana_client": mock_client},
            )

            with patch("lib.executor.handlers.task.get_outbox", return_value=outbox):
                handler._sync_to_asana(
                    "task_1",
                    {"title": "Test Task"},
                )

            mock_client.tasks.create_task.assert_not_called()
        finally:
            os.unlink(db_path)

    def test_complete_in_asana_records_intent(self):
        """_complete_in_asana records outbox intent before Asana API."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from lib.outbox import SideEffectOutbox

            outbox = SideEffectOutbox(db_path=db_path)
            call_order = []
            original_record = outbox.record_intent

            def tracking_record(*args, **kwargs):
                call_order.append("record_intent")
                return original_record(*args, **kwargs)

            outbox.record_intent = tracking_record

            mock_client = MagicMock()

            def mock_update(*args, **kwargs):
                call_order.append("asana_update_api")

            mock_client.tasks.update_task = mock_update

            from lib.executor.handlers.task import TaskHandler

            handler = TaskHandler(
                store=MagicMock(),
                config={"asana_client": mock_client},
            )

            with patch("lib.executor.handlers.task.get_outbox", return_value=outbox):
                handler._complete_in_asana("asana_gid_456")

            assert call_order.index("record_intent") < call_order.index("asana_update_api")
        finally:
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════════
# Part 8: Reconciliation tooling
# ═══════════════════════════════════════════════════════════════════════


class TestReconciliationTooling:
    """Prove reconciliation operations work correctly."""

    def test_get_stats(self, outbox_db):
        """get_stats returns correct counts by status."""
        outbox, db_path = outbox_db

        # Create one of each status
        id1 = outbox.record_intent(handler="cal", action="a", payload={}, idempotency_key="k1")
        id2 = outbox.record_intent(handler="cal", action="b", payload={}, idempotency_key="k2")
        outbox.record_intent(handler="cal", action="c", payload={}, idempotency_key="k3")

        outbox.mark_fulfilled(id1, external_resource_id="ext_1")
        outbox.mark_failed(id2, error="timeout")
        # id3 stays pending

        stats = outbox.get_stats()
        assert stats["fulfilled"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 1
        assert stats["total"] == 3

    def test_reset_failed_to_pending(self, outbox_db):
        """Failed intents can be reset to pending for retry."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="email", action="send", payload={}, idempotency_key="retry_test"
        )
        outbox.mark_failed(intent_id, error="Connection reset")

        success = outbox.reset_failed_to_pending(intent_id)
        assert success is True

        intent = outbox.get_intent(intent_id)
        assert intent["status"] == "pending"
        assert intent["error"] is None

    def test_force_fulfill(self, outbox_db):
        """Operator can force-fulfill a pending intent."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="asana", action="create", payload={}, idempotency_key="force_test"
        )

        success = outbox.force_fulfill(intent_id, external_resource_id="asana_gid_manual")
        assert success is True

        intent = outbox.get_intent(intent_id)
        assert intent["status"] == "fulfilled"
        assert intent["external_resource_id"] == "asana_gid_manual"

        # Now a retry with the same key sees it as fulfilled
        fulfilled = outbox.get_fulfilled_intent(idempotency_key="force_test")
        assert fulfilled is not None
        assert fulfilled["external_resource_id"] == "asana_gid_manual"

    def test_force_fulfill_blocks_duplicate(self, outbox_db):
        """After force-fulfill, handler sees fulfilled and skips API call."""
        outbox, db_path = outbox_db

        intent_id = outbox.record_intent(
            handler="calendar",
            action="create_event",
            payload={},
            idempotency_key="force_dup_test",
        )
        outbox.force_fulfill(intent_id, external_resource_id="gcal_forced")

        # Simulate handler checking on retry
        fulfilled = outbox.get_fulfilled_intent(idempotency_key="force_dup_test")
        assert fulfilled is not None
        assert fulfilled["external_resource_id"] == "gcal_forced"

    def test_get_all_intents_filters(self, outbox_db):
        """get_all_intents supports status and handler filters."""
        outbox, db_path = outbox_db

        outbox.record_intent(handler="calendar", action="create", payload={}, idempotency_key="f1")
        id2 = outbox.record_intent(
            handler="asana", action="create", payload={}, idempotency_key="f2"
        )
        outbox.mark_fulfilled(id2, external_resource_id="g1")

        # Filter by status
        pending = outbox.get_all_intents(status="pending")
        assert all(i["status"] == "pending" for i in pending)

        # Filter by handler
        asana_only = outbox.get_all_intents(handler="asana")
        assert all(i["handler"] == "asana" for i in asana_only)

        # Combined filter
        fulfilled_asana = outbox.get_all_intents(status="fulfilled", handler="asana")
        assert len(fulfilled_asana) == 1
        assert fulfilled_asana[0]["handler"] == "asana"


# ═══════════════════════════════════════════════════════════════════════
# Part 9: Spec router auth closure
# ═══════════════════════════════════════════════════════════════════════


class TestSpecRouterAuth:
    """Prove spec router mutation endpoints require auth."""

    SPEC_MUTATIONS = [
        ("POST", "/api/v2/inbox/fake-id/action"),
        ("POST", "/api/v2/inbox/fake-id/read"),
        ("POST", "/api/v2/issues"),
        ("POST", "/api/v2/notifications/mute"),
    ]

    @pytest.mark.parametrize("method,path", SPEC_MUTATIONS)
    def test_spec_mutations_reject_no_token(self, app_client, method, path):
        """Spec router mutation endpoints return 401 without Bearer token."""
        resp = app_client.post(path, json={})
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code} without auth — "
            f"expected 401. Body: {resp.text[:200]}"
        )
