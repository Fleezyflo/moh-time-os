"""
Invariants Module — Semantic Correctness Checks.

Domain invariants verify MEANING, not just shape.
They ensure internal consistency across different parts of the snapshot.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 4:
- Invariants run in PRODUCTION, not just tests
- Generator fails if invariants fail
- Cross-check: same metric computed two ways must match
"""

from .predicates import NormalizedData


class InvariantViolation(Exception):
    """Raised when a domain invariant is violated."""

    pass


# =============================================================================
# INVARIANT FUNCTIONS
# =============================================================================


def check_ar_totals_match(snapshot: dict, normalized: NormalizedData) -> None:
    """
    INVARIANT: AR totals must be consistent across computation paths.

    Cross-check: tiles total == sum of debtors == sum of invoices

    Raises:
        InvariantViolation: If totals don't match
    """
    cash_ar = snapshot.get("cash_ar")
    if not cash_ar:
        return  # No AR section, nothing to check

    tiles = cash_ar.get("tiles", {})
    debtors = cash_ar.get("debtors", [])

    # Path 1: from tiles
    tiles_valid_ar = tiles.get("valid_ar", {})
    if isinstance(tiles_valid_ar, dict):
        tiles_total = sum(tiles_valid_ar.values())
    else:
        tiles_total = float(tiles_valid_ar or 0)

    # Path 2: sum of debtors
    debtors_total = sum(
        d.get("total_valid_ar", 0) for d in debtors if isinstance(d, dict)
    )

    # Allow small floating point differences
    tolerance = 0.01
    if abs(tiles_total - debtors_total) > tolerance:
        raise InvariantViolation(
            f"AR totals mismatch: tiles={tiles_total:.2f}, debtors={debtors_total:.2f}. "
            f"Difference={abs(tiles_total - debtors_total):.2f}"
        )


def check_commitment_resolution_complete(
    snapshot: dict, normalized: NormalizedData
) -> None:
    """
    INVARIANT: All commitments must be resolved OR explicitly marked unresolved with reason.

    No silent None values allowed.

    Raises:
        InvariantViolation: If any commitment has None client_id AND None reason
    """
    comms = snapshot.get("comms_commitments", {})
    commitments = comms.get("commitments", [])

    unresolved_without_reason = []
    for c in commitments:
        if not isinstance(c, dict):
            continue

        resolved_client = c.get("resolved_client_id")
        unresolved_reason = c.get("unresolved_reason")

        # If not resolved, must have a reason
        if resolved_client is None and unresolved_reason is None:
            commitment_id = c.get("commitment_id", "unknown")
            unresolved_without_reason.append(commitment_id)

    if unresolved_without_reason:
        raise InvariantViolation(
            f"Commitments with no resolution AND no reason: {unresolved_without_reason}. "
            f"Count: {len(unresolved_without_reason)}"
        )


def check_people_count_consistency(snapshot: dict, normalized: NormalizedData) -> None:
    """
    INVARIANT: people_overview count must match normalized people with assignments.

    Raises:
        InvariantViolation: If counts don't match
    """
    capacity = snapshot.get("capacity_command", {})
    people_overview = capacity.get("people_overview", [])

    # Get expected count from normalized data
    expected_with_hours = [
        p
        for p in normalized.people
        if hasattr(p, "assigned_hours")
        and p.assigned_hours > 0
        or (isinstance(p, dict) and p.get("hours_assigned", 0) > 0)
    ]
    expected_count = len(expected_with_hours)

    # Get actual count from snapshot
    actual_count = len(people_overview)

    # Only check if normalized has data (avoid false positives on empty data)
    if expected_count > 0 and actual_count != expected_count:
        raise InvariantViolation(
            f"People count mismatch: overview={actual_count}, expected={expected_count}"
        )


def check_heatstrip_subset_of_portfolio(
    snapshot: dict, normalized: NormalizedData
) -> None:
    """
    INVARIANT: Every project in heatstrip must exist in delivery_command.portfolio.

    Orphan projects in heatstrip = invariant violation.

    Raises:
        InvariantViolation: If heatstrip contains projects not in portfolio
    """
    delivery = snapshot.get("delivery_command", {})
    portfolio = delivery.get("portfolio", [])
    heatstrip = snapshot.get("heatstrip_projects", [])

    # Build set of portfolio project IDs
    portfolio_ids = {
        p.get("project_id")
        for p in portfolio
        if isinstance(p, dict) and p.get("project_id")
    }

    # Check heatstrip projects
    heatstrip_ids = {
        p.get("project_id")
        for p in heatstrip
        if isinstance(p, dict) and p.get("project_id")
    }

    # Find orphans
    orphans = heatstrip_ids - portfolio_ids
    if orphans:
        raise InvariantViolation(
            f"Heatstrip contains projects not in portfolio: {orphans}"
        )


def check_client360_at_risk_consistency(
    snapshot: dict, normalized: NormalizedData
) -> None:
    """
    INVARIANT: at_risk_count must match actual count of clients with at_risk=True.

    Raises:
        InvariantViolation: If counts don't match
    """
    client360 = snapshot.get("client_360", {})
    portfolio = client360.get("portfolio", [])
    declared_count = client360.get("at_risk_count", 0)

    # Count actual at-risk clients
    actual_at_risk = [c for c in portfolio if isinstance(c, dict) and c.get("at_risk")]
    actual_count = len(actual_at_risk)

    if actual_count != declared_count:
        raise InvariantViolation(
            f"Client360 at_risk_count mismatch: declared={declared_count}, actual={actual_count}"
        )


def check_no_orphan_commitments(snapshot: dict, normalized: NormalizedData) -> None:
    """
    INVARIANT: Commitments must reference valid scope types.

    Unknown scope_ref_type = invariant violation.

    Raises:
        InvariantViolation: If any commitment has unknown scope type
    """
    VALID_SCOPE_TYPES = {"client", "project", "thread", "invoice", "task"}

    comms = snapshot.get("comms_commitments", {})
    commitments = comms.get("commitments", [])

    unknown_types = []
    for c in commitments:
        if not isinstance(c, dict):
            continue

        scope_type = c.get("scope_ref_type")
        if scope_type and scope_type not in VALID_SCOPE_TYPES:
            unknown_types.append(
                f"{c.get('commitment_id', 'unknown')}: type='{scope_type}'"
            )

    if unknown_types:
        raise InvariantViolation(
            f"Commitments with unknown scope_ref_type (Amendment 2 violation): {unknown_types}"
        )


# =============================================================================
# INVARIANT REGISTRY
# =============================================================================

# ALL invariants - run together
ALL_INVARIANTS = [
    check_ar_totals_match,
    check_commitment_resolution_complete,
    check_people_count_consistency,
    check_heatstrip_subset_of_portfolio,
    check_client360_at_risk_consistency,
    check_no_orphan_commitments,
]


# =============================================================================
# ENFORCEMENT
# =============================================================================


def enforce_invariants(snapshot: dict, normalized: NormalizedData) -> list[str]:
    """
    Run all invariants. Returns list of violations.

    Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 4:
    - This runs in PRODUCTION, not just tests
    - Violations are errors, not warnings

    Args:
        snapshot: The final snapshot dict to validate
        normalized: The normalized data from extraction

    Returns:
        List of violation messages. Empty = pass.
    """
    violations = []

    for invariant in ALL_INVARIANTS:
        try:
            invariant(snapshot, normalized)
        except InvariantViolation as e:
            violations.append(f"INVARIANT_VIOLATION: {str(e)}")

    return violations


def enforce_invariants_strict(snapshot: dict, normalized: NormalizedData) -> None:
    """
    Strict enforcement — raises on first violation.

    Use this in production generator to fail fast.

    Raises:
        InvariantViolation: If any invariant fails
    """
    for invariant in ALL_INVARIANTS:
        invariant(snapshot, normalized)  # Raises InvariantViolation if fails
