"""Tests for Google Chat webhook notification channel."""

import asyncio

from lib.notifier.channels.google_chat import GoogleChatChannel


class TestGoogleChatChannel:
    """Test GoogleChatChannel."""

    def test_import(self):
        """Channel can be imported."""
        assert GoogleChatChannel is not None

    def test_dry_run_text(self):
        """Dry run with plain text produces correct payload."""
        ch = GoogleChatChannel(webhook_url="https://example.com/webhook", dry_run=True)
        result = ch.send_sync("Hello world")

        assert result["status"] == "dry_run"
        assert result["success"] is True
        assert result["payload"] == {"text": "Hello world"}

    def test_dry_run_card(self):
        """Dry run with title produces Card v2 payload."""
        ch = GoogleChatChannel(webhook_url="https://example.com/webhook", dry_run=True)
        result = ch.send_sync("Body text", title="Alert Title")

        assert result["status"] == "dry_run"
        assert result["success"] is True
        payload = result["payload"]
        assert "cardsV2" in payload
        card = payload["cardsV2"][0]["card"]
        assert card["header"]["title"] == "Alert Title"
        assert card["sections"][0]["widgets"][0]["textParagraph"]["text"] == "Body text"

    def test_format_text_only(self):
        """Plain text format produces simple text payload."""
        ch = GoogleChatChannel(webhook_url="https://example.com", dry_run=True)
        payload = ch._format_payload("Hello")
        assert payload == {"text": "Hello"}

    def test_format_with_title(self):
        """Title format produces Card v2 payload."""
        ch = GoogleChatChannel(webhook_url="https://example.com", dry_run=True)
        payload = ch._format_payload("Body", title="Title")
        assert "cardsV2" in payload
        assert payload["cardsV2"][0]["cardId"] == "moh-notification"

    def test_send_sync_bad_url(self):
        """Bad webhook URL returns error result (not raises)."""
        ch = GoogleChatChannel(webhook_url="https://invalid.test.example/bad")
        result = ch.send_sync("test")
        assert result["status"] == "error"
        assert result["success"] is False
        assert "error" in result

    def test_async_dry_run(self):
        """Async dry run works."""
        ch = GoogleChatChannel(webhook_url="https://example.com", dry_run=True)
        result = asyncio.run(ch.send("Async test", title="Test"))
        assert result["status"] == "dry_run"
        assert result["success"] is True

    def test_extra_kwargs_accepted(self):
        """Extra kwargs don't cause errors."""
        ch = GoogleChatChannel(webhook_url="https://example.com", dry_run=True)
        result = ch.send_sync("test", priority="high", extra="ignored")
        assert result["status"] == "dry_run"


class TestNotificationEngineWithGoogleChat:
    """Test that NotificationEngine loads GoogleChat channel."""

    def test_engine_loads_gchat_from_config(self, tmp_path):
        """Engine loads Google Chat channel from config."""
        from unittest.mock import MagicMock

        from lib.notifier.engine import NotificationEngine

        store = MagicMock()
        config = {
            "channels": {
                "google_chat": {
                    "webhook_url": "https://chat.googleapis.com/test",
                    "dry_run": True,
                }
            }
        }

        engine = NotificationEngine(store=store, config=config)
        assert "google_chat" in engine.channels
        assert engine.channels["google_chat"].dry_run is True
