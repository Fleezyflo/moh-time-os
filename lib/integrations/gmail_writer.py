"""
Gmail Writer - Write-back integration for Gmail.

Handles creating drafts, sending emails, managing labels, and threading replies
via Google API using service account with domain-wide delegation.
"""

import base64
import logging
import os
import sqlite3
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

# Service account configuration
DEFAULT_SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
DEFAULT_USER = "molham@hrmny.co"


@dataclass
class GmailWriteResult:
    """Result of a Gmail write operation."""

    success: bool
    message_id: str | None = None
    draft_id: str | None = None
    data: dict | None = None
    error: str | None = None

    def __post_init__(self):
        """Validate result state."""
        if self.success and not self.message_id and not self.draft_id:
            logger.warning("Success result without message_id or draft_id")


class GmailWriter:
    """Write drafts, send emails, and manage labels in Gmail."""

    def __init__(
        self,
        credentials_path: str | None = None,
        delegated_user: str | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize GmailWriter.

        Args:
            credentials_path: Path to service account JSON. If None, uses env var or default.
            delegated_user: User to impersonate. If None, uses DEFAULT_USER.
            dry_run: If True, validate without sending.
        """
        self.credentials_path = credentials_path or os.environ.get(
            "GMAIL_SA_FILE", str(DEFAULT_SA_FILE)
        )
        self.delegated_user = delegated_user or os.environ.get("GMAIL_USER", DEFAULT_USER)
        self.dry_run = dry_run
        self._service = None

    def _get_service(self):
        """Get Gmail API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES
            )
            creds = creds.with_subject(self.delegated_user)
            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to get Gmail service: {e}"
            logger.error(error_msg)
            raise

    def _create_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to_message_id: str | None = None,
        html_body: str | None = None,
    ) -> str:
        """
        Create MIME message and return base64-encoded string.

        Args:
            to: Recipient email
            subject: Email subject
            body: Plain text body
            cc: List of CC'd emails
            bcc: List of BCC'd emails
            reply_to_message_id: Gmail message ID to reply to
            html_body: HTML body (if provided, used instead of plain text)

        Returns:
            Base64-encoded MIME message
        """
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        # Add reply-to header if replying to thread
        if reply_to_message_id:
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id

        # Attach bodies
        if html_body:
            # Add plain text first, then HTML (MIME best practice)
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        # Encode to base64
        return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to_message_id: str | None = None,
        html_body: str | None = None,
    ) -> GmailWriteResult:
        """
        Create a draft email.

        Args:
            to: Recipient email
            subject: Email subject
            body: Plain text body
            cc: List of CC'd emails
            bcc: List of BCC'd emails
            reply_to_message_id: Gmail message ID to reply to
            html_body: HTML body (optional)

        Returns:
            GmailWriteResult with draft_id on success
        """
        try:
            raw_message = self._create_message(
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                reply_to_message_id=reply_to_message_id,
                html_body=html_body,
            )

            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    draft_id="draft_dry_run",
                    data={"dry_run": True, "to": to, "subject": subject},
                )

            service = self._get_service()
            draft_body = {"message": {"raw": raw_message}}

            result = service.users().drafts().create(userId="me", body=draft_body).execute()

            draft_id = result.get("id")
            message_id = result.get("message", {}).get("id")

            logger.info(f"Created draft {draft_id} for {to}")
            return GmailWriteResult(
                success=True,
                draft_id=draft_id,
                message_id=message_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to create draft: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)

    def send_draft(self, draft_id: str) -> GmailWriteResult:
        """
        Send an existing draft.

        Args:
            draft_id: Gmail draft ID

        Returns:
            GmailWriteResult with message_id on success
        """
        try:
            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    message_id="msg_dry_run",
                    data={"dry_run": True, "draft_id": draft_id},
                )

            service = self._get_service()
            result = service.users().drafts().send(userId="me", id=draft_id).execute()

            message_id = result.get("id")
            logger.info(f"Sent draft {draft_id} as message {message_id}")
            return GmailWriteResult(
                success=True,
                message_id=message_id,
                draft_id=draft_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to send draft {draft_id}: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        html_body: str | None = None,
    ) -> GmailWriteResult:
        """
        Create and send an email in one step.

        Args:
            to: Recipient email
            subject: Email subject
            body: Plain text body
            cc: List of CC'd emails
            bcc: List of BCC'd emails
            html_body: HTML body (optional)

        Returns:
            GmailWriteResult with message_id on success
        """
        try:
            raw_message = self._create_message(
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                html_body=html_body,
            )

            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    message_id="msg_dry_run",
                    data={"dry_run": True, "to": to, "subject": subject},
                )

            service = self._get_service()
            message_body = {"raw": raw_message}

            result = service.users().messages().send(userId="me", body=message_body).execute()

            message_id = result.get("id")
            logger.info(f"Sent email to {to}: {subject}")
            return GmailWriteResult(
                success=True,
                message_id=message_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to send email to {to}: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)

    def add_label(
        self,
        message_id: str,
        label_ids: list[str],
    ) -> GmailWriteResult:
        """
        Add labels to a message.

        Args:
            message_id: Gmail message ID
            label_ids: List of label IDs to add

        Returns:
            GmailWriteResult
        """
        try:
            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    message_id=message_id,
                    data={"dry_run": True, "action": "add_label", "label_ids": label_ids},
                )

            service = self._get_service()
            result = (
                service.users()
                .messages()
                .modify(
                    userId="me",
                    id=message_id,
                    body={"addLabelIds": label_ids},
                )
                .execute()
            )

            logger.info(f"Added labels {label_ids} to message {message_id}")
            return GmailWriteResult(
                success=True,
                message_id=message_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to add labels to {message_id}: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)

    def remove_label(
        self,
        message_id: str,
        label_ids: list[str],
    ) -> GmailWriteResult:
        """
        Remove labels from a message.

        Args:
            message_id: Gmail message ID
            label_ids: List of label IDs to remove

        Returns:
            GmailWriteResult
        """
        try:
            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    message_id=message_id,
                    data={"dry_run": True, "action": "remove_label", "label_ids": label_ids},
                )

            service = self._get_service()
            result = (
                service.users()
                .messages()
                .modify(
                    userId="me",
                    id=message_id,
                    body={"removeLabelIds": label_ids},
                )
                .execute()
            )

            logger.info(f"Removed labels {label_ids} from message {message_id}")
            return GmailWriteResult(
                success=True,
                message_id=message_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to remove labels from {message_id}: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)

    def archive_message(self, message_id: str) -> GmailWriteResult:
        """
        Archive a message (remove from INBOX).

        Args:
            message_id: Gmail message ID

        Returns:
            GmailWriteResult
        """
        return self.remove_label(message_id, ["INBOX"])

    def reply_to_thread(
        self,
        thread_id: str,
        body: str,
        html_body: str | None = None,
    ) -> GmailWriteResult:
        """
        Reply to a thread (requires thread first message ID).

        Args:
            thread_id: Gmail thread ID
            body: Plain text body
            html_body: HTML body (optional)

        Returns:
            GmailWriteResult
        """
        try:
            if self.dry_run:
                return GmailWriteResult(
                    success=True,
                    message_id="msg_dry_run",
                    data={"dry_run": True, "thread_id": thread_id},
                )

            service = self._get_service()

            # Get thread details to find first message
            thread = (
                service.users().threads().get(userId="me", id=thread_id, format="minimal").execute()
            )

            message_ids = thread.get("messages", [])
            if not message_ids:
                return GmailWriteResult(
                    success=False,
                    error=f"Thread {thread_id} has no messages",
                )

            # Use first message in thread for In-Reply-To
            first_message_id = message_ids[0].get("id")

            # Get headers to extract To and Subject
            first_message = (
                service.users()
                .messages()
                .get(userId="me", id=first_message_id, format="full")
                .execute()
            )

            headers = first_message.get("payload", {}).get("headers", [])
            to_addr = ""
            subject = ""

            for header in headers:
                name = header.get("name", "").lower()
                if name == "from":
                    to_addr = header.get("value", "")
                elif name == "subject":
                    subject = header.get("value", "")

            if not to_addr:
                return GmailWriteResult(
                    success=False,
                    error=f"Could not extract From address from thread {thread_id}",
                )

            # Ensure subject has "Re:" prefix
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            raw_message = self._create_message(
                to=to_addr,
                subject=subject,
                body=body,
                reply_to_message_id=first_message_id,
                html_body=html_body,
            )

            message_body = {"raw": raw_message, "threadId": thread_id}
            result = service.users().messages().send(userId="me", body=message_body).execute()

            message_id = result.get("id")
            logger.info(f"Replied to thread {thread_id} with message {message_id}")
            return GmailWriteResult(
                success=True,
                message_id=message_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to reply to thread {thread_id}: {e}"
            logger.error(error_msg)
            return GmailWriteResult(success=False, error=error_msg)
