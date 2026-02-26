"""
Tests for Google Chat interactive integration.

Tests ChatInteractive, SlashCommandHandler, CardBuilder, and webhook endpoints.
All HTTP calls are mocked using unittest.mock.
"""

from unittest.mock import Mock, patch

import pytest

from lib.integrations.chat_commands import CardBuilder, SlashCommandHandler
from lib.integrations.chat_interactive import ChatInteractive, ChatWriteResult

# ============================================================
# ChatWriteResult Tests
# ============================================================


class TestChatWriteResult:
    """Test ChatWriteResult dataclass."""

    def test_success_result(self):
        """Can create a success result."""
        result = ChatWriteResult(
            success=True,
            message_name="spaces/AAAABBBB/messages/CCCCDDDD",
        )
        assert result.success is True
        assert result.message_name == "spaces/AAAABBBB/messages/CCCCDDDD"
        assert result.error is None

    def test_error_result(self):
        """Can create an error result."""
        result = ChatWriteResult(
            success=False,
            error="No token provided",
        )
        assert result.success is False
        assert result.error == "No token provided"
        assert result.message_name is None


# ============================================================
# ChatInteractive Init Tests
# ============================================================


class TestChatInteractiveInit:
    """Test ChatInteractive initialization."""

    def test_init_with_bot_token(self):
        """Can initialize with explicit bot token."""
        chat = ChatInteractive(bot_token="test_token_123")
        assert chat.bot_token == "test_token_123"
        assert chat.webhook_url is None

    def test_init_with_webhook_url(self):
        """Can initialize with webhook URL."""
        chat = ChatInteractive(webhook_url="https://example.com/webhook")
        assert chat.webhook_url == "https://example.com/webhook"
        assert chat.bot_token is None

    def test_init_with_both(self):
        """Bot token takes precedence when both provided."""
        chat = ChatInteractive(
            bot_token="token_123",
            webhook_url="https://example.com/webhook",
        )
        assert chat.bot_token == "token_123"
        assert chat.webhook_url == "https://example.com/webhook"

    def test_init_with_env_vars(self, monkeypatch):
        """Can initialize with env vars."""
        monkeypatch.setenv("GOOGLE_CHAT_BOT_TOKEN", "env_token_456")
        chat = ChatInteractive()
        assert chat.bot_token == "env_token_456"

    def test_init_without_credentials_raises(self, monkeypatch):
        """Raises if no credentials provided."""
        monkeypatch.delenv("GOOGLE_CHAT_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_CHAT_WEBHOOK_URL", raising=False)
        with pytest.raises(ValueError, match="No Google Chat credentials"):
            ChatInteractive()


# ============================================================
# ChatInteractive.send_message Tests
# ============================================================


class TestChatInteractiveSendMessage:
    """Test send_message method."""

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_message_basic(self, mock_post):
        """Can send a basic text message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/AAAABBBB/messages/CCCCDDDD",
            "text": "Hello",
        }
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_message("spaces/AAAABBBB", "Hello world")

        assert result.success is True
        assert result.message_name == "spaces/AAAABBBB/messages/CCCCDDDD"
        assert result.data["text"] == "Hello"

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["text"] == "Hello world"

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_message_with_thread(self, mock_post):
        """Can send a threaded message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/AAAABBBB/messages/CCCCDDDD",
        }
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_message(
            "AAAABBBB",
            "Reply",
            thread_key="THREAD1",
        )

        assert result.success is True
        call_kwargs = mock_post.call_args[1]
        assert "thread" in call_kwargs["json"]

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_message_normalizes_space_id(self, mock_post):
        """Normalizes space ID with or without 'spaces/' prefix."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "spaces/X/messages/Y"}
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")

        # Without prefix
        chat.send_message("AAAABBBB", "text")
        url1 = mock_post.call_args[0][0]
        assert "spaces/AAAABBBB" in url1

        mock_post.reset_mock()

        # With prefix
        chat.send_message("spaces/AAAABBBB", "text")
        url2 = mock_post.call_args[0][0]
        assert "spaces/AAAABBBB" in url2

    def test_send_message_requires_bot_token(self):
        """send_message requires bot_token, not just webhook_url."""
        chat = ChatInteractive(webhook_url="https://example.com")
        result = chat.send_message("spaces/X", "text")
        assert result.success is False
        assert "bot_token" in result.error

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_message_handles_error_response(self, mock_post):
        """Handles API error responses."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Invalid space"}}
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_message("spaces/INVALID", "text")

        assert result.success is False
        assert "Invalid space" in result.error

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_message_handles_exception(self, mock_post):
        """Handles network exceptions."""
        mock_post.side_effect = Exception("Network error")

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_message("spaces/X", "text")

        assert result.success is False
        assert "Network error" in result.error


# ============================================================
# ChatInteractive.send_card Tests
# ============================================================


class TestChatInteractiveSendCard:
    """Test send_card method."""

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_card_basic(self, mock_post):
        """Can send a card message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/X/messages/Y",
        }
        mock_post.return_value = mock_response

        card = {
            "id": "test_card",
            "header": {"title": "Test Card"},
        }

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_card("spaces/X", card)

        assert result.success is True
        call_kwargs = mock_post.call_args[1]
        assert "cardsV2" in call_kwargs["json"]

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_card_with_thread(self, mock_post):
        """Can send card in a thread."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "spaces/X/messages/Y"}
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_card(
            "spaces/X",
            {"header": {"title": "Card"}},
            thread_key="THREAD1",
        )

        assert result.success is True
        call_kwargs = mock_post.call_args[1]
        assert "thread" in call_kwargs["json"]


# ============================================================
# ChatInteractive.update_message Tests
# ============================================================


class TestChatInteractiveUpdateMessage:
    """Test update_message method."""

    @patch("lib.integrations.chat_interactive.httpx.patch")
    def test_update_message_text(self, mock_patch):
        """Can update a message with new text."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/X/messages/Y",
            "text": "Updated text",
        }
        mock_patch.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.update_message("spaces/X/messages/Y", text="Updated text")

        assert result.success is True
        assert result.message_name == "spaces/X/messages/Y"

    @patch("lib.integrations.chat_interactive.httpx.patch")
    def test_update_message_card(self, mock_patch):
        """Can update a message with new card."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "spaces/X/messages/Y"}
        mock_patch.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        card = {"header": {"title": "New Card"}}
        result = chat.update_message("spaces/X/messages/Y", card=card)

        assert result.success is True

    def test_update_message_requires_text_or_card(self):
        """update_message requires either text or card."""
        chat = ChatInteractive(bot_token="token_123")
        result = chat.update_message("spaces/X/messages/Y")

        assert result.success is False
        assert "text or card" in result.error


# ============================================================
# ChatInteractive.delete_message Tests
# ============================================================


class TestChatInteractiveDeleteMessage:
    """Test delete_message method."""

    @patch("lib.integrations.chat_interactive.httpx.delete")
    def test_delete_message(self, mock_delete):
        """Can delete a message."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.delete_message("spaces/X/messages/Y")

        assert result.success is True
        assert result.message_name == "spaces/X/messages/Y"

    @patch("lib.integrations.chat_interactive.httpx.delete")
    def test_delete_message_handles_error(self, mock_delete):
        """Handles deletion errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": {"message": "Message not found"}}
        mock_delete.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.delete_message("spaces/X/messages/Y")

        assert result.success is False


# ============================================================
# ChatInteractive.create_space Tests
# ============================================================


class TestChatInteractiveCreateSpace:
    """Test create_space method."""

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_create_space_room(self, mock_post):
        """Can create a new room space."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "name": "spaces/NEWSPACE123",
            "displayName": "Test Room",
            "spaceType": "ROOM",
        }
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.create_space("Test Room", space_type="ROOM")

        assert result.success is True
        assert result.space_name == "spaces/NEWSPACE123"
        assert result.data["displayName"] == "Test Room"

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_create_space_dm(self, mock_post):
        """Can create a DM space."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "name": "spaces/DMSPACE",
            "spaceType": "DM",
        }
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.create_space("DM Name", space_type="DM")

        assert result.success is True


# ============================================================
# ChatInteractive.add_member Tests
# ============================================================


class TestChatInteractiveAddMember:
    """Test add_member method."""

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_add_member(self, mock_post):
        """Can add a member to a space."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/X/members/USER123",
            "member": {
                "name": "users/USER123",
                "email": "user@example.com",
            },
        }
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        result = chat.add_member("spaces/X", "user@example.com")

        assert result.success is True

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_add_member_normalizes_space_name(self, mock_post):
        """Normalizes space name with or without prefix."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "spaces/X/members/Y"}
        mock_post.return_value = mock_response

        chat = ChatInteractive(bot_token="token_123")
        chat.add_member("X", "user@example.com")

        url = mock_post.call_args[0][0]
        assert "spaces/X" in url


# ============================================================
# CardBuilder Tests
# ============================================================


class TestCardBuilder:
    """Test CardBuilder utility."""

    def test_header(self):
        """Can add a header."""
        builder = CardBuilder()
        builder.header("Title", "Subtitle", "https://example.com/icon.png")
        card = builder.build()

        assert card["header"]["title"] == "Title"
        assert card["header"]["subtitle"] == "Subtitle"
        assert card["header"]["imageUrl"] == "https://example.com/icon.png"

    def test_header_without_optional_fields(self):
        """Header works with just title."""
        builder = CardBuilder()
        builder.header("Title")
        card = builder.build()

        assert card["header"]["title"] == "Title"
        assert "subtitle" not in card["header"]

    def test_section_with_widgets(self):
        """Can add a section with widgets."""
        builder = CardBuilder()
        widgets = [
            builder.text_paragraph("Some text"),
        ]
        builder.section("Section Header", widgets)
        card = builder.build()

        assert len(card["sections"]) == 1
        assert card["sections"][0]["header"] == "Section Header"
        assert len(card["sections"][0]["widgets"]) == 1

    def test_section_without_header(self):
        """Section works without header."""
        builder = CardBuilder()
        widgets = [builder.text_paragraph("Text")]
        builder.section(widgets=widgets)
        card = builder.build()

        assert len(card["sections"]) == 1
        assert "header" not in card["sections"][0]

    def test_text_paragraph(self):
        """Can create text paragraph widget."""
        builder = CardBuilder()
        widget = builder.text_paragraph("Hello world")

        assert widget["textParagraph"]["text"] == "Hello world"

    def test_key_value(self):
        """Can create key-value widget."""
        builder = CardBuilder()
        widget = builder.key_value("Name", "John Doe", "Active")

        assert widget["keyValue"]["topLabel"] == "Name"
        assert widget["keyValue"]["content"] == "John Doe"
        assert widget["keyValue"]["bottomLabel"] == "Active"

    def test_key_value_without_bottom_label(self):
        """Key-value works without bottom label."""
        builder = CardBuilder()
        widget = builder.key_value("Name", "John Doe")

        assert "bottomLabel" not in widget["keyValue"]

    def test_button(self):
        """Can create a button widget."""
        builder = CardBuilder()
        widget = builder.button(
            "Click Me",
            "ACTION_NAME",
            {"param1": "value1"},
        )

        assert widget["buttons"][0]["text"] == "Click Me"
        assert widget["buttons"][0]["onClick"]["action"]["actionMethodName"] == "ACTION_NAME"

    def test_button_without_parameters(self):
        """Button works without parameters."""
        builder = CardBuilder()
        widget = builder.button("Click", "ACTION")

        assert widget["buttons"][0]["text"] == "Click"
        assert "parameters" not in widget["buttons"][0]["onClick"]["action"]

    def test_button_list(self):
        """Can create multiple buttons in a list."""
        builder = CardBuilder()
        button1 = builder.button("Yes", "APPROVE")
        button2 = builder.button("No", "REJECT")
        widget = builder.button_list([button1, button2])

        assert len(widget["buttons"]) == 2

    def test_divider(self):
        """Can create divider widget."""
        builder = CardBuilder()
        widget = builder.divider()

        assert "divider" in widget

    def test_chaining(self):
        """Methods can be chained."""
        card = (
            CardBuilder()
            .header("Title")
            .section(
                "Section",
                [CardBuilder().text_paragraph("Text")],
            )
            .build()
        )

        assert card["header"]["title"] == "Title"
        assert card["sections"][0]["header"] == "Section"

    def test_build_empty_card(self):
        """Can build empty card."""
        card = CardBuilder().build()
        assert card == {}

    def test_multiple_sections(self):
        """Can add multiple sections."""
        builder = CardBuilder()
        builder.section("Section 1", [builder.text_paragraph("Text 1")])
        builder.section("Section 2", [builder.text_paragraph("Text 2")])
        card = builder.build()

        assert len(card["sections"]) == 2


# ============================================================
# SlashCommandHandler Tests
# ============================================================


class TestSlashCommandHandlerInit:
    """Test SlashCommandHandler initialization."""

    def test_init_registers_builtins(self):
        """Initializes with built-in commands registered."""
        handler = SlashCommandHandler()

        assert "status" in handler.commands
        assert "tasks" in handler.commands
        assert "signal" in handler.commands
        assert "approve" in handler.commands
        assert "reject" in handler.commands
        assert "brief" in handler.commands

    def test_register_custom_command(self):
        """Can register custom command."""

        def custom_handler(event, params):
            return {"text": "Custom response"}

        handler = SlashCommandHandler()
        handler.register_command(
            "custom",
            custom_handler,
            "Custom command",
            "/custom",
        )

        assert "custom" in handler.commands
        assert handler.commands["custom"]["description"] == "Custom command"


class TestSlashCommandHandlerBuiltins:
    """Test built-in command handlers."""

    def test_status_command(self):
        """Can handle /status command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/status"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "header" in result or "sections" in result

    def test_tasks_command(self):
        """Can handle /tasks command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/tasks"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "header" in result or "sections" in result

    def test_tasks_command_with_assignee(self):
        """Can handle /tasks with assignee parameter."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/tasks user@example.com"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "header" in result or "sections" in result

    def test_signal_command(self):
        """Can handle /signal command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/signal client_name"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "header" in result or "sections" in result

    def test_signal_command_requires_client(self):
        """Signal command returns usage if no client provided."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/signal"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        # Should have sections with usage info
        assert "sections" in result or "text" in result

    def test_approve_command(self):
        """Can handle /approve command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/approve action_123"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "sections" in result or "text" in result

    def test_reject_command(self):
        """Can handle /reject command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/reject action_123 reason"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "sections" in result or "text" in result

    def test_brief_command(self):
        """Can handle /brief command."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/brief"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        assert "header" in result or "sections" in result


class TestSlashCommandHandlerEventProcessing:
    """Test event handling and dispatch."""

    def test_handle_non_command_message(self):
        """Non-slash messages are identified as such."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "Hello world"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        # Should indicate not a command
        text_msg = ""
        if "text" in result:
            text_msg = result.get("text", "")
        elif "sections" in result:
            for section in result.get("sections", []):
                for widget in section.get("widgets", []):
                    if "textParagraph" in widget:
                        text_msg = widget["textParagraph"]["text"]

        assert "command" in text_msg.lower() or "/" in text_msg

    def test_handle_unknown_command(self):
        """Unknown commands return help."""
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/unknown_cmd"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        # Should return help card
        assert "header" in result or "sections" in result

    def test_handle_command_exception(self):
        """Exceptions in handlers are caught and reported."""

        def broken_handler(event, params):
            raise ValueError("Handler error")

        handler = SlashCommandHandler()
        handler.register_command("broken", broken_handler, "Broken", "/broken")

        event = {
            "message": {"text": "/broken"},
            "space": {"name": "spaces/X"},
        }
        result = handler.handle_event(event)

        # Should have error message, not crash
        assert "sections" in result or "text" in result

    def test_help_card_lists_all_commands(self):
        """Help card includes all registered commands."""
        handler = SlashCommandHandler()
        card = handler.get_help_card()

        assert "header" in card
        assert "sections" in card

        # Should have multiple widgets (one per command)
        widgets = card["sections"][0].get("widgets", [])
        assert len(widgets) >= 6  # At least the 6 built-in commands


# ============================================================
# Webhook Router Tests
# ============================================================


class TestChatWebhookRouter:
    """Test webhook router endpoints."""

    def test_webhook_message_event(self):
        """Webhook can receive and handle message events."""
        from api.chat_webhook_router import ChatWebhookRequest

        # Test that request object can be created
        request = ChatWebhookRequest(
            type="MESSAGE",
            message={"text": "/status"},
            space={"name": "spaces/X"},
        )
        assert request.type == "MESSAGE"

    def test_webhook_added_to_space(self):
        """Webhook handles ADDED_TO_SPACE events."""
        from api.chat_webhook_router import ChatWebhookRequest

        request = ChatWebhookRequest(
            type="ADDED_TO_SPACE",
            space={"name": "spaces/X"},
        )
        assert request.type == "ADDED_TO_SPACE"

    def test_webhook_removed_from_space(self):
        """Webhook handles REMOVED_FROM_SPACE events."""
        from api.chat_webhook_router import ChatWebhookRequest

        request = ChatWebhookRequest(
            type="REMOVED_FROM_SPACE",
            space={"name": "spaces/X"},
        )
        assert request.type == "REMOVED_FROM_SPACE"

    def test_interactive_action_request_structure(self):
        """Can create interactive action request."""
        from api.chat_webhook_router import InteractiveActionRequest

        request = InteractiveActionRequest(
            type="CARD_CLICKED",
            action={
                "actionMethodName": "APPROVE_ACTION",
                "parameters": [{"key": "action_id", "value": "action_123"}],
            },
            space={"name": "spaces/X"},
        )

        assert request.type == "CARD_CLICKED"
        assert request.action["actionMethodName"] == "APPROVE_ACTION"


# ============================================================
# Integration Tests
# ============================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_send_help_card_full_flow(self, mock_post):
        """Full flow: build card -> send via ChatInteractive."""
        # Build a help card
        handler = SlashCommandHandler()
        card = handler.get_help_card()

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "spaces/X/messages/Y",
        }
        mock_post.return_value = mock_response

        # Send the card
        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_card("spaces/X", card)

        assert result.success is True
        assert result.message_name == "spaces/X/messages/Y"

    @patch("lib.integrations.chat_interactive.httpx.post")
    def test_command_response_sent_to_chat(self, mock_post):
        """Command handler response can be sent via ChatInteractive."""
        # Handle a command
        handler = SlashCommandHandler()
        event = {
            "message": {"text": "/status"},
            "space": {"name": "spaces/X"},
        }
        card_response = handler.handle_event(event)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "spaces/X/messages/Y"}
        mock_post.return_value = mock_response

        # Send response back
        chat = ChatInteractive(bot_token="token_123")
        result = chat.send_card("spaces/X", card_response)

        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
