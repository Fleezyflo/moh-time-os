"""
Time OS V4 - Ingest Pipeline

Orchestrates ingestion from various sources into the V4 artifact system.
Wraps existing collectors and ensures proper artifact/identity/link creation.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

from .artifact_service import get_artifact_service
from .entity_link_service import get_entity_link_service
from .identity_service import get_identity_service

logger = logging.getLogger(__name__)


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class IngestPipeline:
    """
    Central pipeline for ingesting data into V4 artifact system.

    Flow:
    1. Receive raw data from collector
    2. Resolve identities for actors/participants
    3. Create artifact record
    4. Create entity links with confidence
    5. Generate excerpts for key content
    6. Queue Fix Data for ambiguous cases
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.artifact_svc = get_artifact_service()
        self.identity_svc = get_identity_service()
        self.link_svc = get_entity_link_service()

        # Load client/project recognizers
        self._load_recognizers()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _load_recognizers(self):
        """Load entity recognizers from database."""
        self.client_patterns = {}
        self.project_patterns = {}

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Load client aliases
            cursor.execute("""
                SELECT id, name, name_normalized, aliases_json
                FROM clients WHERE name IS NOT NULL
            """)
            for row in cursor.fetchall():
                client_id, name, normalized, aliases_json = row
                aliases = json.loads(aliases_json or "[]")
                patterns = [normalized] + [a.lower() for a in aliases]
                self.client_patterns[client_id] = {"name": name, "patterns": patterns}

            # Load project patterns
            cursor.execute("""
                SELECT id, name, name_normalized, client_id
                FROM projects WHERE name IS NOT NULL
            """)
            for row in cursor.fetchall():
                project_id, name, normalized, client_id = row
                self.project_patterns[project_id] = {
                    "name": name,
                    "pattern": normalized,
                    "client_id": client_id,
                }
        finally:
            conn.close()

    def _match_entity_in_text(self, text: str) -> list[tuple[str, str, float, str]]:
        """
        Match entities mentioned in text.

        Returns:
            List of (entity_type, entity_id, confidence, reason)
        """
        text_lower = text.lower()
        matches = []

        # Check clients
        for client_id, data in self.client_patterns.items():
            for pattern in data["patterns"]:
                if pattern and pattern in text_lower:
                    # Higher confidence for exact match, lower for partial
                    conf = 0.9 if pattern == data["patterns"][0] else 0.75
                    matches.append(("client", client_id, conf, f"Name match: {pattern}"))
                    break

        # Check projects
        for project_id, data in self.project_patterns.items():
            if data["pattern"] and data["pattern"] in text_lower:
                matches.append(("project", project_id, 0.85, f"Project name: {data['pattern']}"))

        return matches

    # ===========================================
    # Gmail Ingestion
    # ===========================================

    def ingest_gmail_message(self, message_data: dict) -> dict[str, Any]:
        """
        Ingest a Gmail message.

        Expected message_data:
        {
            'id': 'gmail_msg_id',
            'threadId': 'thread_id',
            'snippet': 'preview text',
            'subject': 'email subject',
            'from': 'sender@example.com',
            'to': ['recipient@example.com'],
            'cc': ['cc@example.com'],
            'date': '2024-01-15T10:30:00Z',
            'body': 'full body text',
            'labels': ['INBOX', 'UNREAD']
        }
        """
        msg_id = message_data.get("id")
        thread_id = message_data.get("threadId")

        # Resolve sender identity
        from_email = message_data.get("from", "")
        actor_profile = self.identity_svc.resolve_identity(
            "email", from_email, create_if_missing=True, source="gmail"
        )
        actor_id = actor_profile["profile_id"] if actor_profile else None

        # Create artifact
        result = self.artifact_svc.create_artifact(
            source="gmail",
            source_id=msg_id,
            artifact_type="message",
            occurred_at=message_data.get("date", datetime.now().isoformat()),
            payload=message_data,
            actor_person_id=actor_id,
            visibility_tags=message_data.get("labels", []),
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]

        # Create links
        links_created = []

        # Link to thread
        if thread_id:
            link = self.link_svc.create_link(
                artifact_id,
                "thread",
                thread_id,
                "headers",
                0.99,
                ["Gmail thread ID"],
                auto_confirm=True,
            )
            links_created.append(link)

        # Link to people (recipients)
        all_recipients = (message_data.get("to", []) or []) + (message_data.get("cc", []) or [])
        for email in all_recipients:
            if email:
                profile = self.identity_svc.resolve_identity(
                    "email", email, create_if_missing=True, source="gmail"
                )
                if profile:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "person",
                        profile["profile_id"],
                        "headers",
                        0.95,
                        ["Email recipient"],
                        auto_confirm=True,
                    )
                    links_created.append(link)

        # Match entities in subject/body
        searchable = f"{message_data.get('subject', '')} {message_data.get('snippet', '')}"
        entity_matches = self._match_entity_in_text(searchable)

        for entity_type, entity_id, confidence, reason in entity_matches:
            link = self.link_svc.create_link(
                artifact_id,
                entity_type,
                entity_id,
                "naming",
                confidence,
                [reason],
                auto_confirm=(confidence >= 0.85),
            )
            links_created.append(link)

        # Create excerpt from snippet
        if message_data.get("snippet"):
            self.artifact_svc.create_excerpt(
                artifact_id, message_data["snippet"], anchor_type="message_quote"
            )

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links_created),
            "actor_profile_id": actor_id,
        }

    # ===========================================
    # Calendar Ingestion
    # ===========================================

    def ingest_calendar_event(self, event_data: dict) -> dict[str, Any]:
        """
        Ingest a calendar event.

        Expected event_data:
        {
            'id': 'event_id',
            'summary': 'Meeting title',
            'description': 'Meeting notes',
            'start': '2024-01-15T10:00:00Z',
            'end': '2024-01-15T11:00:00Z',
            'organizer': {'email': 'organizer@example.com'},
            'attendees': [{'email': 'attendee@example.com', 'responseStatus': 'accepted'}],
            'location': 'Conference Room A'
        }
        """
        event_id = event_data.get("id")

        # Resolve organizer
        organizer_email = event_data.get("organizer", {}).get("email", "")
        actor_profile = (
            self.identity_svc.resolve_identity(
                "email", organizer_email, create_if_missing=True, source="calendar"
            )
            if organizer_email
            else None
        )
        actor_id = actor_profile["profile_id"] if actor_profile else None

        # Create artifact
        result = self.artifact_svc.create_artifact(
            source="calendar",
            source_id=event_id,
            artifact_type="calendar_event",
            occurred_at=event_data.get("start", datetime.now().isoformat()),
            payload=event_data,
            actor_person_id=actor_id,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links_created = []

        # Link to attendees
        for attendee in event_data.get("attendees", []):
            email = attendee.get("email")
            if email:
                profile = self.identity_svc.resolve_identity(
                    "email", email, create_if_missing=True, source="calendar"
                )
                if profile:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "person",
                        profile["profile_id"],
                        "participants",
                        0.95,
                        ["Calendar attendee"],
                        auto_confirm=True,
                    )
                    links_created.append(link)

        # Match entities in title/description
        searchable = f"{event_data.get('summary', '')} {event_data.get('description', '')}"
        entity_matches = self._match_entity_in_text(searchable)

        for entity_type, entity_id, confidence, reason in entity_matches:
            link = self.link_svc.create_link(
                artifact_id,
                entity_type,
                entity_id,
                "naming",
                confidence,
                [reason],
                auto_confirm=(confidence >= 0.85),
            )
            links_created.append(link)

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links_created),
            "actor_profile_id": actor_id,
        }

    # ===========================================
    # Asana Ingestion
    # ===========================================

    def ingest_asana_task(self, task_data: dict) -> dict[str, Any]:
        """
        Ingest an Asana task.

        Expected task_data:
        {
            'gid': 'task_gid',
            'name': 'Task name',
            'notes': 'Task description',
            'completed': false,
            'completed_at': null,
            'due_on': '2024-01-20',
            'assignee': {'gid': 'user_gid', 'email': 'user@example.com'},
            'projects': [{'gid': 'project_gid', 'name': 'Project Name'}],
            'created_at': '2024-01-15T10:00:00Z',
            'modified_at': '2024-01-16T14:30:00Z'
        }
        """
        task_gid = task_data.get("gid")

        # Resolve assignee
        assignee = task_data.get("assignee", {}) or {}
        assignee_email = assignee.get("email")
        actor_profile = None
        if assignee_email:
            actor_profile = self.identity_svc.resolve_identity(
                "email", assignee_email, create_if_missing=True, source="asana"
            )
        actor_id = actor_profile["profile_id"] if actor_profile else None

        # Create artifact
        result = self.artifact_svc.create_artifact(
            source="asana",
            source_id=task_gid,
            artifact_type="task",
            occurred_at=task_data.get(
                "modified_at", task_data.get("created_at", datetime.now().isoformat())
            ),
            payload=task_data,
            actor_person_id=actor_id,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links_created = []

        # Link to Asana projects
        for proj in task_data.get("projects", []):
            proj_gid = proj.get("gid")
            if proj_gid:
                # Try to find matching project in our DB
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT id FROM projects WHERE asana_project_id = ?",
                        (proj_gid,),
                    )
                    row = cursor.fetchone()
                    if row:
                        link = self.link_svc.create_link(
                            artifact_id,
                            "project",
                            row[0],
                            "headers",
                            0.95,
                            ["Asana project reference"],
                            auto_confirm=True,
                        )
                        links_created.append(link)
                finally:
                    conn.close()

        # Match entities in task name/notes
        searchable = f"{task_data.get('name', '')} {task_data.get('notes', '')}"
        entity_matches = self._match_entity_in_text(searchable)

        for entity_type, entity_id, confidence, reason in entity_matches:
            link = self.link_svc.create_link(
                artifact_id,
                entity_type,
                entity_id,
                "naming",
                confidence,
                [reason],
                auto_confirm=(confidence >= 0.85),
            )
            links_created.append(link)

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links_created),
            "actor_profile_id": actor_id,
        }

    # ===========================================
    # Xero Ingestion
    # ===========================================

    def ingest_xero_invoice(self, invoice_data: dict) -> dict[str, Any]:
        """
        Ingest a Xero invoice.

        Expected invoice_data:
        {
            'InvoiceID': 'uuid',
            'InvoiceNumber': 'INV-0001',
            'Type': 'ACCREC',
            'Contact': {'ContactID': 'uuid', 'Name': 'Client Name'},
            'DateString': '2024-01-15',
            'DueDateString': '2024-02-14',
            'Status': 'AUTHORISED',
            'Total': 5000.00,
            'AmountDue': 5000.00
        }
        """
        invoice_id = invoice_data.get("InvoiceID")

        # Create artifact
        result = self.artifact_svc.create_artifact(
            source="xero",
            source_id=invoice_id,
            artifact_type="invoice",
            occurred_at=invoice_data.get("DateString", datetime.now().isoformat()),
            payload=invoice_data,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links_created = []

        # Link to client via Xero contact
        contact = invoice_data.get("Contact", {}) or {}
        contact_id = contact.get("ContactID")
        if contact_id:
            conn = self._get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id FROM clients WHERE xero_contact_id = ?", (contact_id,))
                row = cursor.fetchone()
                if row:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "client",
                        row[0],
                        "headers",
                        0.98,
                        ["Xero contact ID match"],
                        auto_confirm=True,
                    )
                    links_created.append(link)
            finally:
                conn.close()

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links_created),
        }

    # ===========================================
    # Bulk Operations
    # ===========================================

    def backfill_from_events_raw(self, limit: int = 1000) -> dict[str, Any]:
        """
        Backfill artifacts from existing events_raw table.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        stats = {
            "processed": 0,
            "created": 0,
            "unchanged": 0,
            "errors": 0,
            "by_surface": {},
        }

        try:
            cursor.execute(
                """
                SELECT id, surface, source_ref, captured_at_ms, payload_json
                FROM events_raw
                ORDER BY captured_at_ms DESC
                LIMIT ?
            """,
                (limit,),
            )

            for row in cursor.fetchall():
                event_id, surface, source_ref, captured_at_ms, payload_json = row

                try:
                    payload = json.loads(payload_json)

                    # Map surface to artifact type
                    source_map = {
                        "gmail": "gmail",
                        "calendar": "calendar",
                        "tasks": "asana",
                        "chat": "gchat",
                    }
                    artifact_type_map = {
                        "gmail": "message",
                        "calendar": "calendar_event",
                        "tasks": "task",
                        "chat": "message",
                    }

                    source = source_map.get(surface, surface)
                    artifact_type = artifact_type_map.get(surface, "note")

                    occurred_at = (
                        datetime.fromtimestamp(captured_at_ms / 1000).isoformat()
                        if captured_at_ms
                        else datetime.now().isoformat()
                    )

                    result = self.artifact_svc.create_artifact(
                        source=source,
                        source_id=source_ref or event_id,
                        artifact_type=artifact_type,
                        occurred_at=occurred_at,
                        payload=payload,
                    )

                    stats["processed"] += 1
                    if result["status"] == "created":
                        stats["created"] += 1
                    else:
                        stats["unchanged"] += 1

                    stats["by_surface"][surface] = stats["by_surface"].get(surface, 0) + 1

                except Exception as e:
                    stats["errors"] += 1
                    logger.info(f"Error processing event {event_id}: {e}")
            return stats

        finally:
            conn.close()

    def get_pipeline_stats(self) -> dict[str, Any]:
        """Get combined stats from all services."""
        return {
            "artifacts": self.artifact_svc.get_stats(),
            "identities": self.identity_svc.get_stats(),
            "links": self.link_svc.get_stats(),
        }


# Singleton
_ingest_pipeline = None


def get_ingest_pipeline() -> IngestPipeline:
    global _ingest_pipeline
    if _ingest_pipeline is None:
        _ingest_pipeline = IngestPipeline()
    return _ingest_pipeline
