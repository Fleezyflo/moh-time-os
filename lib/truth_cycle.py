"""
Truth Cycle Orchestrator

Runs all 4 truth modules in dependency order and produces a unified
truth state that the intelligence engine and agency snapshot consume.

Dependency order:
  1. Time Truth — sync calendar, manage blocks, run scheduler
  2. Commitment Truth — detect commitments, update lifecycle
  3. Capacity Truth — calculate lane utilization, track debt
  4. Client Truth — compute health scores using signals + capacity + commitments
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from lib import paths
from lib.compat import UTC

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Result from a single truth stage."""

    name: str
    ok: bool
    counts: dict = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class TruthCycleResult:
    """Aggregated result from running all truth stages."""

    stages: dict[str, StageResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def all_ok(self) -> bool:
        return all(s.ok for s in self.stages.values())

    @property
    def passed(self) -> int:
        return sum(1 for s in self.stages.values() if s.ok)

    @property
    def failed(self) -> int:
        return sum(1 for s in self.stages.values() if not s.ok)


class TruthCycle:
    """Orchestrates the 4 truth modules in dependency order."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(paths.db_path())

    def run(self) -> TruthCycleResult:
        """Execute all truth modules in dependency order.

        Each stage runs independently — a failure in one does not block others.
        """
        result = TruthCycleResult()
        today = date.today().isoformat()

        # Stage 1: Time Truth
        stage = self._run_time_truth(today)
        result.stages["time"] = stage
        if not stage.ok:
            result.errors.append(f"time: {stage.error}")

        # Stage 2: Commitment Truth
        stage = self._run_commitment_truth()
        result.stages["commitments"] = stage
        if not stage.ok:
            result.errors.append(f"commitments: {stage.error}")

        # Stage 3: Capacity Truth
        stage = self._run_capacity_truth(today)
        result.stages["capacity"] = stage
        if not stage.ok:
            result.errors.append(f"capacity: {stage.error}")

        # Stage 4: Client Truth
        stage = self._run_client_truth()
        result.stages["client_health"] = stage
        if not stage.ok:
            result.errors.append(f"client_health: {stage.error}")

        status = "OK" if result.all_ok else f"{result.failed} failures"
        logger.info(
            "Truth cycle complete: %d/%d stages passed (%s)",
            result.passed,
            len(result.stages),
            status,
        )
        return result

    def _run_time_truth(self, today: str) -> StageResult:
        """Stage 1: Calendar sync → block management → scheduling."""
        start = datetime.now(UTC)
        try:
            from lib.time_truth.block_manager import BlockManager
            from lib.time_truth.scheduler import Scheduler

            bm = BlockManager(self.db_path)
            sched = Scheduler(self.db_path)

            # Create blocks from calendar events for today
            blocks = bm.get_all_blocks(today)
            block_count = len(blocks)

            # Run scheduler for unscheduled tasks
            scheduled = sched.schedule_unscheduled(today)
            scheduled_count = len(scheduled)

            # Get summary
            summary = sched.get_scheduling_summary(today)

            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return StageResult(
                name="time",
                ok=True,
                counts={
                    "blocks_today": block_count,
                    "tasks_scheduled": scheduled_count,
                    "summary": summary,
                },
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.error("Time truth failed: %s\n%s", e, traceback.format_exc())
            return StageResult(name="time", ok=False, error=str(e), duration_ms=elapsed)

    def _run_commitment_truth(self) -> StageResult:
        """Stage 2: Detect commitments from communications, update lifecycle."""
        start = datetime.now(UTC)
        try:
            from lib.commitment_truth.commitment_manager import CommitmentManager

            cm = CommitmentManager()
            summary = cm.get_summary()

            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return StageResult(
                name="commitments",
                ok=True,
                counts=summary,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.error("Commitment truth failed: %s\n%s", e, traceback.format_exc())
            return StageResult(name="commitments", ok=False, error=str(e), duration_ms=elapsed)

    def _run_capacity_truth(self, today: str) -> StageResult:
        """Stage 3: Calculate lane utilization and track capacity debt."""
        start = datetime.now(UTC)
        try:
            from lib.capacity_truth.calculator import CapacityCalculator

            calc = CapacityCalculator()
            summary = calc.get_capacity_summary(today)

            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return StageResult(
                name="capacity",
                ok=True,
                counts=summary,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.error("Capacity truth failed: %s\n%s", e, traceback.format_exc())
            return StageResult(name="capacity", ok=False, error=str(e), duration_ms=elapsed)

    def _run_client_truth(self) -> StageResult:
        """Stage 4: Compute client health scores."""
        start = datetime.now(UTC)
        try:
            from lib.client_truth.health_calculator import HealthCalculator

            hc = HealthCalculator()
            at_risk = hc.get_at_risk_clients()
            at_risk_count = len(at_risk)

            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return StageResult(
                name="client_health",
                ok=True,
                counts={
                    "at_risk_clients": at_risk_count,
                },
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.error("Client truth failed: %s\n%s", e, traceback.format_exc())
            return StageResult(name="client_health", ok=False, error=str(e), duration_ms=elapsed)
