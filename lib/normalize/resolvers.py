"""
Resolvers Module — Exhaustive Semantic Resolution Rules.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 2:
- Unknown scope_ref_type MUST RAISE (not log)
- Known but unresolvable MUST produce (resolved=False, unresolved_reason=...)
- Resolution metrics tracked for thresholds

This is the ONLY place where scope resolution happens.
All resolution rules live here with tests.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ResolutionFailure(Exception):
    """Raised when resolution threshold is not met."""

    pass


# =============================================================================
# SCOPE TYPE ENUM (Exhaustive)
# =============================================================================


class ScopeRefType(StrEnum):
    """
    ALL known scope_ref_type values.

    This enum MUST be exhaustive. Unknown types raise ValueError.
    Add new types here when new scope types are introduced.
    """

    CLIENT = "client"
    PROJECT = "project"
    THREAD = "thread"
    INVOICE = "invoice"
    TASK = "task"
    BRAND = "brand"
    ENGAGEMENT = "engagement"


# =============================================================================
# RESOLUTION RESULT
# =============================================================================


@dataclass
class ResolutionResult:
    """
    Result of a resolution attempt.

    Either resolved=True with client_id, or resolved=False with reason.
    No silent failures.
    """

    client_id: str | None
    resolved: bool
    resolution_path: str  # "direct" | "via_project" | "via_thread" | etc.
    unresolved_reason: str | None = None

    @staticmethod
    def success(client_id: str, path: str) -> "ResolutionResult":
        return ResolutionResult(
            client_id=client_id,
            resolved=True,
            resolution_path=path,
            unresolved_reason=None,
        )

    @staticmethod
    def failure(path: str, reason: str) -> "ResolutionResult":
        return ResolutionResult(
            client_id=None,
            resolved=False,
            resolution_path=path,
            unresolved_reason=reason,
        )


# =============================================================================
# RESOLUTION METRICS
# =============================================================================


@dataclass
class ResolutionMetrics:
    """Metrics tracked during resolution."""

    total: int = 0
    resolved: int = 0
    unresolved: int = 0
    by_path: dict[str, int] = field(default_factory=dict)
    unresolved_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def resolution_rate(self) -> float:
        return self.resolved / self.total if self.total > 0 else 0.0

    def record_success(self, path: str) -> None:
        self.total += 1
        self.resolved += 1
        self.by_path[path] = self.by_path.get(path, 0) + 1

    def record_failure(self, path: str, reason: str) -> None:
        self.total += 1
        self.unresolved += 1
        self.by_path[path] = self.by_path.get(path, 0) + 1
        self.unresolved_reasons[reason] = self.unresolved_reasons.get(reason, 0) + 1


# =============================================================================
# DATABASE PROTOCOL
# =============================================================================


class DatabaseProtocol(Protocol):
    """Protocol for database access."""

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute query and return single row."""
        ...

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute query and return all rows."""
        ...


# =============================================================================
# COMMITMENT RESOLVER
# =============================================================================


class CommitmentResolver:
    """
    Resolves commitment → client relationship.

    Per Amendment 2:
    - Unknown scope_ref_type RAISES ValueError
    - Known but unresolvable produces explicit failure reason

    Resolution paths:
    - client: Direct lookup
    - project: project.client_id lookup
    - thread: thread participant → client matching
    - invoice: invoice.client_id lookup
    - task: task.project → project.client_id
    - brand: brand.client_id lookup
    - engagement: engagement.client_id lookup
    """

    # Threshold for enforcement (85% per spec)
    RESOLUTION_THRESHOLD = 0.85

    def __init__(self, db: DatabaseProtocol | None = None):
        self.db = db
        self.metrics = ResolutionMetrics()

    def resolve(self, scope_type: str, scope_id: str) -> ResolutionResult:
        """
        Resolve scope reference to client.

        Args:
            scope_type: The scope_ref_type value
            scope_id: The scope_ref_id value

        Returns:
            ResolutionResult with client_id or failure reason

        Raises:
            ValueError: If scope_type is unknown (Amendment 2)
        """
        # Validate scope type is known
        try:
            validated_type = ScopeRefType(scope_type)
        except ValueError:
            # UNKNOWN TYPE — explicit failure per Amendment 2
            raise ValueError(
                f"Unknown scope_ref_type '{scope_type}' for scope_id '{scope_id}'. "
                f"Add handling to CommitmentResolver or update ScopeRefType enum. "
                f"Known types: {[t.value for t in ScopeRefType]}"
            )

        # Dispatch to type-specific resolver
        match validated_type:
            case ScopeRefType.CLIENT:
                result = self._resolve_direct_client(scope_id)
            case ScopeRefType.PROJECT:
                result = self._resolve_via_project(scope_id)
            case ScopeRefType.THREAD:
                result = self._resolve_via_thread(scope_id)
            case ScopeRefType.INVOICE:
                result = self._resolve_via_invoice(scope_id)
            case ScopeRefType.TASK:
                result = self._resolve_via_task(scope_id)
            case ScopeRefType.BRAND:
                result = self._resolve_via_brand(scope_id)
            case ScopeRefType.ENGAGEMENT:
                result = self._resolve_via_engagement(scope_id)

        # Track metrics
        if result.resolved:
            self.metrics.record_success(result.resolution_path)
        else:
            self.metrics.record_failure(
                result.resolution_path, result.unresolved_reason or "unknown"
            )

        return result

    def _resolve_direct_client(self, client_id: str) -> ResolutionResult:
        """scope_ref_type == 'client' → direct resolution."""
        if not self.db:
            # No DB, assume valid if ID provided
            if client_id:
                return ResolutionResult.success(client_id, "direct")
            return ResolutionResult.failure("direct", "empty client_id")

        # Verify client exists
        client = self.db.query_one(
            "SELECT id FROM clients WHERE id = ? OR commitment_id = ?",
            (client_id, client_id),
        )
        if client:
            return ResolutionResult.success(client.get("id") or client_id, "direct")

        return ResolutionResult.failure(
            "direct", f"client_id '{client_id}' not found in clients table"
        )

    def _resolve_via_project(self, project_id: str) -> ResolutionResult:
        """scope_ref_type == 'project' → lookup project.client_id."""
        if not self.db:
            return ResolutionResult.failure("via_project", "no database connection")

        project = self.db.query_one(
            "SELECT client_id FROM projects WHERE id = ? OR gid = ?",
            (project_id, project_id),
        )

        if project and project.get("client_id"):
            return ResolutionResult.success(project["client_id"], "via_project")

        return ResolutionResult.failure(
            "via_project", f"project '{project_id}' has no client_id"
        )

    def _resolve_via_thread(self, thread_id: str) -> ResolutionResult:
        """scope_ref_type == 'thread' → lookup thread participants → client match."""
        if not self.db:
            return ResolutionResult.failure("via_thread", "no database connection")

        # Try to find thread and its associated client
        thread = self.db.query_one(
            "SELECT client_id FROM threads WHERE id = ? OR thread_id = ?",
            (thread_id, thread_id),
        )

        if thread and thread.get("client_id"):
            return ResolutionResult.success(thread["client_id"], "via_thread")

        # Try matching participants to contacts → clients
        # This is a more complex resolution path
        return ResolutionResult.failure(
            "via_thread", f"thread '{thread_id}' has no client attribution"
        )

    def _resolve_via_invoice(self, invoice_id: str) -> ResolutionResult:
        """scope_ref_type == 'invoice' → lookup invoice.client_id."""
        if not self.db:
            return ResolutionResult.failure("via_invoice", "no database connection")

        invoice = self.db.query_one(
            "SELECT contact_id FROM invoices WHERE id = ? OR invoice_id = ?",
            (invoice_id, invoice_id),
        )

        if invoice and invoice.get("contact_id"):
            return ResolutionResult.success(invoice["contact_id"], "via_invoice")

        return ResolutionResult.failure(
            "via_invoice", f"invoice '{invoice_id}' has no contact_id"
        )

    def _resolve_via_task(self, task_id: str) -> ResolutionResult:
        """scope_ref_type == 'task' → task.project → project.client_id."""
        if not self.db:
            return ResolutionResult.failure("via_task", "no database connection")

        # Get task's project
        task = self.db.query_one(
            "SELECT project_id FROM tasks WHERE id = ? OR gid = ?", (task_id, task_id)
        )

        if not task or not task.get("project_id"):
            return ResolutionResult.failure(
                "via_task", f"task '{task_id}' has no project_id"
            )

        # Resolve via project
        return self._resolve_via_project(task["project_id"])

    def _resolve_via_brand(self, brand_id: str) -> ResolutionResult:
        """scope_ref_type == 'brand' → brand.client_id."""
        if not self.db:
            return ResolutionResult.failure("via_brand", "no database connection")

        brand = self.db.query_one(
            "SELECT client_id FROM brands WHERE id = ?", (brand_id,)
        )

        if brand and brand.get("client_id"):
            return ResolutionResult.success(brand["client_id"], "via_brand")

        return ResolutionResult.failure(
            "via_brand", f"brand '{brand_id}' has no client_id"
        )

    def _resolve_via_engagement(self, engagement_id: str) -> ResolutionResult:
        """scope_ref_type == 'engagement' → engagement.client_id."""
        if not self.db:
            return ResolutionResult.failure("via_engagement", "no database connection")

        engagement = self.db.query_one(
            "SELECT client_id FROM engagements WHERE id = ?", (engagement_id,)
        )

        if engagement and engagement.get("client_id"):
            return ResolutionResult.success(engagement["client_id"], "via_engagement")

        return ResolutionResult.failure(
            "via_engagement", f"engagement '{engagement_id}' has no client_id"
        )

    def enforce_threshold(self) -> None:
        """
        Enforce resolution rate threshold.

        Call after all resolutions. Fails if below threshold.

        Raises:
            ResolutionFailure: If rate < RESOLUTION_THRESHOLD
        """
        rate = self.metrics.resolution_rate
        if rate < self.RESOLUTION_THRESHOLD:
            raise ResolutionFailure(
                f"Commitment resolution rate {rate:.1%} below threshold "
                f"{self.RESOLUTION_THRESHOLD:.1%}. "
                f"Resolved: {self.metrics.resolved}/{self.metrics.total}. "
                f"By path: {self.metrics.by_path}. "
                f"Unresolved reasons: {self.metrics.unresolved_reasons}"
            )
