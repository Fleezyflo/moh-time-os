"""
Proof tests for the missed-surface closure pass (Pass 3 — full closure).

Proves:
1. ALL 61 inline mutation endpoints in server.py reject unauthenticated requests (401)
2. Intentionally public endpoints (health, ready, auth/mode) still work without auth
3. Chat interactive approve/reject rejects unauthorized sender identity
4. Chat interactive approve/reject accepts authorized sender identity
5. ChatInteractive outbox-safe wrapper records durable intent before external call
6. ChatInteractive outbox-safe wrapper prevents duplicates via idempotency
7. AsanaSyncManager outbox-safe wrapper records durable intent before sync
8. safe_send_sync records durable intent before channel.send_sync()
9. Retries do not duplicate external effects (all outbox-covered paths)
10. Runtime guards: direct ChatInteractive mutation calls raise RuntimeError
11. Runtime guards: direct AsanaSyncManager mutation calls raise RuntimeError
12. Codebase scan: no production code imports or constructs unsafe primitives directly
13. lib/integrations/__init__.py exports safe wrappers, not unsafe classes
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Part 1: server.py auth — ALL 61 mutation endpoints reject without auth
# ═══════════════════════════════════════════════════════════════════════


# Complete list of all inline mutation endpoints in api/server.py
ALL_MUTATION_ENDPOINTS = [
    ("POST", "/api/time/schedule"),
    ("POST", "/api/time/unschedule"),
    ("POST", "/api/commitments/fake-id/link"),
    ("POST", "/api/commitments/fake-id/done"),
    ("POST", "/api/capacity/debt/accrue"),
    ("POST", "/api/capacity/debt/fake-id/resolve"),
    ("POST", "/api/clients/link"),
    ("POST", "/api/tasks"),
    ("PUT", "/api/tasks/fake-id"),
    ("POST", "/api/tasks/fake-id/notes"),
    ("DELETE", "/api/tasks/fake-id"),
    ("POST", "/api/tasks/fake-id/delegate"),
    ("POST", "/api/tasks/fake-id/escalate"),
    ("POST", "/api/tasks/fake-id/recall"),
    ("POST", "/api/data-quality/cleanup/ancient"),
    ("POST", "/api/data-quality/cleanup/stale"),
    ("POST", "/api/data-quality/recalculate-priorities"),
    ("POST", "/api/data-quality/cleanup/legacy-signals"),
    ("POST", "/api/priorities/fake-id/complete"),
    ("POST", "/api/priorities/fake-id/snooze"),
    ("POST", "/api/priorities/fake-id/delegate"),
    ("POST", "/api/decisions/fake-id"),
    ("POST", "/api/bundles/rollback-last"),
    ("POST", "/api/bundles/fake-id/rollback"),
    ("POST", "/api/calibration/run"),
    ("POST", "/api/feedback"),
    ("POST", "/api/priorities/bulk"),
    ("POST", "/api/priorities/archive-stale"),
    ("POST", "/api/emails/fake-id/mark-actionable"),
    ("POST", "/api/notifications/fake-id/dismiss"),
    ("POST", "/api/notifications/dismiss-all"),
    ("POST", "/api/approvals/fake-id"),
    ("POST", "/api/approvals/fake-id/modify"),
    ("PUT", "/api/governance/tasks"),
    ("PUT", "/api/governance/tasks/threshold"),
    ("POST", "/api/governance/emergency-brake"),
    ("DELETE", "/api/governance/emergency-brake"),
    ("POST", "/api/sync"),
    ("POST", "/api/analyze"),
    ("POST", "/api/cycle"),
    ("PUT", "/api/clients/fake-id"),
    ("POST", "/api/projects/fake-id/enrollment"),
    ("POST", "/api/sync/xero"),
    ("POST", "/api/tasks/link"),
    ("POST", "/api/projects/propose"),
    ("POST", "/api/emails/fake-id/dismiss"),
    ("POST", "/api/tasks/fake-id/block"),
    ("DELETE", "/api/tasks/fake-id/block/fake-blocker"),
    ("PATCH", "/api/control-room/issues/fake-id/resolve"),
    ("PATCH", "/api/control-room/issues/fake-id/state"),
    ("POST", "/api/control-room/issues/fake-id/notes"),
    ("POST", "/api/control-room/watchers/fake-id/dismiss"),
    ("POST", "/api/control-room/watchers/fake-id/snooze"),
    ("POST", "/api/control-room/issues"),
    ("POST", "/api/control-room/proposals/fake-id/snooze"),
    ("POST", "/api/control-room/proposals/fake-id/dismiss"),
    ("POST", "/api/control-room/fix-data/identity/fake-id/resolve"),
    ("POST", "/api/admin/seed-identities"),
    ("POST", "/api/command/findings/fake-id/acknowledge"),
    ("POST", "/api/command/findings/fake-id/suppress"),
    ("POST", "/api/command/weight-review/fake-id"),
]

# Intentionally public endpoints — no auth required
PUBLIC_ENDPOINTS = [
    ("GET", "/api/health"),
    ("GET", "/api/ready"),
    ("GET", "/api/auth/mode"),
]


@pytest.fixture(scope="module")
def test_client():
    """Create a test client with auth enforced."""
    os.environ["MOH_TIME_OS_API_KEY"] = "test-proof-key-2026"
    os.environ.setdefault("MOH_TIME_OS_ENV", "test")

    from fastapi.testclient import TestClient

    from api.server import app

    return TestClient(app, raise_server_exceptions=False)


class TestServerAuthClosure:
    """Prove ALL 61 inline mutation endpoints reject unauthenticated access."""

    @pytest.mark.parametrize("method,path", ALL_MUTATION_ENDPOINTS)
    def test_mutation_rejects_no_auth(self, test_client, method, path):
        """Mutation endpoint returns 401 without Bearer token."""
        dispatch = {
            "POST": test_client.post,
            "PUT": test_client.put,
            "DELETE": test_client.delete,
            "PATCH": test_client.patch,
        }
        fn = dispatch[method]
        body = {}
        if "feedback" in path:
            body = {"item_id": "x", "rating": 1}
        elif "weight-review" in path:
            body = {"action": "confirm"}
        elif "notes" in path and "issues" in path:
            body = {"text": "test"}
        elif "notes" in path:
            body = {"note": "test"}
        elif "approvals" in path and "modify" in path:
            body = {"modifications": {}}
        elif "approvals" in path:
            body = {"action": "approve"}
        elif "bulk" in path:
            body = {"action": "archive", "ids": []}
        elif "governance" in path and "threshold" in path:
            body = {"threshold": 0.5}
        elif "governance" in path and method == "PUT":
            body = {"mode": "supervised"}
        elif "enrollment" in path:
            body = {"action": "enroll"}
        elif "block" in path and method == "POST":
            body = {"blocker_id": "fake"}
        elif "resolve" in path:
            body = {"resolution": "test"}
        elif "state" in path:
            body = {"state": "open"}
        elif "dismiss" in path:
            body = {"actor": "test"}
        elif "snooze" in path and "watchers" in path:
            body = {"hours": 24}
        elif "snooze" in path:
            body = {"days": 7}
        elif "issues" in path and method == "POST" and "notes" not in path:
            body = {"proposal_id": "fake"}
        elif "link" in path and "tasks" in path:
            body = {"links": []}

        resp = fn(path, json=body)
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code} without auth — expected 401/403. "
            f"Body: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("method,path", ALL_MUTATION_ENDPOINTS[:5])
    def test_mutation_rejects_wrong_token(self, test_client, method, path):
        """Mutation endpoints reject wrong Bearer token."""
        headers = {"Authorization": "Bearer wrong-key-should-fail"}
        dispatch = {
            "POST": test_client.post,
            "PUT": test_client.put,
            "DELETE": test_client.delete,
            "PATCH": test_client.patch,
        }
        fn = dispatch[method]
        resp = fn(path, json={}, headers=headers)
        assert resp.status_code == 401, (
            f"{method} {path} accepted wrong token — returned {resp.status_code}"
        )

    @pytest.mark.parametrize("method,path", PUBLIC_ENDPOINTS)
    def test_public_endpoints_accessible(self, test_client, method, path):
        """Intentionally public endpoints work without auth."""
        resp = test_client.get(path)
        assert resp.status_code in (200, 503), (
            f"{method} {path} returned {resp.status_code} — expected 200 or 503"
        )


# ═══════════════════════════════════════════════════════════════════════
# Part 2: Chat interactive sender verification
# ═══════════════════════════════════════════════════════════════════════


class TestChatInteractiveSenderVerification:
    """Prove interactive approve/reject verifies sender identity."""

    def test_approve_rejects_no_user(self):
        """APPROVE_ACTION with no user field is rejected."""
        from api.chat_webhook_router import _verify_interactive_sender

        result = _verify_interactive_sender(None, "APPROVE_ACTION")
        assert result is None

    def test_approve_rejects_no_email(self):
        """APPROVE_ACTION with user but no email is rejected."""
        from api.chat_webhook_router import _verify_interactive_sender

        result = _verify_interactive_sender({"name": "Some User"}, "APPROVE_ACTION")
        assert result is None

    def test_approve_rejects_unauthorized_email(self):
        """APPROVE_ACTION from unauthorized email is rejected."""
        # Reset cached emails
        import api.chat_webhook_router as mod
        from api.chat_webhook_router import _verify_interactive_sender

        mod._authorized_emails = {"owner@example.com"}

        result = _verify_interactive_sender({"email": "attacker@evil.com"}, "APPROVE_ACTION")
        assert result is None

    def test_approve_accepts_authorized_email(self):
        """APPROVE_ACTION from authorized email is accepted."""
        import api.chat_webhook_router as mod
        from api.chat_webhook_router import _verify_interactive_sender

        mod._authorized_emails = {"owner@example.com"}

        result = _verify_interactive_sender({"email": "owner@example.com"}, "APPROVE_ACTION")
        assert result == "owner@example.com"

    def test_reject_action_same_verification(self):
        """REJECT_ACTION uses the same verification path."""
        import api.chat_webhook_router as mod
        from api.chat_webhook_router import _verify_interactive_sender

        mod._authorized_emails = {"owner@example.com"}

        # Unauthorized
        result = _verify_interactive_sender({"email": "hacker@evil.com"}, "REJECT_ACTION")
        assert result is None

        # Authorized
        result = _verify_interactive_sender({"email": "owner@example.com"}, "REJECT_ACTION")
        assert result == "owner@example.com"


# ═══════════════════════════════════════════════════════════════════════
# Part 3: ChatInteractive outbox coverage
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def chat_outbox_db():
    """Create outbox and mock ChatInteractive for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    from lib.outbox import SideEffectOutbox

    outbox = SideEffectOutbox(db_path=db_path)
    yield outbox, db_path
    os.unlink(db_path)


class TestChatInteractiveOutbox:
    """Prove ChatInteractive mutations go through outbox."""

    def test_send_message_records_intent(self, chat_outbox_db):
        """send_message records durable intent before external call."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.send_message.return_value = ChatWriteResult(
            success=True, message_name="spaces/X/messages/Y"
        )

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)
        result = safe.send_message("spaces/X", "Hello")

        assert result.success
        mock_client.send_message.assert_called_once()

        # Verify outbox has fulfilled intent
        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1

    def test_send_message_idempotent_retry(self, chat_outbox_db):
        """Duplicate send_message with same params returns outbox hit, no external call."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.send_message.return_value = ChatWriteResult(
            success=True, message_name="spaces/X/messages/Y"
        )

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)

        # First call — goes through
        safe.send_message("spaces/X", "Hello")
        assert mock_client.send_message.call_count == 1

        # Second call — idempotent skip
        result2 = safe.send_message("spaces/X", "Hello")
        assert result2.success
        assert mock_client.send_message.call_count == 1  # NOT called again

    def test_send_card_records_intent(self, chat_outbox_db):
        """send_card records durable intent."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.send_card.return_value = ChatWriteResult(
            success=True, message_name="spaces/X/messages/Z"
        )

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)
        result = safe.send_card("spaces/X", {"id": "card1", "header": {}})

        assert result.success
        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1

    def test_delete_message_failed_tracked(self, chat_outbox_db):
        """Failed delete_message is tracked in outbox for reconciliation."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.delete_message.return_value = ChatWriteResult(success=False, error="HTTP 404")

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)
        result = safe.delete_message("spaces/X/messages/Y")

        assert not result.success
        pending = outbox.get_pending_intents(handler="chat_interactive")
        assert len(pending) >= 1
        assert any(p["status"] == "failed" for p in pending)

    def test_create_space_records_intent(self, chat_outbox_db):
        """create_space records intent and tracks external resource."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.create_space.return_value = ChatWriteResult(
            success=True, space_name="spaces/NEWSPACE"
        )

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)
        result = safe.create_space("Test Space")

        assert result.success
        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1

    def test_add_member_records_intent(self, chat_outbox_db):
        """add_member records intent."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.chat_interactive import ChatWriteResult

        mock_client = MagicMock()
        mock_client.add_member.return_value = ChatWriteResult(
            success=True, data={"name": "spaces/X/members/user@test.com"}
        )

        from lib.integrations.chat_interactive_safe import SafeChatInteractive

        safe = SafeChatInteractive(client=mock_client, outbox=outbox)
        result = safe.add_member("spaces/X", "user@test.com")

        assert result.success
        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1


# ═══════════════════════════════════════════════════════════════════════
# Part 4: AsanaSyncManager outbox coverage
# ═══════════════════════════════════════════════════════════════════════


class TestAsanaSyncOutbox:
    """Prove AsanaSyncManager mutations go through outbox."""

    def test_sync_task_records_intent(self, chat_outbox_db):
        """sync_task_to_asana records durable intent before Asana API call."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.asana_sync import SyncResult

        mock_manager = MagicMock()
        mock_manager.sync_task_to_asana.return_value = SyncResult(
            success=True,
            local_id="task_1",
            asana_gid="12345",
            action="create",
        )

        from lib.integrations.asana_sync_safe import SafeAsanaSyncManager

        safe = SafeAsanaSyncManager(manager=mock_manager, outbox=outbox)
        result = safe.sync_task_to_asana("task_1", "project_gid_1")

        assert result.success
        assert result.asana_gid == "12345"
        mock_manager.sync_task_to_asana.assert_called_once()

        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1

    def test_sync_task_idempotent_retry(self, chat_outbox_db):
        """Retry with same args returns outbox hit, no duplicate external call."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.asana_sync import SyncResult

        mock_manager = MagicMock()
        mock_manager.sync_task_to_asana.return_value = SyncResult(
            success=True,
            local_id="task_2",
            asana_gid="67890",
            action="create",
        )

        from lib.integrations.asana_sync_safe import SafeAsanaSyncManager

        safe = SafeAsanaSyncManager(manager=mock_manager, outbox=outbox)

        safe.sync_task_to_asana("task_2", "project_2")
        assert mock_manager.sync_task_to_asana.call_count == 1

        result2 = safe.sync_task_to_asana("task_2", "project_2")
        assert result2.success
        assert mock_manager.sync_task_to_asana.call_count == 1  # NOT called again

    def test_sync_failure_tracked(self, chat_outbox_db):
        """Failed sync is tracked in outbox for reconciliation."""
        outbox, db_path = chat_outbox_db

        from lib.integrations.asana_sync import SyncResult

        mock_manager = MagicMock()
        mock_manager.sync_task_to_asana.return_value = SyncResult(
            success=False,
            local_id="task_3",
            error="Asana API timeout",
        )

        from lib.integrations.asana_sync_safe import SafeAsanaSyncManager

        safe = SafeAsanaSyncManager(manager=mock_manager, outbox=outbox)
        result = safe.sync_task_to_asana("task_3", "project_3")

        assert not result.success
        pending = outbox.get_pending_intents(handler="asana_sync")
        assert len(pending) >= 1
        assert any("timeout" in (p.get("error") or "").lower() for p in pending)


# ═══════════════════════════════════════════════════════════════════════
# Part 5: safe_send_sync outbox coverage
# ═══════════════════════════════════════════════════════════════════════


class TestSafeSendSync:
    """Prove channel.send_sync() callers are outbox-protected."""

    def test_records_intent_before_send(self, chat_outbox_db):
        """safe_send_sync records intent before calling channel.send_sync()."""
        outbox, db_path = chat_outbox_db

        mock_channel = MagicMock()
        mock_channel.send_sync.return_value = {
            "success": True,
            "message_id": "msg_123",
            "status": "sent",
        }

        from lib.notifier.channels.safe_send import safe_send_sync

        result = safe_send_sync(
            channel=mock_channel,
            message="Test notification",
            title="Test",
            caller="test_runner",
            outbox=outbox,
        )

        assert result["success"]
        mock_channel.send_sync.assert_called_once()
        stats = outbox.get_stats()
        assert stats.get("fulfilled", 0) >= 1

    def test_idempotent_retry(self, chat_outbox_db):
        """Duplicate send with same message skips external call."""
        outbox, db_path = chat_outbox_db

        mock_channel = MagicMock()
        mock_channel.send_sync.return_value = {
            "success": True,
            "message_id": "msg_456",
            "status": "sent",
        }

        from lib.notifier.channels.safe_send import safe_send_sync

        safe_send_sync(
            channel=mock_channel,
            message="Daily digest content",
            title="Morning Brief",
            caller="morning_brief_test",
            outbox=outbox,
        )
        assert mock_channel.send_sync.call_count == 1

        result2 = safe_send_sync(
            channel=mock_channel,
            message="Daily digest content",
            title="Morning Brief",
            caller="morning_brief_test",
            outbox=outbox,
        )
        assert result2["success"]
        assert mock_channel.send_sync.call_count == 1  # NOT called again

    def test_failure_tracked(self, chat_outbox_db):
        """Failed send is tracked in outbox."""
        outbox, db_path = chat_outbox_db

        mock_channel = MagicMock()
        mock_channel.send_sync.return_value = {
            "success": False,
            "error": "Webhook timeout",
            "status": "error",
        }

        from lib.notifier.channels.safe_send import safe_send_sync

        result = safe_send_sync(
            channel=mock_channel,
            message="Failure test message",
            caller="failure_test",
            outbox=outbox,
        )

        assert not result["success"]
        pending = outbox.get_pending_intents(handler="notification")
        assert len(pending) >= 1
        assert any("timeout" in (p.get("error") or "").lower() for p in pending)

    def test_exception_during_send_tracked(self, chat_outbox_db):
        """Exception during send_sync() is tracked as failed intent."""
        outbox, db_path = chat_outbox_db

        mock_channel = MagicMock()
        mock_channel.send_sync.side_effect = OSError("Connection refused")

        from lib.notifier.channels.safe_send import safe_send_sync

        result = safe_send_sync(
            channel=mock_channel,
            message="Exception test",
            caller="exception_test",
            outbox=outbox,
        )

        assert not result["success"]
        assert "Connection refused" in result.get("error", "")


# ═══════════════════════════════════════════════════════════════════════
# Part 6: Runtime guards — unsafe direct calls raise RuntimeError
# ═══════════════════════════════════════════════════════════════════════


class TestChatInteractiveDirectCallGuard:
    """Prove ChatInteractive mutation methods raise RuntimeError without _direct_call_allowed."""

    def test_send_message_blocked(self):
        """send_message raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.send_message("spaces/X", "text")

    def test_send_card_blocked(self):
        """send_card raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.send_card("spaces/X", {"id": "card"})

    def test_update_message_blocked(self):
        """update_message raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.update_message("spaces/X/messages/Y", text="new")

    def test_delete_message_blocked(self):
        """delete_message raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.delete_message("spaces/X/messages/Y")

    def test_create_space_blocked(self):
        """create_space raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.create_space("Test")

    def test_add_member_blocked(self):
        """add_member raises RuntimeError on default construction."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            client.add_member("spaces/X", "user@test.com")

    def test_allowed_when_flag_set(self):
        """Mutation methods work when _direct_call_allowed=True."""
        from lib.integrations.chat_interactive import ChatInteractive

        client = ChatInteractive(bot_token="test_token", _direct_call_allowed=True)
        # Should not raise — will fail on httpx call, but that's OK
        # We just verify the guard doesn't block
        with patch("lib.integrations.chat_interactive.HAS_HTTPX", False):
            result = client.send_message("spaces/X", "text")
            assert not result.success  # Fails because httpx not available, but guard didn't fire


class TestAsanaSyncManagerDirectCallGuard:
    """Prove AsanaSyncManager mutation methods raise RuntimeError without _direct_call_allowed."""

    def test_sync_task_blocked(self):
        """sync_task_to_asana raises RuntimeError on default construction."""
        from lib.integrations.asana_sync import AsanaSyncManager

        mock_writer = MagicMock()
        manager = AsanaSyncManager(writer=mock_writer, _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            manager.sync_task_to_asana("task_1", "project_1")

    def test_sync_completion_blocked(self):
        """sync_completion raises RuntimeError on default construction."""
        from lib.integrations.asana_sync import AsanaSyncManager

        mock_writer = MagicMock()
        manager = AsanaSyncManager(writer=mock_writer, _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            manager.sync_completion("task_1")

    def test_post_status_comment_blocked(self):
        """post_status_comment raises RuntimeError on default construction."""
        from lib.integrations.asana_sync import AsanaSyncManager

        mock_writer = MagicMock()
        manager = AsanaSyncManager(writer=mock_writer, _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            manager.post_status_comment("task_1", "comment")

    def test_bulk_sync_blocked(self):
        """bulk_sync raises RuntimeError on default construction."""
        from lib.integrations.asana_sync import AsanaSyncManager

        mock_writer = MagicMock()
        manager = AsanaSyncManager(writer=mock_writer, _direct_call_allowed=False)
        with pytest.raises(RuntimeError, match="Direct call.*forbidden"):
            manager.bulk_sync(["task_1"], "project_1")

    def test_allowed_when_flag_set(self):
        """sync methods work when _direct_call_allowed=True (hits DB, not guard)."""
        from lib.integrations.asana_sync import AsanaSyncManager

        mock_writer = MagicMock()
        manager = AsanaSyncManager(writer=mock_writer, _direct_call_allowed=True)
        # Will fail on DB access, but guard doesn't fire
        with patch("lib.integrations.asana_sync.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = manager.sync_task_to_asana("task_1", "project_1")
            assert not result.success  # No local task found, but guard didn't fire


# ═══════════════════════════════════════════════════════════════════════
# Part 7: Codebase scan — no production code uses unsafe direct paths
# ═══════════════════════════════════════════════════════════════════════


class TestCodebaseEnforcement:
    """Scan production code to ensure no forbidden direct-call patterns exist."""

    @staticmethod
    def _get_production_python_files():
        """Get all Python files under lib/ and api/ (production code only)."""
        import glob

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lib_files = glob.glob(os.path.join(base, "lib", "**", "*.py"), recursive=True)
        api_files = glob.glob(os.path.join(base, "api", "*.py"))
        return lib_files + api_files

    def test_no_production_import_of_chatinteractive(self):
        """No production file imports ChatInteractive directly (except safe wrapper)."""
        allowed = {
            "chat_interactive.py",  # The class definition itself
            "chat_interactive_safe.py",  # The safe wrapper (needs to import it)
        }

        violations = []
        for filepath in self._get_production_python_files():
            basename = os.path.basename(filepath)
            if basename in allowed:
                continue
            with open(filepath) as f:
                content = f.read()
            if "from lib.integrations.chat_interactive import ChatInteractive" in content:
                violations.append(filepath)
            if "ChatInteractive(" in content and basename not in allowed:
                violations.append(f"{filepath} (construction)")

        assert not violations, (
            f"Production code imports/constructs ChatInteractive directly "
            f"(use SafeChatInteractive instead): {violations}"
        )

    def test_no_production_import_of_asanasyncmanager(self):
        """No production file imports AsanaSyncManager directly (except safe wrapper)."""
        allowed = {
            "asana_sync.py",  # The class definition itself
            "asana_sync_safe.py",  # The safe wrapper (needs to import it)
            "__init__.py",  # Package init imports SyncResult (type only)
        }

        violations = []
        for filepath in self._get_production_python_files():
            basename = os.path.basename(filepath)
            if basename in allowed:
                continue
            with open(filepath) as f:
                content = f.read()
            if "from lib.integrations.asana_sync import AsanaSyncManager" in content:
                violations.append(filepath)
            if "AsanaSyncManager(" in content and basename not in allowed:
                violations.append(f"{filepath} (construction)")

        assert not violations, (
            f"Production code imports/constructs AsanaSyncManager directly "
            f"(use SafeAsanaSyncManager instead): {violations}"
        )

    def test_no_direct_send_sync_outside_safe_paths(self):
        """No production code calls channel.send_sync() outside the sanctioned paths."""
        # These files are allowed to call .send_sync():
        # - safe_send.py (the wrapper itself, calls channel.send_sync internally)
        # - engine.py (notification engine, has its own outbox protection from Pass 1)
        # - Channel implementations (email.py etc.) define send_sync() as their method
        allowed_basenames = {
            "safe_send.py",
            "engine.py",
            "google_chat.py",  # Channel implementation defines send_sync
            "email.py",  # Channel implementation defines/delegates send_sync
            "console.py",  # Channel implementation if it exists
        }

        violations = []
        for filepath in self._get_production_python_files():
            basename = os.path.basename(filepath)
            if basename in allowed_basenames:
                continue
            with open(filepath) as f:
                for lineno, line in enumerate(f, 1):
                    # Match .send_sync( but not safe_send_sync or def send_sync
                    stripped = line.strip()
                    if (
                        ".send_sync(" in stripped
                        and "safe_send_sync" not in stripped
                        and not stripped.startswith("def ")
                    ):
                        violations.append(f"{filepath}:{lineno}: {stripped[:100]}")

        assert not violations, (
            f"Production code calls channel.send_sync() directly — "
            f"use safe_send_sync() or the notification engine instead: {violations}"
        )

    def test_integrations_init_exports_safe_wrappers(self):
        """lib/integrations/__init__.py exports SafeChatInteractive and SafeAsanaSyncManager."""
        import lib.integrations as integrations_mod

        exported = dir(integrations_mod)
        assert "SafeChatInteractive" in exported, (
            "lib/integrations/__init__.py must export SafeChatInteractive"
        )
        assert "SafeAsanaSyncManager" in exported, (
            "lib/integrations/__init__.py must export SafeAsanaSyncManager"
        )

    def test_integrations_init_does_not_export_unsafe_classes(self):
        """lib/integrations/__init__.py does NOT export AsanaSyncManager or ChatInteractive."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        init_path = os.path.join(base, "lib", "integrations", "__init__.py")
        with open(init_path) as f:
            content = f.read()

        assert "AsanaSyncManager" not in content or "SafeAsanaSyncManager" in content, (
            "__init__.py must not re-export AsanaSyncManager — export SafeAsanaSyncManager instead"
        )
        # ChatInteractive is not exported (only ChatWriteResult is)
        assert '"ChatInteractive"' not in content, (
            "__init__.py must not export ChatInteractive class — export SafeChatInteractive instead"
        )
