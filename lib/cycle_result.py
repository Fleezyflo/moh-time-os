"""
CycleResult dataclass for autonomous loop tracking.

Provides structured tracking of cycle execution with per-phase results.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PhaseResult:
    """Result of a single phase execution."""

    name: str
    success: bool
    error: str | None = None
    duration_seconds: float = 0.0
    data: dict = field(default_factory=dict)


@dataclass
class CycleResult:
    """Result of a complete autonomous cycle."""

    cycle_number: int
    started_at: datetime
    completed_at: datetime
    phases: list[PhaseResult] = field(default_factory=list)
    overall_success: bool = True
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def failed_phases(self) -> list[str]:
        """Get names of failed phases."""
        return [p.name for p in self.phases if not p.success]

    @property
    def succeeded_phases(self) -> list[str]:
        """Get names of successful phases."""
        return [p.name for p in self.phases if p.success]

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "cycle_number": self.cycle_number,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "overall_success": self.overall_success,
            "error": self.error,
            "phases": [
                {
                    "name": p.name,
                    "success": p.success,
                    "error": p.error,
                    "duration_seconds": p.duration_seconds,
                }
                for p in self.phases
            ],
            "failed_phases": self.failed_phases,
            "succeeded_phases": self.succeeded_phases,
        }
