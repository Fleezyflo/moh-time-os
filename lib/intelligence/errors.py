"""
Typed exceptions for the intelligence layer.

These exist so that distinct failure modes (DB lock, missing view, query error)
surface as named errors instead of being masked as empty results — enforcing the
CLAUDE.md rule "No return [] on failure".

TrajectoryComputationError subclasses OSError so that existing call sites which
already catch (sqlite3.Error, ValueError, OSError) continue to handle the failure,
while still being able to distinguish it by type.
"""


class IntelligenceError(OSError):
    """Base class for intelligence-layer failures (subclass of OSError)."""


class TrajectoryComputationError(IntelligenceError):
    """Raised when portfolio/client trajectory computation fails at the engine."""
