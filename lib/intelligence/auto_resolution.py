"""
Auto-Resolution Engine for Resolution Queue

Provides intelligent automation to resolve queue items:
- Analyzes pending resolution items
- Applies resolution rules with confidence thresholds
- Returns proposed actions without writing to DB
- Escalates items that don't meet confidence threshold

Resolution rules (7 types):
- project_unlinked: Search for project with matching name substring
- brand_missing: Infer brand from client name or domain
- client_unidentified: Match communication sender email to known contacts
- due_date_missing: Set due date to 30 days from creation
- invoice_missing_client: Match invoice contact email to known clients
- invoice_missing_due: Set due date to invoice_date + 30 days
- comm_missing_client: Match email domain to known client domains
"""

import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ResolutionRule:
    """Definition of an auto-resolution rule."""

    rule_id: str  # e.g., "project_unlinked"
    issue_type: str  # Must match resolution_queue.issue_type
    description: str
    confidence_threshold: float = 0.8  # 0.0 to 1.0
    auto_apply: bool = True  # Auto-apply if >= threshold
    method_name: str = ""  # Name of method that applies this rule

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResolutionAttempt:
    """Result of attempting to auto-resolve a single item."""

    item_id: str
    issue_type: str
    resolved: bool  # True if auto-resolved
    confidence: float  # 0.0 to 1.0
    action_taken: str | None = None  # What action was proposed
    reason: str = ""  # Why it was/wasn't resolved
    rule_id: str | None = None  # Which rule was applied
    requires_review: bool = False  # High confidence but below auto_apply threshold

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResolutionReport:
    """Report from scan_and_resolve operation."""

    total_scanned: int
    auto_resolved: int
    escalated: int
    failed: int
    duration_ms: int
    attempts: list[ResolutionAttempt] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_scanned": self.total_scanned,
            "auto_resolved": self.auto_resolved,
            "escalated": self.escalated,
            "failed": self.failed,
            "duration_ms": self.duration_ms,
            "attempts": [a.to_dict() for a in self.attempts],
        }


@dataclass
class BatchResult:
    """Result of batch_resolve operation."""

    total: int
    resolved: int
    failed: int
    results: list[ResolutionAttempt] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "resolved": self.resolved,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


# =============================================================================
# AUTO-RESOLUTION ENGINE
# =============================================================================


class AutoResolutionEngine:
    """
    Engine for automatically resolving resolution queue items.

    Does NOT write to database. Returns proposed actions for caller to apply.
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize with optional database path."""
        self.db_path = db_path if db_path is not None else paths.db_path()
        self._rules: list[ResolutionRule] | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute query and return list of dicts."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Query execution failed: {e}")
            return []
        finally:
            conn.close()

    def _execute_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute query and return single dict or None."""
        results = self._execute(sql, params)
        return results[0] if results else None

    # =========================================================================
    # RESOLUTION RULES
    # =========================================================================

    def get_resolution_rules(self) -> list[ResolutionRule]:
        """Return list of available auto-resolution rules."""
        if self._rules is not None:
            return self._rules

        self._rules = [
            ResolutionRule(
                rule_id="project_unlinked",
                issue_type="project_unlinked",
                description="Search for project with matching name substring. If exactly 1 match, auto-link.",
                confidence_threshold=0.85,
                auto_apply=True,
                method_name="resolve_project_unlinked",
            ),
            ResolutionRule(
                rule_id="brand_missing",
                issue_type="missing_brand",
                description="Infer brand from client name or domain. If client has existing brand, copy it.",
                confidence_threshold=0.80,
                auto_apply=True,
                method_name="resolve_brand_missing",
            ),
            ResolutionRule(
                rule_id="client_unidentified",
                issue_type="unlinked_with_commitments",
                description="Match communication sender email to known client contacts. If 1 match, assign.",
                confidence_threshold=0.90,
                auto_apply=True,
                method_name="resolve_client_unidentified",
            ),
            ResolutionRule(
                rule_id="due_date_missing",
                issue_type="missing_due_date",
                description="Set due date to 30 days from creation if task has no date.",
                confidence_threshold=0.95,
                auto_apply=True,
                method_name="resolve_due_date_missing",
            ),
            ResolutionRule(
                rule_id="invoice_missing_client",
                issue_type="missing_client",
                description="Match invoice contact email to known clients.",
                confidence_threshold=0.85,
                auto_apply=True,
                method_name="resolve_invoice_missing_client",
            ),
            ResolutionRule(
                rule_id="invoice_missing_due",
                issue_type="missing_due_date",
                description="Set due date to invoice_date + 30 days (standard net-30 terms).",
                confidence_threshold=0.95,
                auto_apply=True,
                method_name="resolve_invoice_missing_due",
            ),
            ResolutionRule(
                rule_id="comm_missing_client",
                issue_type="unlinked_with_commitments",
                description="Match email domain to known client domains.",
                confidence_threshold=0.80,
                auto_apply=True,
                method_name="resolve_comm_missing_client",
            ),
        ]
        return self._rules

    # =========================================================================
    # INDIVIDUAL RESOLUTION METHODS
    # =========================================================================

    def resolve_project_unlinked(self, item: dict) -> ResolutionAttempt:
        """
        Resolve project_unlinked: Search for project with matching name.
        Returns ResolutionAttempt with proposed action.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="project_unlinked",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the task name
        task = self._execute_one("SELECT id, name FROM tasks WHERE id = ?", (entity_id,))
        if not task:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="project_unlinked",
                resolved=False,
                confidence=0.0,
                reason="Task not found",
            )

        task_name = task.get("name", "")
        if not task_name:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="project_unlinked",
                resolved=False,
                confidence=0.0,
                reason="Task has no name",
            )

        # Search for projects with matching name substring
        projects = self._execute(
            "SELECT id, name FROM projects WHERE LOWER(name) LIKE LOWER(?) LIMIT 10",
            (f"%{task_name[:20]}%",),
        )

        if len(projects) == 1:
            project_id = projects[0]["id"]
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="project_unlinked",
                resolved=True,
                confidence=0.85,
                action_taken=f"Link task {entity_id} to project {project_id}",
                reason="Exactly 1 project matched task name",
                rule_id="project_unlinked",
            )

        if len(projects) > 1:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="project_unlinked",
                resolved=False,
                confidence=0.6,
                reason=f"Found {len(projects)} possible projects, ambiguous",
            )

        return ResolutionAttempt(
            item_id=item.get("id", ""),
            issue_type="project_unlinked",
            resolved=False,
            confidence=0.1,
            reason="No matching projects found",
        )

    def resolve_brand_missing(self, item: dict) -> ResolutionAttempt:
        """
        Resolve brand_missing: Infer brand from client or check existing client brand.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_brand",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the project and its client
        project = self._execute_one(
            "SELECT id, name, client_id FROM projects WHERE id = ?",
            (entity_id,),
        )
        if not project:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_brand",
                resolved=False,
                confidence=0.0,
                reason="Project not found",
            )

        client_id = project.get("client_id")
        if not client_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_brand",
                resolved=False,
                confidence=0.3,
                reason="Project has no client linked",
            )

        # Check if client has a brand
        brand = self._execute_one(
            "SELECT id FROM brands WHERE client_id = ? LIMIT 1",
            (client_id,),
        )

        if brand:
            brand_id = brand.get("id")
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_brand",
                resolved=True,
                confidence=0.85,
                action_taken=f"Assign brand {brand_id} to project {entity_id}",
                reason="Client has existing brand, copy to project",
                rule_id="brand_missing",
            )

        return ResolutionAttempt(
            item_id=item.get("id", ""),
            issue_type="missing_brand",
            resolved=False,
            confidence=0.2,
            reason="Client has no brand to copy",
        )

    def resolve_client_unidentified(self, item: dict) -> ResolutionAttempt:
        """
        Resolve client_unidentified: Match communication sender email to client contacts.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the communication sender email
        comm = self._execute_one(
            "SELECT id, sender_email FROM communications WHERE id = ?",
            (entity_id,),
        )
        if not comm:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="Communication not found",
            )

        sender_email = comm.get("sender_email", "").lower()
        if not sender_email:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="Communication has no sender email",
            )

        # Search for client contacts with matching email
        clients = self._execute(
            "SELECT DISTINCT c.id, c.name FROM clients c JOIN client_contacts cc ON c.id = cc.client_id WHERE LOWER(cc.email) = ?",
            (sender_email,),
        )

        if len(clients) == 1:
            client_id = clients[0]["id"]
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=True,
                confidence=0.95,
                action_taken=f"Link communication {entity_id} to client {client_id}",
                reason="Exactly 1 client matched sender email",
                rule_id="client_unidentified",
            )

        if len(clients) > 1:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.6,
                reason=f"Found {len(clients)} possible clients, ambiguous",
            )

        return ResolutionAttempt(
            item_id=item.get("id", ""),
            issue_type="unlinked_with_commitments",
            resolved=False,
            confidence=0.1,
            reason="No matching client contacts found",
        )

    def resolve_due_date_missing(self, item: dict) -> ResolutionAttempt:
        """
        Resolve due_date_missing: Set due date to 30 days from creation.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the task creation date
        task = self._execute_one(
            "SELECT id, created_at FROM tasks WHERE id = ?",
            (entity_id,),
        )
        if not task:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="Task not found",
            )

        created_at = task.get("created_at")
        if not created_at:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="Task has no creation date",
            )

        try:
            # Parse creation date and add 30 days
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            due_date = (created + timedelta(days=30)).isoformat()

            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=True,
                confidence=0.98,
                action_taken=f"Set task {entity_id} due date to {due_date}",
                reason="Default 30-day due date from creation",
                rule_id="due_date_missing",
            )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Failed to parse creation date: {e}")
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason=f"Failed to parse creation date: {str(e)[:50]}",
            )

    def resolve_invoice_missing_client(self, item: dict) -> ResolutionAttempt:
        """
        Resolve invoice_missing_client: Match invoice contact email to clients.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_client",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the invoice contact email
        invoice = self._execute_one(
            "SELECT id, contact_email FROM invoices WHERE id = ?",
            (entity_id,),
        )
        if not invoice:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_client",
                resolved=False,
                confidence=0.0,
                reason="Invoice not found",
            )

        contact_email = invoice.get("contact_email", "").lower()
        if not contact_email:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_client",
                resolved=False,
                confidence=0.0,
                reason="Invoice has no contact email",
            )

        # Search for clients with matching contact email
        clients = self._execute(
            "SELECT DISTINCT c.id FROM clients c JOIN client_contacts cc ON c.id = cc.client_id WHERE LOWER(cc.email) = ?",
            (contact_email,),
        )

        if len(clients) == 1:
            client_id = clients[0]["id"]
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_client",
                resolved=True,
                confidence=0.90,
                action_taken=f"Assign client {client_id} to invoice {entity_id}",
                reason="Exactly 1 client matched contact email",
                rule_id="invoice_missing_client",
            )

        if len(clients) > 1:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_client",
                resolved=False,
                confidence=0.5,
                reason=f"Found {len(clients)} possible clients, ambiguous",
            )

        return ResolutionAttempt(
            item_id=item.get("id", ""),
            issue_type="missing_client",
            resolved=False,
            confidence=0.1,
            reason="No matching client contacts found",
        )

    def resolve_invoice_missing_due(self, item: dict) -> ResolutionAttempt:
        """
        Resolve invoice_missing_due: Set due date to invoice_date + 30 days.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the invoice issue date
        invoice = self._execute_one(
            "SELECT id, issue_date, issued_at FROM invoices WHERE id = ?",
            (entity_id,),
        )
        if not invoice:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="Invoice not found",
            )

        issue_date = invoice.get("issue_date") or invoice.get("issued_at")
        if not issue_date:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason="Invoice has no issue date",
            )

        try:
            # Parse issue date and add 30 days
            issued = datetime.fromisoformat(issue_date.replace("Z", "+00:00"))
            due_date = (issued + timedelta(days=30)).isoformat()

            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=True,
                confidence=0.98,
                action_taken=f"Set invoice {entity_id} due date to {due_date}",
                reason="Standard net-30 terms",
                rule_id="invoice_missing_due",
            )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Failed to parse issue date: {e}")
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="missing_due_date",
                resolved=False,
                confidence=0.0,
                reason=f"Failed to parse issue date: {str(e)[:50]}",
            )

    def resolve_comm_missing_client(self, item: dict) -> ResolutionAttempt:
        """
        Resolve comm_missing_client: Match email domain to known client domains.
        """
        entity_id = item.get("entity_id")
        if not entity_id:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="No entity_id provided",
            )

        # Get the communication sender email
        comm = self._execute_one(
            "SELECT id, sender_email FROM communications WHERE id = ?",
            (entity_id,),
        )
        if not comm:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="Communication not found",
            )

        sender_email = comm.get("sender_email", "").lower()
        if not sender_email or "@" not in sender_email:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.0,
                reason="Communication has no valid sender email",
            )

        # Extract domain from email
        sender_domain = sender_email.split("@")[1]

        # Search for clients with matching domain in contact emails
        clients = self._execute(
            """
            SELECT DISTINCT c.id, c.name
            FROM clients c
            JOIN client_contacts cc ON c.id = cc.client_id
            WHERE LOWER(cc.email) LIKE ?
            """,
            (f"%{sender_domain}",),
        )

        if len(clients) == 1:
            client_id = clients[0]["id"]
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=True,
                confidence=0.80,
                action_taken=f"Link communication {entity_id} to client {client_id}",
                reason=f"Exactly 1 client matched email domain @{sender_domain}",
                rule_id="comm_missing_client",
            )

        if len(clients) > 1:
            return ResolutionAttempt(
                item_id=item.get("id", ""),
                issue_type="unlinked_with_commitments",
                resolved=False,
                confidence=0.5,
                reason=f"Found {len(clients)} clients with same domain, ambiguous",
            )

        return ResolutionAttempt(
            item_id=item.get("id", ""),
            issue_type="unlinked_with_commitments",
            resolved=False,
            confidence=0.1,
            reason=f"No clients found with domain @{sender_domain}",
        )

    # =========================================================================
    # MAIN RESOLUTION METHODS
    # =========================================================================

    def attempt_auto_resolve(self, item: dict) -> ResolutionAttempt:
        """
        Attempt to auto-resolve one item.

        Returns ResolutionAttempt with:
        - resolved=True if successfully auto-resolved
        - requires_review=True if high confidence but below auto_apply threshold
        - resolved=False if no good match found
        """
        item_id = item.get("id")
        issue_type = item.get("issue_type")

        if not item_id or not issue_type:
            return ResolutionAttempt(
                item_id=item_id or "",
                issue_type=issue_type or "",
                resolved=False,
                confidence=0.0,
                reason="Missing item_id or issue_type",
            )

        # Find matching rule
        rules = self.get_resolution_rules()
        matching_rules = [r for r in rules if r.issue_type == issue_type]

        if not matching_rules:
            return ResolutionAttempt(
                item_id=item_id,
                issue_type=issue_type,
                resolved=False,
                confidence=0.0,
                reason=f"No auto-resolution rule for issue_type {issue_type}",
            )

        # Try each matching rule
        best_attempt = None
        for rule in matching_rules:
            method_name = rule.method_name
            if not hasattr(self, method_name):
                logger.warning(f"Resolution method not found: {method_name}")
                continue

            try:
                method = getattr(self, method_name)
                attempt = method(item)
                attempt.rule_id = rule.rule_id

                # Keep track of best result
                if attempt.confidence > (best_attempt.confidence if best_attempt else 0):
                    best_attempt = attempt

                    # Check if we should auto-apply
                    if (
                        attempt.resolved
                        and attempt.confidence >= rule.confidence_threshold
                        and rule.auto_apply
                    ):
                        # Mark as resolved
                        attempt.resolved = True
                        attempt.requires_review = False
                        return attempt

                    # Check if we should mark for review
                    if (
                        attempt.confidence >= 0.5
                        and attempt.confidence < rule.confidence_threshold
                        and not attempt.resolved
                    ):
                        attempt.requires_review = True

            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Error in {method_name} for item {item_id}: {e}")
                continue

        if best_attempt:
            return best_attempt

        return ResolutionAttempt(
            item_id=item_id,
            issue_type=issue_type,
            resolved=False,
            confidence=0.0,
            reason=f"No successful resolution method for {issue_type}",
        )

    def batch_resolve(self, items: list[dict]) -> BatchResult:
        """
        Resolve multiple items.

        Returns BatchResult with counts and individual ResolutionAttempts.
        """
        result = BatchResult(
            total=len(items),
            resolved=0,
            failed=0,
            results=[],
        )

        for item in items:
            try:
                attempt = self.attempt_auto_resolve(item)
                result.results.append(attempt)

                if attempt.resolved:
                    result.resolved += 1
                else:
                    result.failed += 1

            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Batch resolution failed for item {item.get('id')}: {e}")
                result.failed += 1
                result.results.append(
                    ResolutionAttempt(
                        item_id=item.get("id", ""),
                        issue_type=item.get("issue_type", ""),
                        resolved=False,
                        confidence=0.0,
                        reason=f"Exception during resolution: {str(e)[:50]}",
                    )
                )

        return result

    def escalate(self, item: dict, reason: str) -> bool:
        """
        Escalate an item that can't be auto-resolved.

        Persists an escalation record to the resolution_escalations table,
        marks the original queue item as escalated, and logs for audit.

        Returns True if escalation was persisted successfully.
        """
        item_id = item.get("id")
        if not item_id:
            logger.error("Cannot escalate item without id")
            return False

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")

            # Ensure escalation table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resolution_escalations (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    issue_type TEXT,
                    reason TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    escalated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    resolution_notes TEXT
                )
            """)

            escalation_id = f"esc_{item_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            conn.execute(
                """INSERT INTO resolution_escalations
                   (id, item_id, issue_type, reason, entity_type, entity_id, escalated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    escalation_id,
                    item_id,
                    item.get("issue_type", "unknown"),
                    reason,
                    item.get("entity_type", ""),
                    item.get("entity_id", ""),
                    datetime.now().isoformat(),
                ),
            )

            # Mark original item as escalated in resolution_queue if it exists
            conn.execute(
                """UPDATE resolution_queue
                   SET status = 'escalated', updated_at = ?
                   WHERE id = ?""",
                (datetime.now().isoformat(), item_id),
            )

            conn.commit()
            conn.close()

            logger.info(f"Escalated item {item_id} as {escalation_id}: {reason}")
            return True

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Failed to escalate item {item_id}: {e}")
            return False

    def scan_and_resolve(self) -> ResolutionReport:
        """
        Main entry point: scan queue, attempt auto-resolution, report results.

        Returns ResolutionReport with counts and attempt details.
        """
        start_time = time.time()
        report = ResolutionReport(
            total_scanned=0,
            auto_resolved=0,
            escalated=0,
            failed=0,
            duration_ms=0,
            attempts=[],
        )

        try:
            # Get pending items
            items = self._execute(
                """
                SELECT id, entity_type, entity_id, issue_type, priority,
                       context, created_at, expires_at
                FROM resolution_queue
                WHERE resolved_at IS NULL
                ORDER BY priority ASC, created_at ASC
                """
            )

            report.total_scanned = len(items)

            for item in items:
                try:
                    attempt = self.attempt_auto_resolve(item)
                    report.attempts.append(attempt)

                    if attempt.resolved:
                        report.auto_resolved += 1
                    elif attempt.requires_review:
                        # Mark for review but don't count as resolved
                        pass
                    else:
                        # Try to escalate if confidence is low
                        if attempt.confidence < 0.5:
                            if self.escalate(item, attempt.reason):
                                report.escalated += 1
                            else:
                                report.failed += 1
                        else:
                            report.failed += 1

                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(f"Error resolving item {item.get('id')}: {e}")
                    report.failed += 1
                    report.attempts.append(
                        ResolutionAttempt(
                            item_id=item.get("id", ""),
                            issue_type=item.get("issue_type", ""),
                            resolved=False,
                            confidence=0.0,
                            reason=f"Exception: {str(e)[:50]}",
                        )
                    )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"scan_and_resolve failed: {e}")
            report.failed += 1

        finally:
            report.duration_ms = int((time.time() - start_time) * 1000)

        return report
