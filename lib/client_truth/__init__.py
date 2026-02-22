"""
Client Truth Module

Computes client health scores and surfaces at-risk relationships.

Dependencies:

Objects:
- Client (with health score, tier, activity)
- ClientProject (project-client link)

Invariants:
- Every project maps to zero or one client
- Health scores are 0-100
- At-risk clients (<50 health) surface in briefs
"""

from .health_calculator import HealthCalculator
from .linker import ClientLinker

__all__ = ["HealthCalculator", "ClientLinker"]
