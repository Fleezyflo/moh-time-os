"""Google Chat webhook notification channel."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class GoogleChatChannel:
    """Delivers notifications via Google Chat webhook.

    Supports both async and synchronous sending.
    Card v2 formatting for titled notifications, plain text otherwise.
    """

    def __init__(self, webhook_url: str, dry_run: bool = False):
        self.webhook_url = webhook_url
        self.dry_run = dry_run

    async def send(self, message: str, title: str | None = None, **kwargs) -> dict:
        """Send notification to Google Chat space (async)."""
        payload = self._format_payload(message, title)

        if self.dry_run:
            logger.info("DRY RUN — Google Chat payload: %s", payload)
            return {"status": "dry_run", "success": True, "payload": payload}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                return {
                    "status": "sent",
                    "success": True,
                    "response": response.json(),
                    "message_id": response.json().get("name", ""),
                }
        except httpx.HTTPStatusError as e:
            logger.error("Google Chat HTTP error: %s", e)
            return {"status": "error", "success": False, "error": str(e)}
        except httpx.RequestError as e:
            logger.error("Google Chat request error: %s", e)
            return {"status": "error", "success": False, "error": str(e)}

    def send_sync(self, message: str, title: str | None = None, **kwargs) -> dict:
        """Synchronous send for non-async contexts."""
        payload = self._format_payload(message, title)

        if self.dry_run:
            logger.info("DRY RUN — Google Chat payload: %s", payload)
            return {"status": "dry_run", "success": True, "payload": payload}

        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            return {
                "status": "sent",
                "success": True,
                "response": response.json(),
                "message_id": response.json().get("name", ""),
            }
        except httpx.HTTPStatusError as e:
            logger.error("Google Chat HTTP error: %s", e)
            return {"status": "error", "success": False, "error": str(e)}
        except httpx.RequestError as e:
            logger.error("Google Chat request error: %s", e)
            return {"status": "error", "success": False, "error": str(e)}

    def _format_payload(self, message: str, title: str | None = None) -> dict:
        """Format as Google Chat Card v2 or simple text."""
        if title:
            return {
                "cardsV2": [
                    {
                        "cardId": "moh-notification",
                        "card": {
                            "header": {"title": title},
                            "sections": [{"widgets": [{"textParagraph": {"text": message}}]}],
                        },
                    }
                ]
            }
        return {"text": message}
