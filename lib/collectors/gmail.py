"""
Gmail Collector - Pulls emails from Gmail via Service Account API.
Uses direct Google API with service account for domain-wide delegation.
"""

import base64
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")


class GmailCollector(BaseCollector):
    """Collects emails from Gmail using Service Account."""

    source_name = "gmail"
    target_table = "communications"

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None
        self._raw_data: dict[str, Any] | None = (
            None  # Store raw data for secondary table extraction
        )

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
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
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
                return str(h.get("value", ""))
        return ""

    def collect(self) -> dict[str, Any]:
        """Fetch emails from Gmail using Service Account API.

        Config options:
            lookback_days (int): Days to look back. Default 90.
            since (str): ISO date string for historical backfill (e.g. '2025-08-01').
                          Overrides lookback_days when provided.
            max_results (int): Max threads to fetch. Default 500. Set 0 for unlimited.
        """
        try:
            service = self._get_service()
            all_threads = []
            max_results = self.config.get("max_results", 500)
            since = self.config.get("since")  # ISO date for backfill

            # Build query — `since` overrides lookback_days
            if since:
                # Gmail `after:` uses YYYY/MM/DD format
                since_formatted = since.replace("-", "/")
                query = f"after:{since_formatted} -category:promotions -category:updates -category:social"
                self.logger.info(f"Gmail backfill mode: fetching since {since}")
            else:
                lookback_days = self.config.get("lookback_days", 90)
                query = f"newer_than:{lookback_days}d -category:promotions -category:updates -category:social"

            # Paginated thread listing
            page_token = None
            thread_refs = []
            while True:
                list_params = {
                    "userId": "me",
                    "maxResults": 100,
                    "q": query,
                }
                if page_token:
                    list_params["pageToken"] = page_token

                results = service.users().threads().list(**list_params).execute()
                thread_refs.extend(results.get("threads", []))

                page_token = results.get("nextPageToken")
                if not page_token:
                    break
                if max_results and len(thread_refs) >= max_results:
                    thread_refs = thread_refs[:max_results]
                    break

            self.logger.info(f"Found {len(thread_refs)} thread refs to fetch")

            # Fetch full thread details with all message data
            for ref in thread_refs[:max_results] if max_results else thread_refs:
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
                            "messages": messages,  # Store all messages for participant/attachment extraction
                            "subject": self._get_header(headers, "Subject"),
                            "from": self._get_header(headers, "From"),
                            "to": self._get_header(headers, "To"),
                            "date": self._get_header(headers, "Date"),
                            "snippet": thread.get("snippet", ""),
                            "body": self._extract_body(first_msg),
                            "labels": first_msg.get("labelIds", []),
                        }
                    )
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to fetch thread {ref['id']}: {e}")
                    continue

            self.logger.info(f"Collected {len(all_threads)} threads")
            return {"threads": all_threads}

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Gmail collection failed: {e}")
            return {"threads": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Gmail threads to canonical format."""
        transformed = []

        for thread in raw_data.get("threads", []):
            thread_id = thread.get("id")
            if not thread_id:
                continue

            messages = thread.get("messages", [])

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

            # Extract expanded data
            is_read = 0 if "UNREAD" in labels else 1
            is_starred = 1 if "STARRED" in labels else 0
            importance = self._extract_importance(messages)
            to_emails = self._extract_to_emails(messages)
            has_attachments, attachment_count = self._count_attachments(messages)

            # Collect all label names for label_ids column
            label_ids = self._extract_label_ids(labels) if isinstance(labels, list) else []

            transformed.append(
                {
                    "id": f"gmail_{thread_id}",
                    "source": "gmail",
                    "content_hash": content_hash,
                    "body_text_source": "api" if thread.get("body") else "snippet",
                    "source_id": thread_id,
                    "thread_id": thread_id,
                    "from_email": from_addr,
                    "to_emails": json.dumps(to_emails),
                    "subject": subject,
                    "snippet": (body_text or subject)[:500],
                    "body_text": body_text,
                    "priority": self._compute_priority(thread),
                    "requires_response": 1 if self._needs_response(thread) else 0,
                    "response_deadline": self._compute_response_deadline(thread),
                    "sentiment": self._analyze_sentiment(thread),
                    "labels": json.dumps(labels),
                    "is_read": is_read,
                    "is_starred": is_starred,
                    "importance": importance,
                    "has_attachments": has_attachments,
                    "attachment_count": attachment_count,
                    "label_ids": json.dumps(label_ids),
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

    def _extract_to_emails(self, messages: list) -> list[str]:
        """Extract all To addresses from all messages in thread."""
        to_emails = set()
        for msg in messages:
            headers = msg.get("payload", {}).get("headers", [])
            to_header = self._get_header(headers, "To")
            if to_header:
                # Parse comma-separated emails
                for addr in to_header.split(","):
                    email = self._extract_email(addr.strip())
                    if email:
                        to_emails.add(email)
        return sorted(to_emails)

    def _extract_importance(self, messages: list) -> str:
        """Extract importance/priority from headers or labels."""
        for msg in messages:
            headers = msg.get("payload", {}).get("headers", [])

            # Check Importance header
            importance_header = self._get_header(headers, "Importance")
            if importance_header:
                importance_lower = importance_header.lower()
                if "high" in importance_lower:
                    return "high"
                if "low" in importance_lower:
                    return "low"

            # Check X-Priority header
            priority_header = self._get_header(headers, "X-Priority")
            if priority_header:
                try:
                    priority_num = int(priority_header.split()[0])
                    if priority_num <= 2:
                        return "high"
                    if priority_num >= 4:
                        return "low"
                except (ValueError, IndexError):
                    pass

        return "normal"

    def _count_attachments(self, messages: list) -> tuple[int, int]:
        """Count total attachments across all messages.
        Returns (has_attachments: 0|1, attachment_count: int)
        """
        total = 0
        for msg in messages:
            payload = msg.get("payload", {})
            parts = payload.get("parts", [])
            for part in parts:
                if part.get("filename"):
                    total += 1
        return (1 if total > 0 else 0, total)

    def _extract_label_ids(self, labels: list) -> list[str]:
        """Convert label IDs to string list, filtering out system labels."""
        # Gmail system labels like UNREAD, STARRED are typically all caps
        # Keep all labels but they'll be stored as JSON
        return labels if isinstance(labels, list) else []

    def _transform_participants(self, thread_id: str, messages: list) -> list[dict]:
        """Transform participants from message headers.
        Returns list of dicts: {thread_id, message_id, role, email, name}
        """
        participants = []
        seen = set()  # Deduplicate across all messages in thread

        for msg in messages:
            msg_id = msg.get("id")
            headers = msg.get("payload", {}).get("headers", [])

            # From
            from_header = self._get_header(headers, "From")
            if from_header:
                email = self._extract_email(from_header)
                name = self._extract_name(from_header)
                key = ("from", email)
                if key not in seen:
                    participants.append(
                        {
                            "thread_id": thread_id,
                            "message_id": msg_id,
                            "role": "from",
                            "email": email,
                            "name": name,
                        }
                    )
                    seen.add(key)

            # To
            to_header = self._get_header(headers, "To")
            if to_header:
                for addr in to_header.split(","):
                    email = self._extract_email(addr.strip())
                    name = self._extract_name(addr.strip())
                    key = ("to", email)
                    if email and key not in seen:
                        participants.append(
                            {
                                "thread_id": thread_id,
                                "message_id": msg_id,
                                "role": "to",
                                "email": email,
                                "name": name,
                            }
                        )
                        seen.add(key)

            # Cc
            cc_header = self._get_header(headers, "Cc")
            if cc_header:
                for addr in cc_header.split(","):
                    email = self._extract_email(addr.strip())
                    name = self._extract_name(addr.strip())
                    key = ("cc", email)
                    if email and key not in seen:
                        participants.append(
                            {
                                "thread_id": thread_id,
                                "message_id": msg_id,
                                "role": "cc",
                                "email": email,
                                "name": name,
                            }
                        )
                        seen.add(key)

            # Bcc
            bcc_header = self._get_header(headers, "Bcc")
            if bcc_header:
                for addr in bcc_header.split(","):
                    email = self._extract_email(addr.strip())
                    name = self._extract_name(addr.strip())
                    key = ("bcc", email)
                    if email and key not in seen:
                        participants.append(
                            {
                                "thread_id": thread_id,
                                "message_id": msg_id,
                                "role": "bcc",
                                "email": email,
                                "name": name,
                            }
                        )
                        seen.add(key)

        return participants

    def _transform_attachments(self, thread_id: str, messages: list) -> list[dict]:
        """Transform attachments from message parts.
        Returns list of dicts: {thread_id, message_id, filename, mime_type, size_bytes, attachment_id}
        """
        attachments = []

        for msg in messages:
            msg_id = msg.get("id")
            payload = msg.get("payload", {})
            parts = payload.get("parts", [])

            for part in parts:
                filename = part.get("filename")
                if not filename:
                    continue

                attachments.append(
                    {
                        "thread_id": thread_id,
                        "message_id": msg_id,
                        "filename": filename,
                        "mime_type": part.get("mimeType", ""),
                        "size_bytes": part.get("body", {}).get("size", 0),
                        "attachment_id": part.get("body", {}).get("attachmentId"),
                    }
                )

        return attachments

    def _transform_labels(self, thread_id: str, label_ids: list) -> list[dict]:
        """Transform labels into rows for gmail_labels table.
        Returns list of dicts: {thread_id, label_id, label_name}
        """
        labels = []

        for label_id in label_ids:
            # label_id is typically like "Label_123" or system label like "UNREAD"
            # We'll use the ID as-is and infer name from common patterns
            label_name = self._infer_label_name(label_id)
            labels.append(
                {
                    "thread_id": thread_id,
                    "label_id": label_id,
                    "label_name": label_name,
                }
            )

        return labels

    def _extract_name(self, from_field: str) -> str:
        """Extract name from 'Name <email>' format."""
        # Handle format like "John Doe <john@example.com>"
        if "<" in from_field:
            name_part = from_field[: from_field.index("<")].strip()
            # Remove quotes if present
            name_part = name_part.strip('"')
            if name_part:
                return name_part
        return ""

    def _infer_label_name(self, label_id: str) -> str:
        """Infer human-readable label name from label ID."""
        # System labels like UNREAD, STARRED, etc are already readable
        if label_id.isupper() and "_" not in label_id:
            return label_id.replace("_", " ").title()
        # For custom labels like "Label_123", just return as-is
        # In production, would use Gmail API to fetch label names
        return label_id

    def sync(self) -> dict[str, Any]:
        """
        Full sync cycle: collect → transform → store to multiple tables.
        Overrides BaseCollector.sync to handle secondary tables:
        - Primary: communications
        - Secondary: gmail_participants, gmail_attachments, gmail_labels
        """
        from datetime import datetime

        cycle_start = datetime.now()

        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker is {self.circuit_breaker.state}. Skipping sync.")
            self.metrics["circuit_opens"] += 1
            return {
                "source": self.source_name,
                "success": False,
                "error": f"Circuit breaker {self.circuit_breaker.state}",
                "timestamp": datetime.now().isoformat(),
            }

        try:
            # Step 1: Collect from external source
            self.logger.info(f"Collecting from {self.source_name}")

            def collect_with_retry():
                return self.collect()

            try:
                from .resilience import retry_with_backoff

                self._raw_data = retry_with_backoff(
                    collect_with_retry, self.retry_config, self.logger
                )
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.error(f"Collect failed after retries: {e}")
                self.circuit_breaker.record_failure()
                self.store.update_sync_state(self.source_name, success=False, error=str(e))
                return {
                    "source": self.source_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            # Step 2: Transform to canonical format
            try:
                transformed = self.transform(self._raw_data or {})
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                self.logger.warning(f"Transform failed: {e}. Attempting partial success.")
                transformed = []
                self.metrics["partial_failures"] += 1

            self.logger.info(f"Transformed {len(transformed)} items")

            # Step 3: Store primary table (communications)
            stored_primary = self.store.insert_many(self.target_table, transformed)

            # Step 4: Store secondary tables - failures don't block primary
            secondary_stats: dict[str, int] = {}
            for thread in (self._raw_data or {}).get("threads", []):
                thread_id = thread.get("id")
                messages = thread.get("messages", [])
                label_ids = thread.get("labels", [])

                if not thread_id:
                    continue

                try:
                    # Store participants
                    participants = self._transform_participants(thread_id, messages)
                    if participants:
                        stored = self.store.insert_many("gmail_participants", participants)
                        secondary_stats["participants"] = (
                            secondary_stats.get("participants", 0) + stored
                        )
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store participants for {thread_id}: {e}")

                try:
                    # Store attachments
                    attachments = self._transform_attachments(thread_id, messages)
                    if attachments:
                        stored = self.store.insert_many("gmail_attachments", attachments)
                        secondary_stats["attachments"] = (
                            secondary_stats.get("attachments", 0) + stored
                        )
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store attachments for {thread_id}: {e}")

                try:
                    # Store labels
                    labels = self._transform_labels(thread_id, label_ids)
                    if labels:
                        stored = self.store.insert_many("gmail_labels", labels)
                        secondary_stats["labels"] = secondary_stats.get("labels", 0) + stored
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    self.logger.warning(f"Failed to store labels for {thread_id}: {e}")

            # Step 5: Update sync state and record success
            self.last_sync = datetime.now()
            self.store.update_sync_state(self.source_name, success=True, items=stored_primary)
            self.circuit_breaker.record_success()

            duration_ms = (datetime.now() - cycle_start).total_seconds() * 1000

            result = {
                "source": self.source_name,
                "success": True,
                "collected": len((self._raw_data or {}).get("threads", [])),
                "transformed": len(transformed),
                "stored_primary": stored_primary,
                "stored_secondary": secondary_stats,
                "duration_ms": duration_ms,
                "timestamp": self.last_sync.isoformat(),
            }

            self.logger.info(f"Sync completed: {result}")
            return result

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.circuit_breaker.record_failure()
            self.store.update_sync_state(self.source_name, success=False, error=str(e))
            return {
                "source": self.source_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
