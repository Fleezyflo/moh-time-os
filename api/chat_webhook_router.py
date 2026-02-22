"""
Chat Webhook Router — FastAPI endpoints for Google Chat webhook events.

Endpoints:
- POST /api/chat/webhook — receive Chat events (messages, reactions, slash commands)
- POST /api/chat/interactive — handle interactive card button clicks
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from lib.integrations.chat_commands import SlashCommandHandler
from lib.integrations.chat_interactive import ChatInteractive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Global instances
_slash_handler: SlashCommandHandler | None = None
_chat_client: ChatInteractive | None = None


def get_slash_handler() -> SlashCommandHandler:
    """Get or create global slash command handler."""
    global _slash_handler
    if _slash_handler is None:
        _slash_handler = SlashCommandHandler()
    return _slash_handler


def get_chat_client() -> ChatInteractive:
    """Get or create global chat client."""
    global _chat_client
    if _chat_client is None:
        _chat_client = ChatInteractive()
    return _chat_client


# Pydantic models for API requests
class ChatWebhookRequest(BaseModel):
    """Incoming Chat webhook event."""

    type: str = Field(
        ..., description="Event type: MESSAGE, ADDED_TO_SPACE, REMOVED_FROM_SPACE, etc."
    )
    message: dict | None = Field(default=None, description="Message data")
    space: dict | None = Field(default=None, description="Space info")
    user: dict | None = Field(default=None, description="User who triggered event")
    eventTime: str | None = Field(default=None, description="Event timestamp")


class InteractiveActionRequest(BaseModel):
    """Incoming interactive action (button click on card)."""

    type: str = Field(..., description="Should be 'CARD_CLICKED' or similar")
    message: dict | None = Field(default=None, description="Message containing the card")
    space: dict | None = Field(default=None, description="Space info")
    user: dict | None = Field(default=None, description="User who clicked")
    action: dict | None = Field(
        default=None, description="Action details with actionMethodName and parameters"
    )


@router.post("/webhook")
async def handle_webhook(request: ChatWebhookRequest) -> dict:
    """
    Receive and process Chat webhook events.

    Handles:
    - MESSAGE events (including slash commands starting with /)
    - ADDED_TO_SPACE events
    - REMOVED_FROM_SPACE events
    - Other Chat events

    For slash commands, routes to SlashCommandHandler.
    """
    try:
        event_type = request.type
        logger.info(f"Chat webhook: {event_type}")

        # Handle different event types
        if event_type == "ADDED_TO_SPACE":
            # Bot was added to a space
            space = request.space or {}
            logger.info(f"Bot added to space: {space.get('name', 'unknown')}")
            return {"text": "Thanks for adding me! Use /status or other commands."}

        elif event_type == "REMOVED_FROM_SPACE":
            # Bot was removed from a space
            space = request.space or {}
            logger.info(f"Bot removed from space: {space.get('name', 'unknown')}")
            return {"text": ""}

        elif event_type == "MESSAGE":
            # Message event (might be slash command)
            message = request.message or {}
            text = message.get("text", "").strip()

            if text.startswith("/"):
                # Slash command - route to handler
                handler = get_slash_handler()
                event_dict = {
                    "type": "MESSAGE",
                    "message": message,
                    "space": request.space or {},
                    "user": request.user or {},
                }
                response = handler.handle_event(event_dict)

                # Response can be text (dict with "text") or card (dict with "cardsV2")
                if isinstance(response, dict):
                    if "text" in response:
                        return response
                    else:
                        # Assume it's a card
                        return {
                            "cardsV2": [
                                {
                                    "cardId": "command_response",
                                    "card": response,
                                }
                            ]
                        }

                return response

            else:
                # Regular message - could trigger AI analysis, etc.
                # For now, just acknowledge
                logger.debug(f"Chat message: {text[:50]}")
                return {"text": ""}

        else:
            # Other event types (reactions, etc.)
            logger.debug(f"Unhandled event type: {event_type}")
            return {"text": ""}

    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return {"text": f"Error: {str(e)[:100]}"}


@router.post("/interactive")
async def handle_interactive_action(request: InteractiveActionRequest) -> dict:
    """
    Handle interactive card button clicks.

    When user clicks a button on a card, Google Chat sends an interactive action event.
    The action contains actionMethodName and parameters.
    """
    try:
        action = request.action or {}
        action_name = action.get("actionMethodName", "")
        parameters = action.get("parameters", [])

        logger.info(f"Interactive action: {action_name}")

        # Parse parameters into dict
        params_dict = {}
        if isinstance(parameters, list):
            for param in parameters:
                if isinstance(param, dict):
                    params_dict[param.get("key")] = param.get("value")
        elif isinstance(parameters, dict):
            params_dict = parameters

        # Route to appropriate handler based on actionMethodName
        if action_name == "APPROVE_ACTION":
            action_id = params_dict.get("action_id")
            if not action_id:
                return {"text": "Missing action_id parameter"}

            try:
                from lib.actions.action_framework import ActionFramework

                framework = ActionFramework()
                success = framework.approve_action(action_id, approved_by="chat_interactive")
                if success:
                    return {"text": f"✓ Action {action_id} approved"}
                else:
                    return {
                        "text": f"Could not approve action {action_id} (not found or not pending)"
                    }
            except Exception as e:
                logger.error(f"Error approving action {action_id}: {e}", exc_info=True)
                return {"text": f"Error approving action: {str(e)[:100]}"}

        elif action_name == "REJECT_ACTION":
            action_id = params_dict.get("action_id")
            reason = params_dict.get("reason", "No reason")
            if not action_id:
                return {"text": "Missing action_id parameter"}

            try:
                from lib.actions.action_framework import ActionFramework

                framework = ActionFramework()
                success = framework.reject_action(
                    action_id, rejected_by="chat_interactive", reason=reason
                )
                if success:
                    return {"text": f"✓ Action {action_id} rejected: {reason}"}
                else:
                    return {
                        "text": f"Could not reject action {action_id} (not found or not pending)"
                    }
            except Exception as e:
                logger.error(f"Error rejecting action {action_id}: {e}", exc_info=True)
                return {"text": f"Error rejecting action: {str(e)[:100]}"}

        else:
            logger.warning(f"Unknown interactive action: {action_name}")
            return {"text": f"Unknown action: {action_name}"}

    except Exception as e:
        logger.error(f"Error handling interactive action: {e}", exc_info=True)
        return {"text": f"Error: {str(e)[:100]}"}
