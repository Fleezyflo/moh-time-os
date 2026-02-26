"""
SlashCommandHandler - Google Chat slash command routing and built-in commands.

Registers command handlers, processes incoming Chat events, and generates help cards.
Includes built-in commands for status, tasks, signals, approvals, and briefings.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional
import sqlite3

logger = logging.getLogger(__name__)


class CardBuilder:
    """Utility for building Google Chat cards."""

    def __init__(self):
        """Initialize a new card."""
        self.sections = []
        self.header_section = None

    def header(
        self,
        title: str,
        subtitle: str | None = None,
        icon_url: str | None = None,
    ) -> "CardBuilder":
        """
        Add a header section to the card.

        Args:
            title: Header title
            subtitle: Optional subtitle
            icon_url: Optional icon URL

        Returns:
            Self for chaining
        """
        self.header_section = {
            "title": title,
        }
        if subtitle:
            self.header_section["subtitle"] = subtitle
        if icon_url:
            self.header_section["imageUrl"] = icon_url

        return self

    def section(
        self,
        header: str | None = None,
        widgets: list | None = None,
    ) -> "CardBuilder":
        """
        Add a section with optional header and widgets.

        Args:
            header: Optional section header text
            widgets: List of widget dicts

        Returns:
            Self for chaining
        """
        section = {}
        if header:
            section["header"] = header
        if widgets:
            section["widgets"] = widgets

        self.sections.append(section)
        return self

    def text_paragraph(self, text: str) -> dict:
        """
        Create a text paragraph widget.

        Args:
            text: Paragraph text (supports basic markdown)

        Returns:
            Widget dict
        """
        return {
            "textParagraph": {
                "text": text,
            }
        }

    def key_value(
        self,
        top_label: str,
        content: str,
        bottom_label: str | None = None,
    ) -> dict:
        """
        Create a key-value widget.

        Args:
            top_label: Label shown above the content
            content: Main content text
            bottom_label: Optional label shown below content

        Returns:
            Widget dict
        """
        kv = {
            "keyValue": {
                "topLabel": top_label,
                "content": content,
            }
        }
        if bottom_label:
            kv["keyValue"]["bottomLabel"] = bottom_label

        return kv

    def button(
        self,
        text: str,
        action_name: str,
        parameters: dict | None = None,
    ) -> dict:
        """
        Create a button widget.

        Args:
            text: Button display text
            action_name: Action name (e.g., "APPROVE", "REJECT")
            parameters: Dict of parameters to pass with action

        Returns:
            Widget dict
        """
        button = {
            "buttons": [
                {
                    "text": text,
                    "onClick": {
                        "action": {
                            "actionMethodName": action_name,
                        }
                    },
                }
            ]
        }

        if parameters:
            button["buttons"][0]["onClick"]["action"]["parameters"] = [
                {"key": k, "value": v} for k, v in parameters.items()
            ]

        return button

    def button_list(self, buttons: list) -> dict:
        """
        Create a horizontal button list widget.

        Args:
            buttons: List of button dicts (from button() method)

        Returns:
            Widget dict with all buttons
        """
        all_buttons = []
        for btn_widget in buttons:
            if "buttons" in btn_widget:
                all_buttons.extend(btn_widget["buttons"])

        return {"buttons": all_buttons}

    def divider(self) -> dict:
        """
        Create a divider widget.

        Returns:
            Widget dict
        """
        return {"divider": {}}

    def build(self) -> dict:
        """
        Assemble and return the final card JSON.

        Returns:
            Complete card dict ready for Chat API
        """
        card = {}

        if self.header_section:
            card["header"] = self.header_section

        if self.sections:
            card["sections"] = self.sections

        return card


class SlashCommandHandler:
    """Register and handle slash commands for Google Chat."""

    def __init__(self):
        """Initialize command handler."""
        self.commands = {}  # {command_name: {"handler": callable, "description": str, "usage": str}}
        self._register_builtins()

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str,
        usage: str,
    ) -> None:
        """
        Register a new slash command.

        Args:
            name: Command name (without /) e.g., "status"
            handler: Callable(event: dict, params: list) -> dict (response card or text)
            description: Short description of what command does
            usage: Usage string (e.g., "/status" or "/approve <action_id>")
        """
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "usage": usage,
        }
        logger.info(f"Registered command /{name}: {description}")

    def _register_builtins(self) -> None:
        """Register built-in commands."""
        self.register_command(
            "status",
            self._handle_status,
            "Portfolio status summary",
            "/status",
        )
        self.register_command(
            "tasks",
            self._handle_tasks,
            "List open tasks (optionally filtered by assignee)",
            "/tasks [assignee]",
        )
        self.register_command(
            "signal",
            self._handle_signal,
            "Latest signals for a client",
            "/signal <client>",
        )
        self.register_command(
            "approve",
            self._handle_approve,
            "Approve a pending action",
            "/approve <action_id>",
        )
        self.register_command(
            "reject",
            self._handle_reject,
            "Reject a pending action",
            "/reject <action_id> [reason]",
        )
        self.register_command(
            "brief",
            self._handle_brief,
            "Today's daily briefing summary",
            "/brief",
        )

    def _handle_status(self, event: dict, params: list) -> dict:
        """
        Handle /status command.

        Returns a card with portfolio status summary.
        """
        card = CardBuilder().header(
            title="Portfolio Status",
            subtitle="Overall summary",
        )

        card.section(
            header="Summary",
            widgets=[
                card.text_paragraph("Status summary would be populated from state store"),
                card.key_value("Tasks", "12 open"),
                card.key_value("Signals", "3 new"),
            ],
        )

        return card.build()

    def _handle_tasks(self, event: dict, params: list) -> dict:
        """
        Handle /tasks command with optional assignee filter.

        Params:
            [0]: optional assignee email or name
        """
        assignee = params[0] if params else None

        card = CardBuilder().header(
            title="Open Tasks",
            subtitle=f"Assigned to: {assignee}" if assignee else "All open tasks",
        )

        card.section(
            header="Tasks",
            widgets=[
                card.text_paragraph("Task list would be populated from state store"),
            ],
        )

        return card.build()

    def _handle_signal(self, event: dict, params: list) -> dict:
        """
        Handle /signal command to show latest signals for a client.

        Params:
            [0]: client name (required)
        """
        if not params:
            return {
                "sections": [
                    {"widgets": [{"textParagraph": {"text": "Usage: /signal <client_name>"}}]}
                ]
            }

        client = params[0]
        card = CardBuilder().header(
            title=f"Signals for {client}",
            subtitle="Latest signals",
        )

        card.section(
            header="Signals",
            widgets=[
                card.text_paragraph(f"Signals for client '{client}' would be populated"),
            ],
        )

        return card.build()

    def _handle_approve(self, event: dict, params: list) -> dict:
        """
        Handle /approve command to approve a pending action.

        Params:
            [0]: action_id (required)
        """
        if not params:
            return {
                "sections": [
                    {"widgets": [{"textParagraph": {"text": "Usage: /approve <action_id>"}}]}
                ]
            }

        action_id = params[0]
        sender = event.get("message", {}).get("sender", {})
        approved_by = sender.get("email", sender.get("displayName", "chat_user"))

        try:
            from lib.actions.action_framework import ActionFramework

            framework = ActionFramework()
            success = framework.approve_action(action_id, approved_by=approved_by)
            if success:
                msg = f"✓ Action {action_id} approved by {approved_by}"
            else:
                msg = f"Could not approve action {action_id} (not found or not in pending state)"
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            logger.error(f"Error approving action {action_id}: {e}", exc_info=True)
            msg = f"Error approving action: {str(e)[:100]}"

        return {"sections": [{"widgets": [{"textParagraph": {"text": msg}}]}]}

    def _handle_reject(self, event: dict, params: list) -> dict:
        """
        Handle /reject command to reject a pending action.

        Params:
            [0]: action_id (required)
            [1]: reason (optional)
        """
        if not params:
            return {
                "sections": [
                    {
                        "widgets": [
                            {"textParagraph": {"text": "Usage: /reject <action_id> [reason]"}}
                        ]
                    }
                ]
            }

        action_id = params[0]
        reason = " ".join(params[1:]) if len(params) > 1 else "No reason provided"
        sender = event.get("message", {}).get("sender", {})
        rejected_by = sender.get("email", sender.get("displayName", "chat_user"))

        try:
            from lib.actions.action_framework import ActionFramework

            framework = ActionFramework()
            success = framework.reject_action(action_id, rejected_by=rejected_by, reason=reason)
            if success:
                msg = f"✓ Action {action_id} rejected by {rejected_by}: {reason}"
            else:
                msg = f"Could not reject action {action_id} (not found or not in pending state)"
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            logger.error(f"Error rejecting action {action_id}: {e}", exc_info=True)
            msg = f"Error rejecting action: {str(e)[:100]}"

        return {"sections": [{"widgets": [{"textParagraph": {"text": msg}}]}]}

    def _handle_brief(self, event: dict, params: list) -> dict:
        """
        Handle /brief command to show today's briefing.

        Returns a card with briefing summary.
        """
        card = CardBuilder().header(
            title="Daily Briefing",
            subtitle="Today's summary",
        )

        card.section(
            header="Briefing",
            widgets=[
                card.text_paragraph("Daily briefing would be populated from intelligence system"),
            ],
        )

        return card.build()

    def handle_event(self, event: dict) -> dict:
        """
        Process an incoming Chat event and dispatch to appropriate handler.

        Event structure:
        {
            "type": "MESSAGE",
            "message": {
                "text": "/status",
                "thread": {...},
                "sender": {...},
            },
            "space": {...},
        }

        Returns:
            Response dict (card or error message)
        """
        # Extract message text and space
        message = event.get("message", {})
        text = message.get("text", "").strip()

        if not text.startswith("/"):
            return {
                "sections": [{"widgets": [{"textParagraph": {"text": "Commands start with /"}}]}]
            }

        # Parse command and parameters
        parts = text.split()
        command_str = parts[0][1:]  # Remove leading /
        params = parts[1:] if len(parts) > 1 else []

        # Look up command handler
        if command_str not in self.commands:
            return self.get_help_card()

        handler = self.commands[command_str]["handler"]

        try:
            response = handler(event, params)
            return response
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            logger.error(f"Error handling /{command_str}: {e}")
            return {
                "sections": [
                    {
                        "widgets": [
                            {"textParagraph": {"text": f"Error handling command: {str(e)[:100]}"}}
                        ]
                    }
                ]
            }

    def get_help_card(self) -> dict:
        """
        Generate help card listing all registered commands.

        Returns:
            Card dict with command reference
        """
        card = CardBuilder().header(
            title="Command Reference",
            subtitle="Available slash commands",
        )

        # Build widget list for each command
        widgets = []
        for name in sorted(self.commands.keys()):
            cmd = self.commands[name]
            widgets.append(
                card.key_value(
                    top_label=cmd["usage"],
                    content=cmd["description"],
                )
            )

        if widgets:
            card.section(header="Commands", widgets=widgets)

        return card.build()
