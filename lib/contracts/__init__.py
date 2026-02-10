"""
Contracts Module — Multi-Layer Validation for Agency Snapshot Generator.

This module provides:
- schema.py: Pydantic models for shape validation
- predicates.py: Section existence rules
- invariants.py: Semantic correctness checks
- thresholds.py: Quality gates with justifications

All validation is enforced BOTH in tests AND in production.
The generator MUST call these gates before emitting output.
"""

from .invariants import (
    ALL_INVARIANTS,
    InvariantViolation,
    enforce_invariants,
    enforce_invariants_strict,
)
from .predicates import (
    SECTION_PREDICATES,
    PredicateViolation,
    enforce_predicates,
    enforce_predicates_strict,
)
from .schema import (
    SCHEMA_VERSION,
    AgencySnapshotContract,
    CapacityCommandSection,
    CashARSection,
    Client360Section,
    CommsCommitmentsSection,
    DebtorEntry,
    DeliveryCommandSection,
    HeatstripProject,
    PortfolioProject,
)
from .thresholds import (
    THRESHOLDS,
    ThresholdViolation,
    enforce_thresholds,
    enforce_thresholds_strict,
    get_thresholds_for_environment,
)

__all__ = [
    # Schema
    "SCHEMA_VERSION",
    "AgencySnapshotContract",
    "CashARSection",
    "DebtorEntry",
    "DeliveryCommandSection",
    "PortfolioProject",
    "Client360Section",
    "CommsCommitmentsSection",
    "CapacityCommandSection",
    "HeatstripProject",
    # Predicates
    "SECTION_PREDICATES",
    "enforce_predicates",
    "enforce_predicates_strict",
    "PredicateViolation",
    # Invariants
    "ALL_INVARIANTS",
    "enforce_invariants",
    "enforce_invariants_strict",
    "InvariantViolation",
    # Thresholds
    "THRESHOLDS",
    "ThresholdViolation",
    "enforce_thresholds",
    "enforce_thresholds_strict",
    "get_thresholds_for_environment",
]
