"""
Email notification channel — Delivers notifications via GmailWriter.

Routes digest-mode and email_urgent notifications through Gmail.
Follows the same pattern as GoogleChatChannel: async/sync send, dry_run support.

GAP-10-05: Email notification channel
"""

import logging

logger = logging.getLogger(__name__)


class EmailChannel:
    """
    Delivers notifications via GmailWriter.

    Supports both async and synchronous sending.
    Formats notifications as HTML email with subject line from title.
    """

    def __init__(
        self,
        credentials_path: str | None = None,
        delegated_user: str | None = None,
        default_recipient: str | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize EmailChannel.

        Args:
            credentials_path: Path to Gmail service account JSON.
            delegated_user: Gmail user to impersonate.
            default_recipient: Default email recipient. If None, sends to delegated_user.
            dry_run: If True, validate without sending.
        """
        self.dry_run = dry_run
        self._default_recipient = default_recipient
        self._writer = None
        self._credentials_path = credentials_path
        self._delegated_user = delegated_user

    def _get_writer(self):
        """Lazy-initialize GmailWriter."""
        if self._writer is not None:
            return self._writer

        from lib.integrations.gmail_writer import GmailWriter

        self._writer = GmailWriter(
            credentials_path=self._credentials_path,
            delegated_user=self._delegated_user,
            dry_run=self.dry_run,
        )
        return self._writer

    async def send(self, message: str, title: str | None = None, **kwargs) -> dict:
        """Send notification via email (async interface, delegates to sync)."""
        return self.send_sync(message, title=title, **kwargs)

    def send_sync(self, message: str, title: str | None = None, **kwargs) -> dict:
        """
        Send notification via email.

        Args:
            message: Notification body text.
            title: Email subject line. Defaults to "MOH Time OS Notification".
            **kwargs: priority (str), recipient (str).

        Returns:
            dict with keys: status, success, error?, message_id?
        """
        subject = title or "MOH Time OS Notification"
        priority = kwargs.get("priority", "normal")
        recipient = kwargs.get("recipient", self._default_recipient)

        if self.dry_run:
            logger.info("DRY RUN — Email: subject=%s, priority=%s", subject, priority)
            return {
                "status": "dry_run",
                "success": True,
                "payload": {"subject": subject, "body": message, "priority": priority},
            }

        try:
            writer = self._get_writer()
            recipient = recipient or writer.delegated_user

            # Format as HTML for richer display
            html_body = self._format_html(message, priority)

            # Add priority prefix to subject for urgent emails
            if priority in ("critical", "high"):
                subject = f"[{priority.upper()}] {subject}"

            result = writer.send_email(
                to=recipient,
                subject=subject,
                body_html=html_body,
            )

            if result.success:
                return {
                    "status": "sent",
                    "success": True,
                    "message_id": result.message_id,
                }
            return {
                "status": "error",
                "success": False,
                "error": result.error or "Email send failed",
            }

        except (ValueError, OSError) as e:
            logger.error("Email channel send failed: %s", e)
            return {"status": "error", "success": False, "error": str(e)}

    @staticmethod
    def _format_html(message: str, priority: str) -> str:
        """Format notification as simple HTML email body."""
        color = {
            "critical": "#dc2626",
            "high": "#ea580c",
            "normal": "#2563eb",
            "low": "#6b7280",
        }.get(priority, "#2563eb")

        # Convert markdown-style bold to HTML
        html_message = message.replace("**", "<strong>", 1)
        if "<strong>" in html_message:
            html_message = html_message.replace("**", "</strong>", 1)

        paragraphs = html_message.split("\n\n")
        body_html = "".join(f"<p>{p}</p>" for p in paragraphs if p.strip())

        return (
            f'<div style="font-family: -apple-system, sans-serif; max-width: 600px;">'
            f'<div style="border-left: 4px solid {color}; padding-left: 12px;">'
            f"{body_html}"
            f"</div>"
            f'<p style="color: #9ca3af; font-size: 12px; margin-top: 20px;">'
            f"Sent by MOH Time OS"
            f"</p></div>"
        )
