# TASK: Build Google Chat Webhook Notification Channel
> Brief: USER_READINESS | Phase: 4 | Sequence: 4.1 | Status: PENDING

## Context

Clawdbot has been removed (UR-1.2). The notification engine (`lib/notifier/engine.py`) needs a new default channel. Molham uses Google Chat — notifications should go there via webhook.

Google Chat webhooks accept POST requests with a JSON payload containing a `text` field (plain text or Card v2 JSON for rich formatting).

## Objective

Create a Google Chat webhook notification channel that integrates with the existing NotificationEngine.

## Instructions

1. Create `lib/notifier/channels/google_chat.py`:
   ```python
   """Google Chat webhook notification channel."""
   import httpx
   import logging
   from typing import Optional

   logger = logging.getLogger(__name__)

   class GoogleChatChannel:
       """Delivers notifications via Google Chat webhook."""

       def __init__(self, webhook_url: str, dry_run: bool = False):
           self.webhook_url = webhook_url
           self.dry_run = dry_run

       async def send(self, message: str, title: Optional[str] = None, **kwargs) -> dict:
           """Send notification to Google Chat space."""
           payload = self._format_payload(message, title)

           if self.dry_run:
               logger.info("DRY RUN — Google Chat payload: %s", payload)
               return {"status": "dry_run", "payload": payload}

           async with httpx.AsyncClient() as client:
               response = await client.post(
                   self.webhook_url,
                   json=payload,
                   timeout=10.0
               )
               response.raise_for_status()
               return {"status": "sent", "response": response.json()}

       def send_sync(self, message: str, title: Optional[str] = None, **kwargs) -> dict:
           """Synchronous send for non-async contexts."""
           payload = self._format_payload(message, title)

           if self.dry_run:
               logger.info("DRY RUN — Google Chat payload: %s", payload)
               return {"status": "dry_run", "payload": payload}

           response = httpx.post(
               self.webhook_url,
               json=payload,
               timeout=10.0
           )
           response.raise_for_status()
           return {"status": "sent", "response": response.json()}

       def _format_payload(self, message: str, title: Optional[str] = None) -> dict:
           """Format as Google Chat Card v2 or simple text."""
           if title:
               return {
                   "cardsV2": [{
                       "cardId": "moh-notification",
                       "card": {
                           "header": {"title": title},
                           "sections": [{"widgets": [{"textParagraph": {"text": message}}]}]
                       }
                   }]
               }
           return {"text": message}
   ```

2. Register in `lib/notifier/channels/__init__.py`:
   ```python
   from .google_chat import GoogleChatChannel
   __all__ = ["GoogleChatChannel"]
   ```

3. Wire into `lib/notifier/engine.py`:
   - Load Google Chat channel from config (webhook URL from env var or governance.yaml)
   - Set as default channel
   - Config key: `MOH_GCHAT_WEBHOOK_URL` env var

4. Update `config/governance.yaml`:
   - Add `google_chat` channel config with webhook_url placeholder
   - Set as default notification channel

5. Add dry-run test:
   ```python
   ch = GoogleChatChannel(webhook_url="https://example.com", dry_run=True)
   result = ch.send_sync("Test notification", title="MOH Time OS")
   assert result["status"] == "dry_run"
   ```

6. Write unit tests:
   - Test payload formatting (text-only and card)
   - Test dry-run mode
   - Test error handling on bad webhook URL

## Preconditions
- [ ] UR-1.2 complete (Clawdbot removed, engine ready for new channel)

## Validation
1. `from lib.notifier.channels.google_chat import GoogleChatChannel` succeeds
2. Dry-run send produces correctly formatted payload
3. NotificationEngine loads Google Chat as default channel
4. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] GoogleChatChannel created with async + sync send
- [ ] Card v2 formatting for titled notifications
- [ ] Dry-run mode works
- [ ] Wired as default channel in engine
- [ ] Tests written and passing

## Output
- Created: `lib/notifier/channels/google_chat.py`
- Modified: `lib/notifier/channels/__init__.py`
- Modified: `lib/notifier/engine.py`
- Modified: `config/governance.yaml`
- Created: `tests/test_google_chat_channel.py`
