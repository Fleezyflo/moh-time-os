"""
Normalize Module — Canonical Data Representation and Resolution.

This module provides:
- domain_models.py: Canonical types + NormalizedData with stats
- resolvers.py: Exhaustive resolvers with metrics
- extractors/: Per-domain extraction logic

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- Resolution happens HERE, not in aggregation
- Unknown types RAISE (Amendment 2)
- Resolution metrics tracked for thresholds
"""

from .domain_models import (
    Client,
    Commitment,
    Communication,
    Invoice,
    NormalizedData,
    Person,
    Project,
    ResolutionStats,
)
from .resolvers import (
    CommitmentResolver,
    ResolutionFailure,
    ResolutionMetrics,
    ResolutionResult,
    ScopeRefType,
)

__all__ = [
    # Domain models
    "NormalizedData",
    "Project",
    "Client",
    "Invoice",
    "Commitment",
    "Communication",
    "Person",
    "ResolutionStats",
    # Resolvers
    "ScopeRefType",
    "ResolutionResult",
    "ResolutionMetrics",
    "CommitmentResolver",
    "ResolutionFailure",
]
