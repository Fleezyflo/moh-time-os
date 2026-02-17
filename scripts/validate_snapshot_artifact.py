#!/usr/bin/env python3
"""
validate_snapshot_artifact.py — External Validation of Agency Snapshot Artifact

This script validates an agency_snapshot.json file OUTSIDE of the generator
to prove the artifact is contract-compliant (not just "it logged VALID").

Runs ALL gates explicitly:
1. Predicates (section existence rules)
2. Invariants (semantic correctness)
3. Thresholds (quality metrics)
4. Schema validation (Pydantic model)

Usage:
    python scripts/validate_snapshot_artifact.py output/agency_snapshot.json
    python scripts/validate_snapshot_artifact.py path/to/snapshot.json

Exit codes:
    0: VALID (all gates pass)
    1: INVALID (one or more gates failed)
    2: ERROR (file not found, JSON parse error, etc.)
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.contracts import (
    SCHEMA_VERSION,
    AgencySnapshotContract,
    InvariantViolation,
    PredicateViolation,
    ThresholdViolation,
    enforce_invariants_strict,
    enforce_predicates_strict,
    enforce_thresholds_strict,
)
from lib.contracts.predicates import NormalizedData
from lib.contracts.thresholds import ResolutionStats

# Configure logging for CLI output (no timestamps, just messages)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def build_normalized_from_snapshot(snapshot: dict) -> NormalizedData:
    """
    Build NormalizedData from snapshot for validation.

    This reconstructs the minimal normalized data needed for gate validation.
    """
    from dataclasses import dataclass

    @dataclass
    class MinimalClient:
        id: str
        name: str
        status: str = "active"

    @dataclass
    class MinimalProject:
        id: str
        name: str
        client_id: str | None = None
        status: str = "active"

    @dataclass
    class MinimalInvoice:
        id: str
        client_id: str | None = None
        status: str = "draft"
        amount: float = 0.0

    @dataclass
    class MinimalCommitment:
        id: str
        client_id: str | None = None
        resolved: bool = False

    @dataclass
    class MinimalThread:
        id: str
        client_id: str | None = None

    @dataclass
    class MinimalPerson:
        id: str
        name: str
        hours: float = 0.0

    # Extract from snapshot
    clients = []
    for c in snapshot.get("clients", []):
        clients.append(
            MinimalClient(
                id=c.get("id", ""),
                name=c.get("name", ""),
                status=c.get("status", "active"),
            )
        )

    projects = []
    for p in snapshot.get("projects", []):
        projects.append(
            MinimalProject(
                id=p.get("id", ""),
                name=p.get("name", ""),
                client_id=p.get("client_id"),
                status=p.get("status", "active"),
            )
        )

    invoices = []
    ar_section = snapshot.get("ar", {})
    for inv in ar_section.get("invoices", []):
        invoices.append(
            MinimalInvoice(
                id=inv.get("id", ""),
                client_id=inv.get("client_id"),
                status=inv.get("status", "draft"),
                amount=inv.get("amount", 0),
            )
        )

    commitments = []
    comms_section = snapshot.get("comms", {})
    for comm in comms_section.get("commitments", []):
        commitments.append(
            MinimalCommitment(
                id=comm.get("id", ""),
                client_id=comm.get("client_id"),
                resolved=comm.get("resolved", False),
            )
        )

    threads = []
    for t in comms_section.get("threads", []):
        threads.append(MinimalThread(id=t.get("id", ""), client_id=t.get("client_id")))

    people = []
    for p in snapshot.get("people", []):
        people.append(
            MinimalPerson(id=p.get("id", ""), name=p.get("name", ""), hours=p.get("hours", 0))
        )

    return NormalizedData(
        clients=clients,
        projects=projects,
        invoices=invoices,
        commitments=commitments,
        threads=threads,
        people=people,
    )


def compute_resolution_stats(normalized: NormalizedData) -> ResolutionStats:
    """Compute resolution statistics from normalized data."""
    commitments_total = len(normalized.commitments)
    commitments_resolved = sum(1 for c in normalized.commitments if c.resolved)

    threads_total = len(normalized.threads)
    threads_with_client = sum(1 for t in normalized.threads if t.client_id)

    invoices_total = len(normalized.invoices)
    invoices_valid = sum(1 for i in normalized.invoices if i.client_id and i.status != "draft")

    people_total = len(normalized.people)
    people_with_hours = sum(1 for p in normalized.people if p.hours > 0)

    projects_total = len(normalized.projects)
    projects_with_client = sum(1 for p in normalized.projects if p.client_id)

    return ResolutionStats(
        commitments_total=commitments_total,
        commitments_resolved=commitments_resolved,
        threads_total=threads_total,
        threads_with_client=threads_with_client,
        invoices_total=invoices_total,
        invoices_valid=invoices_valid,
        people_total=people_total,
        people_with_hours=people_with_hours,
        projects_total=projects_total,
        projects_with_client=projects_with_client,
    )


def validate_artifact(filepath: Path) -> bool:
    """
    Validate an agency_snapshot.json artifact.

    Returns True if all gates pass, False otherwise.
    Logs detailed failure information on failure.
    """
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║           AGENCY SNAPSHOT ARTIFACT VALIDATION                ║")
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║ File: %-55s ║", str(filepath)[:55])
    logger.info("║ Expected Schema Version: %-36s ║", SCHEMA_VERSION)
    logger.info("╚══════════════════════════════════════════════════════════════╝")
    logger.info("")

    # Load file
    logger.info("Loading artifact...")
    try:
        with open(filepath) as f:
            snapshot = json.load(f)
    except FileNotFoundError:
        logger.error("ERROR: File not found: %s", filepath)
        return False
    except json.JSONDecodeError as e:
        logger.error("ERROR: Invalid JSON: %s", e)
        return False

    logger.info("  ✓ Loaded %s bytes", f"{len(json.dumps(snapshot)):,}")

    # Build normalized data for gates
    logger.info("Building normalized data from snapshot...")
    normalized = build_normalized_from_snapshot(snapshot)
    stats = compute_resolution_stats(normalized)
    logger.info(
        "  ✓ Projects: %d, Clients: %d, Invoices: %d",
        len(normalized.projects),
        len(normalized.clients),
        len(normalized.invoices),
    )

    # Gate 1: Predicates
    logger.info("")
    logger.info("Gate 1: PREDICATES (section existence rules)")
    try:
        enforce_predicates_strict(normalized, snapshot)
        logger.info("  ✓ PASSED")
    except PredicateViolation as e:
        logger.error("  ✗ FAILED: %s", e)
        return False

    # Gate 2: Invariants
    logger.info("")
    logger.info("Gate 2: INVARIANTS (semantic correctness)")
    try:
        enforce_invariants_strict(snapshot, normalized)
        logger.info("  ✓ PASSED")
    except InvariantViolation as e:
        logger.error("  ✗ FAILED: %s", e)
        return False

    # Gate 3: Thresholds
    logger.info("")
    logger.info("Gate 3: THRESHOLDS (quality metrics)")
    # Use artifact_validation environment (lenient for external artifacts)
    env = "artifact_validation"
    try:
        enforce_thresholds_strict(stats, env)
        logger.info("  ✓ PASSED (env=%s)", env)
    except ThresholdViolation as e:
        logger.error("  ✗ FAILED: %s", e)
        return False

    # Gate 4: Schema validation
    logger.info("")
    logger.info("Gate 4: SCHEMA (Pydantic model validation)")
    try:
        validated = AgencySnapshotContract.model_validate(snapshot)
        logger.info("  ✓ PASSED")
        logger.info("  ✓ schema_version: %s", validated.meta.schema_version)
    except Exception as e:
        logger.error("  ✗ FAILED: %s", e)
        return False

    # All gates passed
    logger.info("")
    logger.info("════════════════════════════════════════════════════════════════")
    logger.info("VALID — All validation gates passed")
    logger.info("════════════════════════════════════════════════════════════════")

    return True


def main():
    if len(sys.argv) < 2:
        logger.info("Usage: python scripts/validate_snapshot_artifact.py <path_to_snapshot.json>")
        logger.info("")
        logger.info("Example:")
        logger.info("  python scripts/validate_snapshot_artifact.py output/agency_snapshot.json")
        sys.exit(2)

    filepath = Path(sys.argv[1])

    if not filepath.exists():
        logger.error("ERROR: File not found: %s", filepath)
        sys.exit(2)

    is_valid = validate_artifact(filepath)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
