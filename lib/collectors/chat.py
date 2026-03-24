"""
Chat Collector - Pulls messages, reactions, attachments, and metadata from Google Chat.

Expanded API coverage (~85%):
- Messages: basic fields + reactions, attachments, threading depth
- Spaces: metadata (display name, type, member count, threaded flag)
- Space Members: roster with display names, emails, and roles
- Reactions: emoji reactions on messages
- Attachments: file attachments with metadata
"""

import json
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any

from lib.credential_paths import google_sa_file

from .base import BaseCollector
from .resilience import COLLECTOR_ERRORS
from .result import CollectorResult, CollectorStatus, classify_error

logger = logging.getLogger(__name__)


def _sa_file():
    """Resolve SA file at call time to respect env overrides."""
    return google_sa_file()


# Service account configuration
SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
]
DEFAULT_USER = os.environ.get("DEFAULT_USER_EMAIL", "molham@hrmny.co")


class ChatCollector(BaseCollector):
    """Collects messages, reactions, attachments, space metadata, and members from Google Chat."""

    source_name = "chat"
    target_table = "chat_messages"
    OUTPUT_TABLES = [
        "chat_messages",
        "chat_reactions",
        "chat_attachments",
        "chat_space_metadata",
        "chat_space_members",
    ]

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def _get_service(self, user: str = DEFAULT_USER):
        """Get Chat API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(_sa_file()), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("chat", "v1", credentials=creds)
            return self._service
        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Failed to get Chat service: {e}")
            raise

    def _set_ipv4_only(self):
        """Force IPv4 to avoid IPv6 timeout issues."""
        original_getaddrinfo = socket.getaddrinfo

        def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
            return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = getaddrinfo_ipv4

    def collect(self) -> dict[str, Any]:
        """Fetch spaces, messages, reactions, attachments, metadata, and members from Google Chat."""
        self._set_ipv4_only()

        try:
            service = self._get_service()
            max_spaces = self.config.get("max_spaces", 50)
            max_messages_per_space = self.config.get("max_messages_per_space", 30)

            # Collect spaces
            spaces = self._list_spaces(service, max_spaces)
            self.logger.info(f"Collected {len(spaces)} spaces")

            all_messages = []
            space_metadata = {}
            space_members_by_space = {}

            # For each space, collect messages, metadata, and members
            for space in spaces:
                space_name = space.get("name", "")
                if not space_name:
                    continue

                # Collect space metadata
                space_metadata[space_name] = space

                # Collect messages
                messages = self._list_messages(service, space_name, max_messages_per_space)
                for msg in messages:
                    msg["_space_name"] = space_name
                    msg["_space_display_name"] = space.get("displayName", space_name)
                    msg["_space_type"] = space.get("spaceType", "UNKNOWN")
                all_messages.extend(messages)

                # Collect space members
                try:
                    members = self._list_members(service, space_name)
                    if members:
                        space_members_by_space[space_name] = members
                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to fetch members for {space_name}: {e}")

            return {
                "messages": all_messages,
                "spaces": spaces,
                "space_metadata": space_metadata,
                "space_members_by_space": space_members_by_space,
            }

        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Chat collection failed: {e}")
            raise  # Propagate to sync() — never return empty data as success

    def _list_spaces(self, service, max_spaces: int = 50) -> list[dict]:
        """List chat spaces."""
        try:
            old_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(30)
                results = service.spaces().list(pageSize=max_spaces).execute()
                return list(results.get("spaces", []))
            finally:
                socket.setdefaulttimeout(old_timeout)
        except COLLECTOR_ERRORS as e:
            self.logger.warning(f"Error listing spaces: {e}")
            raise

    def _list_messages(self, service, space_name: str, max_messages: int = 30) -> list[dict]:
        """List messages in a space."""
        try:
            results = (
                service.spaces().messages().list(parent=space_name, pageSize=max_messages).execute()
            )
            return list(results.get("messages", []))
        except COLLECTOR_ERRORS as e:
            self.logger.warning(f"Failed to fetch messages for {space_name}: {e}")
            raise

    def _list_members(self, service, space_name: str) -> list[dict]:
        """List members in a space."""
        try:
            results = service.spaces().members().list(parent=space_name, pageSize=100).execute()
            return list(results.get("memberships", []))
        except COLLECTOR_ERRORS as e:
            self.logger.warning(f"Failed to fetch members for {space_name}: {e}")
            raise

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform raw Chat API data to canonical format for chat_messages."""
        now = datetime.now(timezone.utc).isoformat()
        transformed = []

        for msg in raw_data.get("messages", []):
            msg_name = msg.get("name", "")
            if not msg_name:
                continue

            # Extract basic fields
            sender = msg.get("sender", {}) or {}
            sender_email = sender.get("name", "") if sender else ""
            sender_name = sender.get("displayName", sender_email) if sender else sender_email

            # Extract thread info
            thread = msg.get("thread", {})
            thread_id = thread.get("name", "")

            # Count reactions and attachments
            reaction_counts = msg.get("reactionCounts", [])
            reaction_count = sum(
                rc.get("count", 0) for rc in reaction_counts if isinstance(rc, dict)
            )

            attachments = msg.get("attachments", [])
            attachment_count = len(attachments) if attachments else 0
            has_attachment = 1 if attachment_count > 0 else 0

            # Extract text
            text = msg.get("text", "")

            # Get threading depth if available
            thread_reply_count = 0
            if thread_id:
                # Try to extract from thread or estimate from message structure
                thread_reply_count = self._get_thread_reply_count(msg)

            transformed.append(
                {
                    "id": msg_name,
                    "message_name": msg_name,
                    "space_name": msg.get("_space_name", ""),
                    "sender_name": sender_name,
                    "sender_email": sender_email,
                    "text": text,
                    "create_time": msg.get("createTime", now),
                    "raw_json": json.dumps(msg),
                    "thread_id": thread_id,
                    "thread_reply_count": thread_reply_count,
                    "reaction_count": reaction_count,
                    "has_attachment": has_attachment,
                    "attachment_count": attachment_count,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        return transformed

    def _get_thread_reply_count(self, msg: dict) -> int:
        """Try to get thread reply count from message."""
        # Google Chat API doesn't directly expose reply count, so estimate from structure
        # If message is in a thread (has thread_id), we assume reply count of 1 minimum
        # More sophisticated calculation would require additional API call
        thread = msg.get("thread", {})
        if thread.get("name"):
            return 1
        return 0

    def _transform_reactions(self, message_name: str, reactions: list) -> list[dict]:
        """Transform reactions to chat_reactions table rows."""
        rows: list[dict] = []

        if not reactions:
            return rows

        for reaction_count in reactions:
            if not isinstance(reaction_count, dict):
                continue

            emoji = reaction_count.get("emoji", {}).get("unicode", "")
            if not emoji:
                continue

            # Create one row per reaction (simplified; could expand to show per-user)
            rows.append(
                {
                    "message_id": message_name,
                    "emoji": emoji,
                    "user_id": None,
                    "user_name": None,
                }
            )

        return rows

    def _transform_attachments(self, message_name: str, attachments: list) -> list[dict]:
        """Transform attachments to chat_attachments table rows."""
        rows: list[dict] = []

        if not attachments:
            return rows

        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue

            name = attachment.get("name", "")
            if not name:
                continue

            rows.append(
                {
                    "message_id": message_name,
                    "name": name,
                    "content_type": attachment.get("contentType", ""),
                    "source_uri": attachment.get("source", {}).get("resourceName", ""),
                    "thumbnail_uri": attachment.get("thumbnailUri", ""),
                }
            )

        return rows

    def _transform_space_metadata(self, space: dict) -> dict:
        """Transform space to chat_space_metadata table row."""
        space_name = space.get("name", "")
        if not space_name:
            return {}

        return {
            "space_id": space_name,
            "display_name": space.get("displayName", space_name),
            "space_type": space.get("spaceType", "UNKNOWN"),
            "threaded": 1 if space.get("threaded") else 0,
            "member_count": space.get("memberCount", 0),
            "created_time": space.get("createTime", datetime.now(timezone.utc).isoformat()),
            "last_synced": datetime.now(timezone.utc).isoformat(),
        }

    def _transform_members(self, space_name: str, members: list) -> list[dict]:
        """Transform members to chat_space_members table rows."""
        rows: list[dict] = []

        if not members:
            return rows

        for member in members:
            if not isinstance(member, dict):
                continue

            member_name = member.get("name", "")
            if not member_name:
                continue

            # Extract display name and email from member object
            member_obj = member.get("member", {})
            display_name = member_obj.get("displayName", "")
            email = member_obj.get("email", "")
            member_type = member.get("memberType", "HUMAN")

            # Skip non-humans or service accounts if needed (optional)
            if member_type not in ("HUMAN", "BOT"):
                continue

            rows.append(
                {
                    "space_id": space_name,
                    "member_id": member_name,
                    "display_name": display_name,
                    "email": email,
                    "role": member.get("role", ""),
                }
            )

        return rows

    def sync(self) -> dict[str, Any]:
        """
        Override base sync to handle multi-table storage.

        Collects and stores:
        - chat_messages (main target)
        - chat_reactions, chat_attachments, chat_space_metadata, chat_space_members

        Returns CollectorResult.to_dict() with status indicating health.
        """
        from datetime import datetime

        cycle_start = datetime.now(timezone.utc)

        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker is {self.circuit_breaker.state}. Skipping sync.")
            self.metrics["circuit_opens"] += 1
            cr = CollectorResult(
                source=self.source_name,
                status=CollectorStatus.STALE,
                error=f"Circuit breaker {self.circuit_breaker.state}",
                error_type="circuit_breaker",
                circuit_breaker_state=self.circuit_breaker.state,
            )
            return cr.to_dict()

        try:
            # Step 1: Collect from external source
            self.logger.info(f"Collecting from {self.source_name}")

            try:
                raw_data = self.collect()
            except COLLECTOR_ERRORS as e:
                self.logger.error(f"Collect failed: {e}")
                self.circuit_breaker.record_failure()
                err_type = classify_error(e)
                self.store.update_sync_state(
                    self.source_name,
                    success=False,
                    error=str(e),
                    error_type=err_type,
                    status="failed",
                )
                cr = CollectorResult(
                    source=self.source_name,
                    status=CollectorStatus.FAILED,
                    error=str(e),
                    error_type=err_type,
                    circuit_breaker_state=self.circuit_breaker.state,
                    duration_ms=(datetime.now(timezone.utc) - cycle_start).total_seconds() * 1000,
                )
                return cr.to_dict()

            # Step 2: Transform to canonical format
            try:
                transformed_messages = self.transform(raw_data)
            except COLLECTOR_ERRORS as e:
                self.logger.warning(f"Transform failed: {e}. Attempting partial success.")
                transformed_messages = []
                self.metrics["partial_failures"] += 1

            self.logger.info(f"Transformed {len(transformed_messages)} messages")

            # Step 3: Store messages in main table
            stored_messages = self.store.insert_many(self.target_table, transformed_messages)

            # Step 4: Build typed result and store secondary tables
            cr = CollectorResult(
                source=self.source_name,
                status=CollectorStatus.SUCCESS,
                collected=len(raw_data.get("messages", [])),
                transformed=len(transformed_messages),
                stored=stored_messages,
                circuit_breaker_state=self.circuit_breaker.state,
            )

            # Reactions
            reactions_rows = []
            for msg in raw_data.get("messages", []):
                msg_name = msg.get("name", "")
                reactions = msg.get("reactionCounts", [])
                if msg_name and reactions:
                    rows = self._transform_reactions(msg_name, reactions)
                    reactions_rows.extend(rows)

            if reactions_rows:
                try:
                    stored = self.store.insert_many("chat_reactions", reactions_rows)
                    cr.add_secondary("reactions", stored=stored)
                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to store reactions: {e}")
                    cr.add_secondary("reactions", error=str(e))

            # Attachments
            attachments_rows = []
            for msg in raw_data.get("messages", []):
                msg_name = msg.get("name", "")
                attachments = msg.get("attachments", [])
                if msg_name and attachments:
                    rows = self._transform_attachments(msg_name, attachments)
                    attachments_rows.extend(rows)

            if attachments_rows:
                try:
                    stored = self.store.insert_many("chat_attachments", attachments_rows)
                    cr.add_secondary("attachments", stored=stored)
                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to store attachments: {e}")
                    cr.add_secondary("attachments", error=str(e))

            # Space metadata
            space_metadata_rows = []
            for space in raw_data.get("spaces", []):
                row = self._transform_space_metadata(space)
                if row:
                    space_metadata_rows.append(row)

            if space_metadata_rows:
                try:
                    stored = self.store.insert_many("chat_space_metadata", space_metadata_rows)
                    cr.add_secondary("space_metadata", stored=stored)
                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to store space_metadata: {e}")
                    cr.add_secondary("space_metadata", error=str(e))

            # Space members
            members_rows = []
            for space_name, members in raw_data.get("space_members_by_space", {}).items():
                rows = self._transform_members(space_name, members)
                members_rows.extend(rows)

            if members_rows:
                try:
                    stored = self.store.insert_many("chat_space_members", members_rows)
                    cr.add_secondary("space_members", stored=stored)
                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to store space_members: {e}")
                    cr.add_secondary("space_members", error=str(e))

            # Step 5: Finalize status, update sync state, record success
            self.last_sync = datetime.now(timezone.utc)
            cr.duration_ms = (datetime.now(timezone.utc) - cycle_start).total_seconds() * 1000
            cr.timestamp = self.last_sync.isoformat()
            cr.escalate_to_partial()
            self.store.update_sync_state(
                self.source_name,
                success=(cr.status == CollectorStatus.SUCCESS),
                items=stored_messages,
                status=cr.status.value,
            )
            self.circuit_breaker.record_success()

            return cr.to_dict()

        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.circuit_breaker.record_failure()
            err_type = classify_error(e)
            self.store.update_sync_state(
                self.source_name,
                success=False,
                error=str(e),
                error_type=err_type,
                status="failed",
            )
            cr = CollectorResult(
                source=self.source_name,
                status=CollectorStatus.FAILED,
                error=str(e),
                error_type=err_type,
                circuit_breaker_state=self.circuit_breaker.state,
                duration_ms=(datetime.now(timezone.utc) - cycle_start).total_seconds() * 1000,
            )
            return cr.to_dict()
