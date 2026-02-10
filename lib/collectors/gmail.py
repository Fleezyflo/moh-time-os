"""
Gmail Collector - Pulls emails from Gmail via Service Account API.
Uses direct Google API with service account for domain-wide delegation.
"""

import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_USER = "molham@hrmny.co"


class GmailCollector(BaseCollector):
    """Collects emails from Gmail using Service Account."""

    source_name = "gmail"
    target_table = "communications"

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def _get_service(self, user: str = DEFAULT_USER):
        """Get Gmail API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(SA_FILE), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except Exception as e:
            self.logger.error(f"Failed to get Gmail service: {e}")
            raise

    def _extract_body(self, message: dict) -> str:
        """Extract body text from message."""
        payload = message.get("payload", {})

        # Try direct body
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            try:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
            except (ValueError, UnicodeDecodeError) as e:
                logger.debug(f"Could not decode body data: {e}")

        # Try parts
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    try:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    except (ValueError, UnicodeDecodeError) as e:
                        logger.debug(f"Could not decode part data: {e}")

        return ""

    def _get_header(self, headers: list[dict], name: str) -> str:
        """Get header value by name."""
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    def collect(self) -> dict[str, Any]:
        """Fetch emails from Gmail using Service Account API."""
        try:
            service = self._get_service()
            all_threads = []
            lookback_days = self.config.get("lookback_days", 90)
            max_results = self.config.get("max_results", 200)

            # Search for threads
            query = f"newer_than:{lookback_days}d -category:promotions -category:updates -category:social"
            results = (
                service.users()
                .threads()
                .list(userId="me", maxResults=min(max_results, 100), q=query)
                .execute()
            )

            thread_refs = results.get("threads", [])

            # Fetch full thread details
            for ref in thread_refs[:max_results]:
                try:
                    thread = (
                        service.users()
                        .threads()
                        .get(userId="me", id=ref["id"], format="full")
                        .execute()
                    )

                    messages = thread.get("messages", [])
                    if not messages:
                        continue

                    first_msg = messages[0]
                    headers = first_msg.get("payload", {}).get("headers", [])

                    all_threads.append(
                        {
                            "id": thread["id"],
                            "subject": self._get_header(headers, "Subject"),
                            "from": self._get_header(headers, "From"),
                            "to": self._get_header(headers, "To"),
                            "date": self._get_header(headers, "Date"),
                            "snippet": thread.get("snippet", ""),
                            "body": self._extract_body(first_msg),
                            "labels": first_msg.get("labelIds", []),
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to fetch thread {ref['id']}: {e}")
                    continue

            return {"threads": all_threads}

        except Exception as e:
            self.logger.error(f"Gmail collection failed: {e}")
            return {"threads": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Gmail threads to canonical format."""
        datetime.now().isoformat()
        transformed = []

        for thread in raw_data.get("threads", []):
            thread_id = thread.get("id")
            if not thread_id:
                continue

            # Skip promotional/update categories
            labels = thread.get("labels", [])
            if any(
                cat in labels
                for cat in [
                    "CATEGORY_PROMOTIONS",
                    "CATEGORY_UPDATES",
                    "CATEGORY_SOCIAL",
                ]
            ):
                continue

            from_addr = self._extract_email(thread.get("from", ""))
            subject = thread.get("subject", "(no subject)")
            body_text = thread.get("body", "") or thread.get("snippet", "")

            # Compute content hash
            content_hash = ""
            if body_text:
                content_hash = hashlib.sha256(body_text.encode()).hexdigest()[:16]

            transformed.append(
                {
                    "id": f"gmail_{thread_id}",
                    "source": "gmail",
                    "content_hash": content_hash,
                    "body_text_source": "api" if thread.get("body") else "snippet",
                    "source_id": thread_id,
                    "thread_id": thread_id,
                    "from_email": from_addr,
                    "to_emails": json.dumps([]),
                    "subject": subject,
                    "snippet": (body_text or subject)[:500],
                    "body_text": body_text,
                    "priority": self._compute_priority(thread),
                    "requires_response": 1 if self._needs_response(thread) else 0,
                    "response_deadline": self._compute_response_deadline(thread),
                    "sentiment": self._analyze_sentiment(thread),
                    "labels": json.dumps(labels),
                    "sensitivity": "",
                    "stakeholder_tier": "",
                    "processed": 0,
                    "created_at": self._parse_date(thread.get("date", "")),
                }
            )

        return transformed

    def _extract_email(self, from_field: str) -> str:
        """Extract email from 'Name <email>' format."""
        if "<" in from_field and ">" in from_field:
            start = from_field.index("<") + 1
            end = from_field.index(">")
            return from_field[start:end]
        return from_field

    def _parse_date(self, date_str: str) -> str:
        """Parse date string to ISO format."""
        if not date_str:
            return datetime.now().isoformat()

        # Try common formats
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M"]:
            try:
                dt = datetime.strptime(date_str.split(" (")[0].strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue

        return datetime.now().isoformat()

    def _compute_priority(self, thread: dict) -> int:
        """Compute email priority 0-100."""
        score = 50
        from_addr = self._extract_email(thread.get("from", "")).lower()
        labels = thread.get("labels", [])
        subject = thread.get("subject", "").lower()

        # Sender importance
        if "@hrmny" in from_addr:
            score += 25
        if "tax.gov" in from_addr or "government" in from_addr:
            score += 20

        # Label boosts
        if "IMPORTANT" in labels:
            score += 15
        if "STARRED" in labels:
            score += 10
        if "UNREAD" in labels:
            score += 5

        # Subject keywords
        if any(
            word in subject for word in ["urgent", "asap", "immediately", "deadline", "overdue"]
        ):
            score += 15

        return min(100, max(0, score))

    def _needs_response(self, thread: dict) -> bool:
        """Determine if email likely needs a response."""
        from_addr = self._extract_email(thread.get("from", "")).lower()
        subject = thread.get("subject", "").lower()
        snippet = thread.get("snippet", "").lower()

        # Skip automated emails
        no_reply = [
            "noreply",
            "no-reply",
            "donotreply",
            "notification@",
            "mailer-daemon",
        ]
        if any(p in from_addr for p in no_reply):
            return False

        # Response indicators
        indicators = [
            "please respond",
            "please reply",
            "awaiting",
            "let me know",
            "get back",
            "your thoughts",
            "action required",
            "confirm",
            "?",
        ]
        return any(ind in subject + " " + snippet for ind in indicators)

    def _compute_response_deadline(self, thread: dict) -> str:
        """Compute when a response should be sent."""
        if not self._needs_response(thread):
            return ""
        try:
            msg_date = datetime.fromisoformat(self._parse_date(thread.get("date", "")))
            deadline = msg_date + timedelta(hours=48)
            return deadline.isoformat()
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not compute response deadline: {e}")
            return ""

    def _analyze_sentiment(self, thread: dict) -> str:
        """Simple sentiment analysis."""
        subject = thread.get("subject", "").lower()
        if any(word in subject for word in ["urgent", "asap", "critical"]):
            return "urgent"
        if any(word in subject for word in ["fyi", "newsletter", "update"]):
            return "fyi"
        return "normal"
