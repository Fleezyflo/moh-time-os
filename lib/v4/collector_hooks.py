"""
Time OS V4 - Collector Hooks

Hooks into existing collectors to populate the V4 artifact system.
Call these after each collector sync completes.
"""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

from .artifact_service import decrypt_blob_payload, get_artifact_service
from .entity_link_service import get_entity_link_service
from .identity_service import get_identity_service

log = logging.getLogger("moh_time_os.v4.hooks")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class CollectorHooks:
    """
    Hooks to integrate existing collectors with V4 artifact system.

    Usage:
        from lib.v4.collector_hooks import hooks

        # After Asana sync
        hooks.on_asana_task_synced(task_data)
        hooks.on_asana_project_synced(project_data)

        # After Xero sync
        hooks.on_xero_invoice_synced(invoice_data)

        # After Gmail fetch
        hooks.on_gmail_message_fetched(message_data)
    """

    def __init__(self):
        self.artifact_svc = get_artifact_service()
        self.identity_svc = get_identity_service()
        self.link_svc = get_entity_link_service()
        self._load_entity_patterns()

    def _get_conn(self):
        return sqlite3.connect(DB_PATH, timeout=30)

    def _load_entity_patterns(self):
        """Load client/project/task patterns for entity matching."""
        self.client_patterns = {}
        self.project_patterns = {}
        self.task_patterns = {}

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Load clients
            cursor.execute("""
                SELECT id, name, name_normalized, aliases_json, identity_profile_id
                FROM clients WHERE name IS NOT NULL
            """)
            for row in cursor.fetchall():
                cid, name, normalized, aliases_json, profile_id = row
                aliases = json.loads(aliases_json or "[]")
                patterns = [normalized] + [a.lower() for a in aliases if a]
                self.client_patterns[cid] = {
                    "name": name,
                    "patterns": [p for p in patterns if p],
                    "profile_id": profile_id,
                }

            # Load projects
            cursor.execute("""
                SELECT id, name, name_normalized, client_id, asana_project_id
                FROM projects WHERE name IS NOT NULL
            """)
            for row in cursor.fetchall():
                pid, name, normalized, client_id, asana_pid = row
                self.project_patterns[pid] = {
                    "name": name,
                    "pattern": normalized,
                    "client_id": client_id,
                    "asana_project_id": asana_pid,
                }

            # Load tasks from items table
            cursor.execute("""
                SELECT id, what, source_ref, client_id, project_id, status
                FROM items
                WHERE what IS NOT NULL
                  AND status NOT IN ('done', 'resolved', 'completed', 'cancelled')
            """)
            for row in cursor.fetchall():
                task_id, what, source_ref, client_id, project_id, status = row
                # Normalize task name for matching
                name_normalized = what.lower().strip() if what else ""
                # Extract keywords (3+ char words)
                keywords = [w for w in re.split(r"\W+", name_normalized) if len(w) >= 3]
                self.task_patterns[task_id] = {
                    "name": what,
                    "name_normalized": name_normalized,
                    "keywords": keywords,
                    "asana_gid": source_ref,  # Asana task GID
                    "client_id": client_id,
                    "project_id": project_id,
                }

            log.info(
                f"Loaded patterns: {len(self.client_patterns)} clients, "
                f"{len(self.project_patterns)} projects, {len(self.task_patterns)} tasks"
            )
        finally:
            conn.close()

    def _match_client_in_text(self, text: str) -> list[tuple]:
        """Match client mentions in text. Returns [(client_id, confidence, reason)]"""
        if not text:
            return []
        text_lower = text.lower()
        matches = []

        for client_id, data in self.client_patterns.items():
            for pattern in data["patterns"]:
                if pattern and len(pattern) > 2 and pattern in text_lower:
                    conf = 0.9 if pattern == data["patterns"][0] else 0.75
                    matches.append((client_id, conf, f"Pattern match: {pattern}"))
                    break

        return matches

    def _match_project_by_asana_gid(self, asana_gid: str) -> str | None:
        """Find project ID by Asana GID."""
        for pid, data in self.project_patterns.items():
            if data.get("asana_project_id") == asana_gid:
                return pid
        return None

    def _match_task_in_text(
        self, text: str, min_keyword_matches: int = 2
    ) -> list[tuple[str, float, str]]:
        """
        Match task mentions in text using keyword overlap.
        Returns [(task_id, confidence, reason)]

        Matching strategies:
        1. Exact task name match (high confidence)
        2. Keyword overlap (medium confidence based on match ratio)
        3. Asana GID in URL (very high confidence)
        """
        if not text:
            return []

        text_lower = text.lower()
        text_keywords = {w for w in re.split(r"\W+", text_lower) if len(w) >= 3}
        matches = []
        seen_tasks = set()

        for task_id, data in self.task_patterns.items():
            if task_id in seen_tasks:
                continue

            task_name = data.get("name_normalized", "")
            task_keywords = set(data.get("keywords", []))

            # Strategy 1: Exact or near-exact name match
            if task_name and len(task_name) > 5 and task_name in text_lower:
                matches.append((task_id, 0.92, f"Task name match: {data['name'][:50]}"))
                seen_tasks.add(task_id)
                continue

            # Strategy 2: Keyword overlap
            if task_keywords and text_keywords:
                overlap = task_keywords & text_keywords
                if len(overlap) >= min_keyword_matches:
                    # Confidence based on overlap ratio
                    ratio = len(overlap) / len(task_keywords)
                    if ratio >= 0.5:  # At least half the keywords match
                        conf = min(0.85, 0.5 + ratio * 0.4)
                        matches.append(
                            (
                                task_id,
                                conf,
                                f"Keyword match ({len(overlap)}/{len(task_keywords)}): {', '.join(list(overlap)[:3])}",
                            )
                        )
                        seen_tasks.add(task_id)

        # Sort by confidence descending, return top matches
        matches.sort(key=lambda x: -x[1])
        return matches[:5]  # Limit to top 5 to avoid over-linking

    def _match_task_by_asana_gid(self, asana_gid: str) -> str | None:
        """Find task ID by Asana GID."""
        for task_id, data in self.task_patterns.items():
            if data.get("asana_gid") == asana_gid:
                return task_id
        return None

    def _extract_asana_task_gids(self, text: str) -> list[str]:
        """
        Extract Asana task GIDs from email content.

        Patterns detected:
        - app.asana.com/0/PROJECT_GID/TASK_GID
        - View task links from Asana notifications
        - Asana task URLs in email body
        """
        gids = []

        # Pattern 1: Full Asana task URLs
        # https://app.asana.com/0/1234567890/9876543210
        url_pattern = r"app\.asana\.com/0/\d+/(\d+)"
        gids.extend(re.findall(url_pattern, text))

        # Pattern 2: Standalone GIDs that look like Asana IDs (16+ digit numbers)
        # Only if text mentions Asana
        if "asana" in text.lower():
            gid_pattern = r"\b(\d{16,})\b"
            potential_gids = re.findall(gid_pattern, text)
            # Verify these look like Asana GIDs (start with 12)
            for gid in potential_gids:
                if gid.startswith("12") and gid not in gids:
                    gids.append(gid)

        return list(set(gids))  # Dedupe

    # ===========================================
    # Asana Hooks
    # ===========================================

    def on_asana_task_synced(self, task_data: dict) -> dict[str, Any]:
        """
        Called when an Asana task is synced.

        task_data should contain:
        - gid: Asana task GID
        - name: Task name
        - notes: Task description
        - completed: bool
        - due_on: Due date
        - assignee: {gid, email, name}
        - projects: [{gid, name}]
        - created_at, modified_at
        """
        gid = task_data.get("gid")
        if not gid:
            return {"status": "error", "error": "No task GID"}

        # Resolve assignee identity
        actor_id = None
        assignee = task_data.get("assignee") or {}
        if assignee.get("email"):
            profile = self.identity_svc.resolve_identity(
                "email", assignee["email"], create_if_missing=True, source="asana"
            )
            if profile:
                actor_id = profile["profile_id"]
                # Also add asana_id claim
                if assignee.get("gid"):
                    self.identity_svc.add_claim(
                        profile["profile_id"],
                        "asana_id",
                        assignee["gid"],
                        "asana",
                        0.99,
                    )

        # Create artifact
        occurred_at = (
            task_data.get("modified_at")
            or task_data.get("created_at")
            or datetime.now().isoformat()
        )

        result = self.artifact_svc.create_artifact(
            source="asana",
            source_id=gid,
            artifact_type="task",
            occurred_at=occurred_at,
            payload=task_data,
            actor_person_id=actor_id,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links = []

        # Link to projects
        for proj in task_data.get("projects", []):
            proj_gid = proj.get("gid")
            if proj_gid:
                our_project_id = self._match_project_by_asana_gid(proj_gid)
                if our_project_id:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "project",
                        our_project_id,
                        "headers",
                        0.98,
                        ["Asana project GID match"],
                        auto_confirm=True,
                    )
                    links.append(link)

                    # Also link to client via project
                    proj_data = self.project_patterns.get(our_project_id, {})
                    if proj_data.get("client_id"):
                        link = self.link_svc.create_link(
                            artifact_id,
                            "client",
                            proj_data["client_id"],
                            "rules",
                            0.95,
                            ["Via project-client relationship"],
                            auto_confirm=True,
                        )
                        links.append(link)

        # Match clients in task name/notes
        searchable = f"{task_data.get('name', '')} {task_data.get('notes', '')}"
        for client_id, conf, reason in self._match_client_in_text(searchable):
            link = self.link_svc.create_link(
                artifact_id,
                "client",
                client_id,
                "naming",
                conf,
                [reason],
                auto_confirm=(conf >= 0.85),
            )
            links.append(link)

        # Create excerpt from task name
        if task_data.get("name"):
            self.artifact_svc.create_excerpt(
                artifact_id,
                task_data["name"],
                anchor_type="json_path",
                anchor_start="$.name",
                anchor_end="$.name",
            )

        log.debug(f"Asana task {gid}: artifact={artifact_id}, links={len(links)}")
        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links),
        }

    def on_asana_project_synced(self, project_data: dict) -> dict[str, Any]:
        """Called when an Asana project is synced."""
        gid = project_data.get("gid")
        if not gid:
            return {"status": "error", "error": "No project GID"}

        result = self.artifact_svc.create_artifact(
            source="asana",
            source_id=f"project_{gid}",
            artifact_type="project_update",
            occurred_at=project_data.get("modified_at", datetime.now().isoformat()),
            payload=project_data,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links = []

        # Link to client if provided
        client_id = project_data.get("client_id")
        if client_id:
            link = self.link_svc.create_link(
                artifact_id,
                "client",
                client_id,
                "headers",
                0.95,
                ["Project client_id reference"],
                auto_confirm=True,
            )
            links.append(link)

        # Link to the project itself
        # Find our internal project ID
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, client_id FROM projects WHERE asana_project_id = ? OR id = ?",
                (gid, gid),
            )
            row = cursor.fetchone()
            if row:
                project_id, proj_client_id = row
                link = self.link_svc.create_link(
                    artifact_id,
                    "project",
                    project_id,
                    "headers",
                    0.98,
                    ["Direct project reference"],
                    auto_confirm=True,
                )
                links.append(link)

                # Also link to client via project if not already linked
                if proj_client_id and proj_client_id != client_id:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "client",
                        proj_client_id,
                        "rules",
                        0.90,
                        ["Via project-client relationship"],
                        auto_confirm=True,
                    )
                    links.append(link)
        finally:
            conn.close()

        # Also try text matching for client mentions
        project_name = project_data.get("name", "")
        for cid, conf, reason in self._match_client_in_text(project_name):
            if cid != client_id:  # Don't duplicate
                link = self.link_svc.create_link(
                    artifact_id,
                    "client",
                    cid,
                    "naming",
                    conf,
                    [reason],
                    auto_confirm=(conf >= 0.85),
                )
                links.append(link)

        return {
            "artifact_id": result.get("artifact_id"),
            "status": result["status"],
            "links_created": len(links),
        }

    # ===========================================
    # Xero Hooks
    # ===========================================

    def on_xero_invoice_synced(self, invoice_data: dict) -> dict[str, Any]:
        """
        Called when a Xero invoice is synced.

        invoice_data should contain:
        - InvoiceID
        - InvoiceNumber
        - Contact: {ContactID, Name}
        - DateString, DueDateString
        - Status
        - Total, AmountDue
        """
        invoice_id = invoice_data.get("InvoiceID")
        if not invoice_id:
            return {"status": "error", "error": "No InvoiceID"}

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
        links = []

        # Link to client via Xero contact
        contact = invoice_data.get("Contact", {}) or {}
        contact_id = contact.get("ContactID")
        if contact_id:
            conn = self._get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id FROM clients WHERE xero_contact_id = ?", (contact_id,)
                )
                row = cursor.fetchone()
                if row:
                    link = self.link_svc.create_link(
                        artifact_id,
                        "client",
                        row[0],
                        "headers",
                        0.99,
                        ["Xero ContactID match"],
                        auto_confirm=True,
                    )
                    links.append(link)
            finally:
                conn.close()

        # Create excerpt with invoice summary
        summary = f"Invoice {invoice_data.get('InvoiceNumber', 'N/A')}: {invoice_data.get('Total', 0)} ({invoice_data.get('Status', 'Unknown')})"
        self.artifact_svc.create_excerpt(
            artifact_id, summary, anchor_type="message_quote"
        )

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links),
        }

    def on_xero_payment_synced(self, payment_data: dict) -> dict[str, Any]:
        """Called when a Xero payment is synced."""
        payment_id = payment_data.get("PaymentID")
        if not payment_id:
            return {"status": "error", "error": "No PaymentID"}

        result = self.artifact_svc.create_artifact(
            source="xero",
            source_id=payment_id,
            artifact_type="payment",
            occurred_at=payment_data.get("Date", datetime.now().isoformat()),
            payload=payment_data,
        )

        return {"artifact_id": result.get("artifact_id"), "status": result["status"]}

    # ===========================================
    # Gmail Hooks
    # ===========================================

    def on_gmail_message_fetched(self, message_data: dict) -> dict[str, Any]:
        """
        Called when a Gmail message is fetched.

        message_data should contain:
        - id: Gmail message ID
        - threadId
        - subject, snippet
        - from, to, cc
        - date
        - body (optional)
        - labels
        """
        msg_id = message_data.get("id")
        if not msg_id:
            return {"status": "error", "error": "No message ID"}

        # Resolve sender
        actor_id = None
        from_email = message_data.get("from", "")
        if from_email:
            profile = self.identity_svc.resolve_identity(
                "email", from_email, create_if_missing=True, source="gmail"
            )
            if profile:
                actor_id = profile["profile_id"]

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
        links = []

        # Link to thread
        thread_id = message_data.get("threadId")
        if thread_id:
            link = self.link_svc.create_link(
                artifact_id,
                "thread",
                thread_id,
                "headers",
                0.99,
                ["Gmail threadId"],
                auto_confirm=True,
            )
            links.append(link)

        # Link to recipients
        all_recipients = (message_data.get("to", []) or []) + (
            message_data.get("cc", []) or []
        )
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
                    links.append(link)

        # Match clients in subject/body
        searchable = (
            f"{message_data.get('subject', '')} {message_data.get('snippet', '')}"
        )
        for client_id, conf, reason in self._match_client_in_text(searchable):
            link = self.link_svc.create_link(
                artifact_id,
                "client",
                client_id,
                "naming",
                conf,
                [reason],
                auto_confirm=(conf >= 0.85),
            )
            links.append(link)

        # ========================================
        # TASK LINKING (V4 enhancement)
        # ========================================

        # Include body in searchable text for task matching
        body_text = (
            message_data.get("body", "") or message_data.get("body_text", "") or ""
        )
        full_searchable = f"{searchable} {body_text}"

        # Strategy 1: Extract Asana task GIDs from URLs in email
        asana_gids = self._extract_asana_task_gids(full_searchable)
        linked_task_ids = set()

        for gid in asana_gids:
            task_id = self._match_task_by_asana_gid(gid)
            if task_id and task_id not in linked_task_ids:
                link = self.link_svc.create_link(
                    artifact_id,
                    "task",
                    task_id,
                    "rules",
                    0.98,
                    [f"Asana GID in email: {gid}"],
                    auto_confirm=True,
                )
                links.append(link)
                linked_task_ids.add(task_id)
                log.debug(
                    f"Linked email {msg_id} to task {task_id} via Asana GID {gid}"
                )

        # Strategy 2: Keyword/name matching for tasks
        for task_id, conf, reason in self._match_task_in_text(full_searchable):
            if task_id not in linked_task_ids:
                link = self.link_svc.create_link(
                    artifact_id,
                    "task",
                    task_id,
                    "naming",
                    conf,
                    [reason],
                    auto_confirm=(conf >= 0.85),
                )
                links.append(link)
                linked_task_ids.add(task_id)
                log.debug(f"Linked email {msg_id} to task {task_id}: {reason}")

        # Create excerpt
        if message_data.get("snippet"):
            self.artifact_svc.create_excerpt(
                artifact_id, message_data["snippet"], anchor_type="message_quote"
            )

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links),
        }

    # ===========================================
    # Calendar Hooks
    # ===========================================

    def on_calendar_event_synced(self, event_data: dict) -> dict[str, Any]:
        """
        Called when a calendar event is synced.

        event_data should contain:
        - id: Event ID
        - summary: Event title
        - description
        - start, end
        - organizer: {email}
        - attendees: [{email, responseStatus}]
        """
        event_id = event_data.get("id")
        if not event_id:
            return {"status": "error", "error": "No event ID"}

        # Resolve organizer
        actor_id = None
        organizer = event_data.get("organizer", {}) or {}
        if organizer.get("email"):
            profile = self.identity_svc.resolve_identity(
                "email", organizer["email"], create_if_missing=True, source="calendar"
            )
            if profile:
                actor_id = profile["profile_id"]

        start = event_data.get("start", {})
        occurred_at = (
            start.get("dateTime") or start.get("date") or datetime.now().isoformat()
        )

        result = self.artifact_svc.create_artifact(
            source="calendar",
            source_id=event_id,
            artifact_type="calendar_event",
            occurred_at=occurred_at,
            payload=event_data,
            actor_person_id=actor_id,
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links = []

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
                    links.append(link)

        # Match clients in event title/description
        searchable = (
            f"{event_data.get('summary', '')} {event_data.get('description', '')}"
        )
        for client_id, conf, reason in self._match_client_in_text(searchable):
            link = self.link_svc.create_link(
                artifact_id,
                "client",
                client_id,
                "naming",
                conf,
                [reason],
                auto_confirm=(conf >= 0.85),
            )
            links.append(link)

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links),
        }

    # ===========================================
    # Bulk Sync
    # ===========================================

    def sync_all_from_db(self) -> dict[str, Any]:
        """
        Sync artifacts from existing database tables.
        Used for initial backfill or catch-up.
        Creates proper entity links using internal IDs.
        """
        stats = {
            "projects": {"processed": 0, "created": 0},
            "tasks": {"processed": 0, "created": 0, "links_created": 0},
            "clients": {"processed": 0, "created": 0},
            "invoices": {"processed": 0, "created": 0},
        }

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Sync projects
            cursor.execute("""
                SELECT id, name, asana_project_id, client_id, status,
                       start_date, target_end_date, created_at, updated_at
                FROM projects WHERE name IS NOT NULL
            """)
            for row in cursor.fetchall():
                (
                    pid,
                    name,
                    asana_pid,
                    client_id,
                    status,
                    start,
                    end,
                    created,
                    updated,
                ) = row
                try:
                    result = self.on_asana_project_synced(
                        {
                            "gid": asana_pid or pid,
                            "name": name,
                            "client_id": client_id,
                            "status": status,
                            "start_date": start,
                            "target_end_date": end,
                            "created_at": created,
                            "modified_at": updated,
                        }
                    )
                    stats["projects"]["processed"] += 1
                    if result.get("status") == "created":
                        stats["projects"]["created"] += 1
                except Exception as e:
                    log.warning(f"Failed to sync project {pid}: {e}")

            # Sync items (tasks) - with proper linking via internal IDs
            cursor.execute("""
                SELECT i.id, i.what, i.source_type, i.owner, i.project_id, i.status,
                       i.due, i.source_captured_at, i.client_id, i.context_client_name,
                       p.client_id as project_client_id
                FROM items i
                LEFT JOIN projects p ON i.project_id = p.id
                WHERE i.what IS NOT NULL
                LIMIT 1000
            """)
            for row in cursor.fetchall():
                (
                    iid,
                    title,
                    domain,
                    owner,
                    project_id,
                    status,
                    due,
                    created,
                    item_client_id,
                    context_client,
                    project_client_id,
                ) = row

                # Determine client_id - prefer direct, then via project, then try context
                client_id = item_client_id or project_client_id
                if not client_id and context_client:
                    # Try to match context_client_name to a client
                    for cid, data in self.client_patterns.items():
                        if context_client.lower() in list(data["patterns"]):
                            client_id = cid
                            break

                try:
                    result = self._sync_item_with_links(
                        iid,
                        title,
                        domain,
                        owner,
                        project_id,
                        client_id,
                        status,
                        due,
                        created,
                    )
                    stats["tasks"]["processed"] += 1
                    if result.get("status") == "created":
                        stats["tasks"]["created"] += 1
                    stats["tasks"]["links_created"] += result.get("links_created", 0)
                except Exception as e:
                    log.warning(f"Failed to sync item {iid}: {e}")

            # Repair missing links for existing artifacts
            repair_stats = self.repair_missing_links()
            stats["repair"] = repair_stats

            # Generate fix data for still-unlinked artifacts
            fix_count = self._generate_fix_data_for_unlinked()
            stats["fix_data_created"] = fix_count

            return stats

        finally:
            conn.close()

    def _sync_item_with_links(
        self,
        item_id: str,
        title: str,
        domain: str,
        owner: str,
        project_id: str,
        client_id: str,
        status: str,
        due: str,
        created: str,
    ) -> dict[str, Any]:
        """
        Sync a single item and create proper entity links using internal IDs.
        """
        # Create artifact
        result = self.artifact_svc.create_artifact(
            source="asana",
            source_id=item_id,
            artifact_type="task",
            occurred_at=created or datetime.now().isoformat(),
            payload={
                "gid": item_id,
                "name": title,
                "domain": domain,
                "assignee": {"name": owner} if owner else None,
                "project_id": project_id,
                "client_id": client_id,
                "completed": status == "done",
                "due_on": due,
            },
        )

        if result["status"] == "unchanged":
            return result

        artifact_id = result["artifact_id"]
        links = []

        # Create link to project (using internal project_id directly)
        if project_id:
            link = self.link_svc.create_link(
                artifact_id,
                "project",
                project_id,
                "headers",
                0.95,
                ["Internal project ID reference"],
                auto_confirm=True,
            )
            links.append(link)

        # Create link to client (using internal client_id directly)
        if client_id:
            link = self.link_svc.create_link(
                artifact_id,
                "client",
                client_id,
                "rules",
                0.95,
                ["Client ID from item or project"],
                auto_confirm=True,
            )
            links.append(link)

        # Also try text matching for additional client matches
        for cid, conf, reason in self._match_client_in_text(title or ""):
            if cid != client_id:  # Don't duplicate
                link = self.link_svc.create_link(
                    artifact_id,
                    "client",
                    cid,
                    "naming",
                    conf,
                    [reason],
                    auto_confirm=(conf >= 0.85),
                )
                links.append(link)

        # Create excerpt from task name
        if title:
            self.artifact_svc.create_excerpt(
                artifact_id,
                title,
                anchor_type="json_path",
                anchor_start="$.name",
                anchor_end="$.name",
            )

        return {
            "artifact_id": artifact_id,
            "status": result["status"],
            "links_created": len(links),
        }

    def repair_missing_links(self) -> dict[str, Any]:
        """
        Repair missing entity links for existing artifacts.
        Runs linking logic for artifacts that don't have high-confidence links.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {"repaired": 0, "links_created": 0, "errors": 0}

        try:
            # Find artifacts without high-confidence links
            cursor.execute("""
                SELECT a.artifact_id, a.source, a.type, a.source_id, a.payload_ref
                FROM artifacts a
                WHERE NOT EXISTS (
                    SELECT 1 FROM entity_links el
                    WHERE el.from_artifact_id = a.artifact_id
                    AND el.confidence >= 0.7
                )
                LIMIT 500
            """)

            for row in cursor.fetchall():
                artifact_id, source, atype, source_id, payload_ref = row

                try:
                    links = []

                    # Parse payload (with decryption support)
                    if payload_ref.startswith("blob:"):
                        blob_id = payload_ref.replace("blob:", "")
                        cursor.execute(
                            "SELECT payload FROM artifact_blobs WHERE blob_id = ?",
                            (blob_id,),
                        )
                        blob_row = cursor.fetchone()
                        if blob_row:
                            payload_data = decrypt_blob_payload(blob_row[0])
                            payload = json.loads(payload_data)
                        else:
                            continue
                    else:
                        payload = json.loads(payload_ref)

                    if atype == "project_update":
                        # Link project artifacts
                        gid = payload.get("gid") or source_id.replace("project_", "")
                        client_id = payload.get("client_id")

                        # Find project
                        cursor.execute(
                            "SELECT id, client_id FROM projects WHERE asana_project_id = ? OR id = ?",
                            (gid, gid),
                        )
                        proj_row = cursor.fetchone()
                        if proj_row:
                            project_id, proj_client_id = proj_row
                            link = self.link_svc.create_link(
                                artifact_id,
                                "project",
                                project_id,
                                "headers",
                                0.95,
                                ["Repaired: direct project reference"],
                                auto_confirm=True,
                            )
                            links.append(link)

                            effective_client = client_id or proj_client_id
                            if effective_client:
                                link = self.link_svc.create_link(
                                    artifact_id,
                                    "client",
                                    effective_client,
                                    "rules",
                                    0.90,
                                    ["Repaired: project-client relationship"],
                                    auto_confirm=True,
                                )
                                links.append(link)

                    elif atype == "task":
                        # Link task artifacts
                        project_id = payload.get("project_id")
                        client_id = payload.get("client_id")

                        if project_id:
                            link = self.link_svc.create_link(
                                artifact_id,
                                "project",
                                project_id,
                                "headers",
                                0.95,
                                ["Repaired: task project reference"],
                                auto_confirm=True,
                            )
                            links.append(link)

                            # Get client from project if not set
                            if not client_id:
                                cursor.execute(
                                    "SELECT client_id FROM projects WHERE id = ?",
                                    (project_id,),
                                )
                                pcrow = cursor.fetchone()
                                if pcrow and pcrow[0]:
                                    client_id = pcrow[0]

                        if client_id:
                            link = self.link_svc.create_link(
                                artifact_id,
                                "client",
                                client_id,
                                "rules",
                                0.90,
                                ["Repaired: task client reference"],
                                auto_confirm=True,
                            )
                            links.append(link)

                        # Try text matching
                        title = payload.get("name", "")
                        for cid, conf, reason in self._match_client_in_text(title):
                            if cid != client_id:
                                link = self.link_svc.create_link(
                                    artifact_id,
                                    "client",
                                    cid,
                                    "naming",
                                    conf,
                                    [f"Repaired: {reason}"],
                                    auto_confirm=(conf >= 0.85),
                                )
                                links.append(link)

                    elif atype == "calendar_event":
                        # Try text matching for calendar events
                        summary = payload.get("summary", "")
                        for cid, conf, reason in self._match_client_in_text(summary):
                            link = self.link_svc.create_link(
                                artifact_id,
                                "client",
                                cid,
                                "naming",
                                conf,
                                [f"Repaired: {reason}"],
                                auto_confirm=(conf >= 0.85),
                            )
                            links.append(link)

                    if links:
                        stats["repaired"] += 1
                        stats["links_created"] += len(links)

                except Exception as e:
                    log.warning(
                        f"Failed to repair links for artifact {artifact_id}: {e}"
                    )
                    stats["errors"] += 1

            return stats

        finally:
            conn.close()

    def _generate_fix_data_for_unlinked(self) -> int:
        """
        Generate Fix Data items for artifacts without high-confidence entity links.
        Returns count of fix data items created.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        count = 0

        try:
            # Find artifacts without any confirmed high-confidence links to client or project
            cursor.execute("""
                SELECT a.artifact_id, a.source, a.type, a.occurred_at
                FROM artifacts a
                WHERE NOT EXISTS (
                    SELECT 1 FROM entity_links el
                    WHERE el.from_artifact_id = a.artifact_id
                    AND el.to_entity_type IN ('client', 'project', 'engagement')
                    AND el.confidence >= 0.7
                    AND el.status != 'rejected'
                )
                AND a.type IN ('task', 'message', 'invoice')
                LIMIT 500
            """)

            for row in cursor.fetchall():
                artifact_id, source, atype, occurred_at = row

                # Check if fix data already exists
                cursor.execute(
                    """
                    SELECT fix_id FROM fix_data_queue
                    WHERE artifact_id = ? AND fix_type = 'missing_entity_link' AND status = 'pending'
                """,
                    (artifact_id,),
                )

                if not cursor.fetchone():
                    fix_id = self.link_svc._generate_id("fix")
                    cursor.execute(
                        """
                        INSERT INTO fix_data_queue
                        (fix_id, fix_type, severity, artifact_id, description, context, status, created_at, updated_at)
                        VALUES (?, 'missing_entity_link', 'medium', ?, ?, ?, 'pending', datetime('now'), datetime('now'))
                    """,
                        (
                            fix_id,
                            artifact_id,
                            f"Artifact {atype} from {source} has no high-confidence entity links",
                            json.dumps(
                                {
                                    "artifact_id": artifact_id,
                                    "source": source,
                                    "type": atype,
                                    "occurred_at": occurred_at,
                                }
                            ),
                        ),
                    )
                    count += 1

            conn.commit()
            log.info(f"Generated {count} fix data items for unlinked artifacts")
            return count

        finally:
            conn.close()

    def relink_emails_to_tasks(self, limit: int = 500) -> dict[str, Any]:
        """
        Reprocess email artifacts to add task links.

        This backfills task links for existing email artifacts that were
        ingested before task linking was implemented.

        Returns stats on reprocessing.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {
            "processed": 0,
            "links_created": 0,
            "emails_linked": 0,
            "asana_gid_matches": 0,
            "keyword_matches": 0,
            "errors": 0,
        }

        # Reload task patterns to get latest
        self._load_entity_patterns()
        log.info(
            f"Relinking emails to tasks. {len(self.task_patterns)} task patterns loaded."
        )

        try:
            # Find email artifacts that don't have task links
            cursor.execute(
                """
                SELECT a.artifact_id, a.source_id, a.payload_ref
                FROM artifacts a
                WHERE a.source = 'gmail'
                  AND a.type = 'message'
                  AND NOT EXISTS (
                      SELECT 1 FROM entity_links el
                      WHERE el.from_artifact_id = a.artifact_id
                        AND el.to_entity_type = 'task'
                  )
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            log.info(f"Found {len(rows)} email artifacts without task links")

            for artifact_id, _source_id, payload_ref in rows:
                try:
                    # Get payload (with decryption support)
                    if payload_ref.startswith("blob:"):
                        blob_id = payload_ref.replace("blob:", "")
                        cursor.execute(
                            "SELECT payload FROM artifact_blobs WHERE blob_id = ?",
                            (blob_id,),
                        )
                        blob_row = cursor.fetchone()
                        if not blob_row:
                            continue
                        payload_data = decrypt_blob_payload(blob_row[0])
                        payload = json.loads(payload_data)
                    else:
                        payload = json.loads(payload_ref)

                    stats["processed"] += 1

                    # Build searchable text
                    subject = payload.get("subject", "")
                    snippet = payload.get("snippet", "")
                    body = payload.get("body", "") or payload.get("body_text", "") or ""
                    searchable = f"{subject} {snippet} {body}"

                    links_created = 0
                    linked_task_ids = set()

                    # Strategy 1: Asana GIDs in URLs
                    asana_gids = self._extract_asana_task_gids(searchable)
                    for gid in asana_gids:
                        task_id = self._match_task_by_asana_gid(gid)
                        if task_id and task_id not in linked_task_ids:
                            link = self.link_svc.create_link(
                                artifact_id,
                                "task",
                                task_id,
                                "rules",
                                0.98,
                                [f"Asana GID in email: {gid}"],
                                auto_confirm=True,
                            )
                            if link.get("status") == "created":
                                links_created += 1
                                stats["asana_gid_matches"] += 1
                            linked_task_ids.add(task_id)

                    # Strategy 2: Keyword matching
                    for task_id, conf, reason in self._match_task_in_text(searchable):
                        if task_id not in linked_task_ids:
                            link = self.link_svc.create_link(
                                artifact_id,
                                "task",
                                task_id,
                                "naming",
                                conf,
                                [f"Backfill: {reason}"],
                                auto_confirm=(conf >= 0.85),
                            )
                            if link.get("status") == "created":
                                links_created += 1
                                stats["keyword_matches"] += 1
                            linked_task_ids.add(task_id)

                    if links_created > 0:
                        stats["links_created"] += links_created
                        stats["emails_linked"] += 1

                except Exception as e:
                    log.warning(f"Error relinking email {artifact_id}: {e}")
                    stats["errors"] += 1

            log.info(f"Relink complete: {stats}")
            return stats

        finally:
            conn.close()


# Singleton instance
_hooks = None


def get_hooks() -> CollectorHooks:
    """Get the singleton hooks instance."""
    global _hooks
    if _hooks is None:
        _hooks = CollectorHooks()
    return _hooks


# Convenience alias
hooks = None


def init_hooks():
    """Initialize hooks (call at module import if needed)."""
    global hooks
    hooks = get_hooks()
    return hooks
