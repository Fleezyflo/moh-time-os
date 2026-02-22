"""
ChatInteractive - Google Chat write-back integration.

Handles sending messages, cards, managing spaces, and members via Google Chat API v1.
Uses httpx for HTTP calls with bot token or webhook URL.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)

GOOGLE_CHAT_API_BASE = "https://www.googleapis.com/chat/v1"


@dataclass
class ChatWriteResult:
    """Result of a Chat write operation."""

    success: bool
    message_name: str | None = None  # Resource name of created/updated message
    space_name: str | None = None  # Resource name of created space
    data: dict | None = None  # Full response data from Chat API
    error: str | None = None  # Error message if failed


class ChatInteractive:
    """Send messages, cards, and manage spaces/members in Google Chat."""

    def __init__(
        self,
        bot_token: str | None = None,
        webhook_url: str | None = None,
    ):
        """
        Initialize ChatInteractive.

        Args:
            bot_token: Google Chat bot token. If None, uses GOOGLE_CHAT_BOT_TOKEN env var.
            webhook_url: Webhook URL for incoming webhooks. If None, uses GOOGLE_CHAT_WEBHOOK_URL env var.
                If both provided, bot_token is preferred for API calls.
        """
        self.bot_token = bot_token or os.environ.get("GOOGLE_CHAT_BOT_TOKEN")
        self.webhook_url = webhook_url or os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

        if not self.bot_token and not self.webhook_url:
            raise ValueError(
                "No Google Chat credentials provided. "
                "Set GOOGLE_CHAT_BOT_TOKEN or GOOGLE_CHAT_WEBHOOK_URL env var."
            )

    def _get_headers(self) -> dict:
        """Get authorization headers for API calls."""
        if self.bot_token:
            return {"Authorization": f"Bearer {self.bot_token}"}
        return {}

    def send_message(
        self,
        space_id: str,
        text: str,
        thread_key: str | None = None,
    ) -> ChatWriteResult:
        """
        Send a text message to a space.

        Args:
            space_id: Space ID (e.g., "spaces/AAAABBBB" or just "AAAABBBB")
            text: Message text content
            thread_key: Thread ID for threaded messages (optional)

        Returns:
            ChatWriteResult with message_name on success, error on failure
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(
                success=False,
                error="send_message requires bot_token (webhook_url only works for webhooks)",
            )

        # Normalize space_id
        space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id

        try:
            payload = {
                "text": text,
            }
            if thread_key:
                payload["thread"] = {"name": f"{space_name}/threads/{thread_key}"}

            url = f"{GOOGLE_CHAT_API_BASE}/{space_name}/messages"
            params = {"key": self.bot_token}

            response = httpx.post(
                url,
                json=payload,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ChatWriteResult(
                    success=True,
                    message_name=data.get("name"),
                    data=data,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"send_message failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"send_message exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

    def send_card(
        self,
        space_id: str,
        card: dict,
        thread_key: str | None = None,
    ) -> ChatWriteResult:
        """
        Send a card message to a space.

        Args:
            space_id: Space ID (e.g., "spaces/AAAABBBB")
            card: Card JSON dict (follows Google Chat card format)
            thread_key: Thread ID for threaded messages (optional)

        Returns:
            ChatWriteResult with message_name on success
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(success=False, error="send_card requires bot_token")

        space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id

        try:
            payload = {
                "cardsV2": [
                    {
                        "cardId": card.get("id", "default"),
                        "card": card,
                    }
                ]
            }
            if thread_key:
                payload["thread"] = {"name": f"{space_name}/threads/{thread_key}"}

            url = f"{GOOGLE_CHAT_API_BASE}/{space_name}/messages"
            params = {"key": self.bot_token}

            response = httpx.post(
                url,
                json=payload,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ChatWriteResult(
                    success=True,
                    message_name=data.get("name"),
                    data=data,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"send_card failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"send_card exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

    def update_message(
        self,
        message_name: str,
        text: str | None = None,
        card: dict | None = None,
    ) -> ChatWriteResult:
        """
        Update an existing message (text or card).

        Args:
            message_name: Full message resource name (e.g., "spaces/X/messages/Y")
            text: New text content (if updating text message)
            card: New card JSON (if updating card message)

        Returns:
            ChatWriteResult with updated message_name
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(success=False, error="update_message requires bot_token")

        if not text and not card:
            return ChatWriteResult(success=False, error="Must provide text or card to update")

        try:
            payload = {}
            if text:
                payload["text"] = text
            if card:
                payload["cardsV2"] = [
                    {
                        "cardId": card.get("id", "default"),
                        "card": card,
                    }
                ]

            url = f"{GOOGLE_CHAT_API_BASE}/{message_name}"
            params = {"key": self.bot_token}

            response = httpx.patch(
                url,
                json=payload,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ChatWriteResult(
                    success=True,
                    message_name=data.get("name"),
                    data=data,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"update_message failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"update_message exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

    def delete_message(self, message_name: str) -> ChatWriteResult:
        """
        Delete a message.

        Args:
            message_name: Full message resource name

        Returns:
            ChatWriteResult indicating success/failure
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(success=False, error="delete_message requires bot_token")

        try:
            url = f"{GOOGLE_CHAT_API_BASE}/{message_name}"
            params = {"key": self.bot_token}

            response = httpx.delete(
                url,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 204):
                return ChatWriteResult(
                    success=True,
                    message_name=message_name,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"delete_message failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"delete_message exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

    def create_space(
        self,
        display_name: str,
        space_type: str = "ROOM",
    ) -> ChatWriteResult:
        """
        Create a new space.

        Args:
            display_name: Display name for the space
            space_type: "ROOM" (default), "DM", or "GROUP_DM"

        Returns:
            ChatWriteResult with space_name on success
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(success=False, error="create_space requires bot_token")

        try:
            payload = {
                "displayName": display_name,
                "spaceType": space_type,
            }

            url = f"{GOOGLE_CHAT_API_BASE}/spaces"
            params = {"key": self.bot_token}

            response = httpx.post(
                url,
                json=payload,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ChatWriteResult(
                    success=True,
                    space_name=data.get("name"),
                    data=data,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"create_space failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"create_space exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

    def add_member(
        self,
        space_name: str,
        member_email: str,
    ) -> ChatWriteResult:
        """
        Add a member to a space.

        Args:
            space_name: Space resource name (e.g., "spaces/AAAABBBB")
            member_email: Email address of member to add

        Returns:
            ChatWriteResult with membership info on success
        """
        if not HAS_HTTPX:
            return ChatWriteResult(success=False, error="httpx not installed")

        if not self.bot_token:
            return ChatWriteResult(success=False, error="add_member requires bot_token")

        space_resource = (
            f"spaces/{space_name}" if not space_name.startswith("spaces/") else space_name
        )

        try:
            payload = {
                "member": {
                    "name": member_email,  # Will be resolved by API
                    "type": "HUMAN",
                }
            }

            url = f"{GOOGLE_CHAT_API_BASE}/{space_resource}/members"
            params = {"key": self.bot_token}

            response = httpx.post(
                url,
                json=payload,
                params=params,
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ChatWriteResult(
                    success=True,
                    data=data,
                )

            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                error_msg += f": {response.text[:100]}"

            logger.error(f"add_member failed: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"add_member exception: {error_msg}")
            return ChatWriteResult(
                success=False,
                error=error_msg,
            )
