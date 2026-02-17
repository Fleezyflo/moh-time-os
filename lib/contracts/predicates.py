"""
Predicates Module — Section Existence Rules.

Existence predicates define when sections MUST be non-empty.
Each predicate is a function that returns (must_exist: bool, reason: str).

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- Predicates enforce data-existence rules
- Empty section when data exists = violation
- Violations fail the build (not warnings)
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class PredicateViolation(Exception):
    """Raised when a predicate check fails."""

    pass


@dataclass
class NormalizedData:
    """
    Normalized data container for predicate evaluation.

    This is the canonical representation after extraction and normalization.
    Predicates check this against the final snapshot.
    """

    projects: list[Any]
    clients: list[Any]
    invoices: list[Any]
    commitments: list[Any]
    communications: list[Any]
    people: list[Any]

    def __init__(
        self,
        projects: list[Any] | None = None,
        clients: list[Any] | None = None,
        invoices: list[Any] | None = None,
        commitments: list[Any] | None = None,
        communications: list[Any] | None = None,
        people: list[Any] | None = None,
    ) -> None:
        self.projects = projects if projects is not None else []
        self.clients = clients if clients is not None else []
        self.invoices = invoices if invoices is not None else []
        self.commitments = commitments if commitments is not None else []
        self.communications = communications if communications is not None else []
        self.people = people if people is not None else []


def get_nested(obj: dict[str, Any], path: str) -> Any:
    """
    Get nested value from dict using dot notation.

    Example: get_nested(snapshot, "cash_ar.debtors")
             returns snapshot["cash_ar"]["debtors"]
    """
    parts = path.split(".")
    current: Any = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


# =============================================================================
# PREDICATE FUNCTIONS
# =============================================================================


def heatstrip_must_exist(normalized: NormalizedData) -> tuple[bool, str]:
    """
    Heatstrip required if any project exists in delivery portfolio.

    Logic: If normalized has projects, the heatstrip section must have items.
    """
    count = len(normalized.projects)
    return (count > 0, f"projects_count={count}")


def cash_ar_debtors_must_exist(normalized: NormalizedData) -> tuple[bool, str]:
    """
    Debtors required if any unpaid invoice exists.

    Logic: If normalized has unpaid invoices, cash_ar.debtors must have items.
    """
    # Check for unpaid invoices (those without payment_date and with status sent/overdue)
    unpaid = [
        inv
        for inv in normalized.invoices
        if hasattr(inv, "is_unpaid")
        and inv.is_unpaid
        or (
            isinstance(inv, dict)
            and inv.get("status") in ("sent", "overdue")
            and not inv.get("payment_date")
        )
    ]
    count = len(unpaid)
    return (count > 0, f"unpaid_invoices={count}")


def comms_threads_must_exist(normalized: NormalizedData) -> tuple[bool, str]:
    """
    Threads required if any communication exists.

    Logic: If normalized has communications, comms_commitments.threads must have items.
    """
    count = len(normalized.communications)
    return (count > 0, f"communications_count={count}")


def capacity_people_must_exist(normalized: NormalizedData) -> tuple[bool, str]:
    """
    People overview required if any person has assigned tasks.

    Logic: If normalized has people with hours, capacity_command.people_overview must have items.
    """
    # Check for people with assigned hours
    assigned = [
        p
        for p in normalized.people
        if hasattr(p, "assigned_hours")
        and p.assigned_hours > 0
        or (isinstance(p, dict) and p.get("hours_assigned", 0) > 0)
    ]
    count = len(assigned)
    return (count > 0, f"people_with_assignments={count}")


def commitments_must_exist(normalized: NormalizedData) -> tuple[bool, str]:
    """
    Commitments section required if any commitment exists in normalized data.
    """
    count = len(normalized.commitments)
    return (count > 0, f"commitments_count={count}")


# =============================================================================
# PREDICATE REGISTRY
# =============================================================================

# Registry maps section path to predicate function
# ALL predicates are enforced together
SECTION_PREDICATES: dict[str, Callable[[NormalizedData], tuple[bool, str]]] = {
    "heatstrip_projects": heatstrip_must_exist,
    "cash_ar.debtors": cash_ar_debtors_must_exist,
    "comms_commitments.threads": comms_threads_must_exist,
    "capacity_command.people_overview": capacity_people_must_exist,
    "comms_commitments.commitments": commitments_must_exist,
}


# =============================================================================
# ENFORCEMENT
# =============================================================================


def enforce_predicates(normalized: NormalizedData, snapshot: dict) -> list[str]:
    """
    Enforce all predicates. Returns list of violations.

    Empty list = all predicates pass.
    Non-empty list = violations that must fail the build.

    Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
    - This runs in PRODUCTION, not just tests
    - Violations are errors, not warnings

    Args:
        normalized: The normalized data from extraction
        snapshot: The final snapshot dict to validate

    Returns:
        List of violation messages. Empty = pass.
    """
    violations = []

    for section_path, predicate in SECTION_PREDICATES.items():
        must_exist, reason = predicate(normalized)
        actual = get_nested(snapshot, section_path)

        # Check if section is empty when it must exist
        is_empty = actual is None or (isinstance(actual, (list, dict)) and len(actual) == 0)

        if must_exist and is_empty:
            violations.append(
                f"PREDICATE_VIOLATION: {section_path} is empty but must exist ({reason})"
            )

    return violations


def enforce_predicates_strict(normalized: NormalizedData, snapshot: dict) -> None:
    """
    Strict enforcement — raises on first violation.

    Use this in production generator to fail fast.

    Raises:
        PredicateViolation: If any predicate fails
    """
    violations = enforce_predicates(normalized, snapshot)
    if violations:
        raise PredicateViolation(
            f"Predicate check failed with {len(violations)} violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
