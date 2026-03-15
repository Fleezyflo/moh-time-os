"""
Time OS Daemon — Standalone Background Scheduler

A proper daemon process that:
- Runs independently of the web UI
- Handles its own scheduling with smart logic
- Detects sleep/wake and catches up missed runs
- Has proper signal handling and graceful shutdown
- Self-heals on failures with exponential backoff

Usage:
    python -m lib.daemon start          # Start daemon (foreground)
    python -m lib.daemon start --bg     # Start daemon (background, writes PID file)
    python -m lib.daemon stop           # Stop running daemon
    python -m lib.daemon status         # Check if running
    python -m lib.daemon run-once       # Run one cycle and exit

Or via CLI:
    python cli_v2.py daemon start
"""

import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from lib import paths
from lib.collectors.resilience import CircuitBreaker
from lib.compat import StrEnum
from lib.observability.metrics import REGISTRY

_orchestrator = None  # Lazy-loaded on first use
_orchestrator_lock = threading.Lock()


def _get_orchestrator():
    """Lazy-import orchestrator to avoid import-time side effects.

    Thread-safe: uses double-checked locking to prevent multiple instantiation.
    """
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    with _orchestrator_lock:
        if _orchestrator is None:
            from lib.collectors.orchestrator import CollectorOrchestrator

            _orchestrator = CollectorOrchestrator()
        return _orchestrator


class JobHealth(StrEnum):
    """Health status for scheduled jobs."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


logger = logging.getLogger(__name__)


# Paths - centralized via lib/paths.py
def _project_root():
    return paths.project_root()


def _pid_file():
    return paths.data_dir() / "daemon.pid"


def _state_file():
    return paths.data_dir() / "daemon_state.json"


def _log_file():
    return paths.data_dir() / "daemon.log"


# Configure logging
def setup_logging(to_file: bool = False):
    """Configure daemon logging with rotation when writing to file."""
    handlers = [logging.StreamHandler()]
    if to_file:
        _log_file().parent.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            _log_file(),
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=5,
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    return logging.getLogger("timeos.daemon")


@dataclass
class JobConfig:
    """Configuration for a scheduled job."""

    name: str
    interval_minutes: int
    command: list
    timeout_seconds: int | None = None  # None = no timeout
    retry_on_fail: bool = True
    max_retries: int = 3
    backoff_base: int = 2  # Exponential backoff base


@dataclass
class JobState:
    """Runtime state for a job."""

    last_run: datetime | None = None
    last_success: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    total_runs: int = 0
    total_failures: int = 0
    health_status: JobHealth = JobHealth.HEALTHY
    circuit_breaker: CircuitBreaker | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if job is in healthy state."""
        return self.health_status == JobHealth.HEALTHY


class TimeOSDaemon:
    """
    Standalone daemon for Time OS background jobs.

    Features:
    - Interval-based scheduling with drift correction
    - Sleep/wake detection and catch-up
    - Exponential backoff on failures
    - Graceful shutdown on SIGTERM/SIGINT
    - State persistence across restarts
    """

    def __init__(self):
        self.logger = setup_logging(to_file=True)
        self.running = False
        self.jobs: dict[str, JobConfig] = {}
        self.job_states: dict[str, JobState] = {}
        self._shutdown_event = threading.Event()
        self._last_tick = datetime.now(timezone.utc)
        self._tick_count = 0

        # Register default jobs
        self._register_default_jobs()

        # Initialize circuit breakers for resilience
        self._initialize_circuit_breakers()
        # Load persisted state
        self._load_state()

    def _register_default_jobs(self):
        """Register the standard Time OS jobs."""

        # 8-stage pipeline (wiring remediation — activates detection + intelligence)
        # Stage 1: Collect data from all sources
        self.register_job(
            JobConfig(
                name="collect",
                interval_minutes=30,
                command=None,
            )
        )

        # Stage 2: Lane assignment (categorize tasks into capacity lanes)
        self.register_job(
            JobConfig(
                name="lane_assignment",
                interval_minutes=30,
                command=None,
            )
        )

        # Stage 3: Run truth cycle (time → commitment → capacity → client)
        self.register_job(
            JobConfig(
                name="truth_cycle",
                interval_minutes=15,
                command=None,
            )
        )

        # Stage 4: Detection system (collision, drift, bottleneck → production table)
        self.register_job(
            JobConfig(
                name="detection",
                interval_minutes=15,
                command=None,
            )
        )

        # Stage 5: Intelligence pipeline (scoring → signals → patterns → proposals)
        self.register_job(
            JobConfig(
                name="intelligence",
                interval_minutes=15,
                command=None,
            )
        )

        # Stage 6: Generate agency snapshot
        self.register_job(
            JobConfig(
                name="snapshot",
                interval_minutes=15,
                command=None,
            )
        )

        # Stage 7: Morning brief (daily detection digest via Google Chat)
        self.register_job(
            JobConfig(
                name="morning_brief",
                interval_minutes=15,
                command=None,
            )
        )

        # Stage 8: Send notifications
        self.register_job(
            JobConfig(
                name="notify",
                interval_minutes=60,
                command=None,
            )
        )

    def register_job(self, config: JobConfig):
        """Register a job with the daemon."""
        self.jobs[config.name] = config
        if config.name not in self.job_states:
            self.job_states[config.name] = JobState()

    def _load_state(self):
        """Load persisted job state from disk."""
        if _state_file().exists():
            try:
                with open(_state_file()) as f:
                    data = json.load(f)
                for name, state_data in data.get("jobs", {}).items():
                    if name in self.job_states:
                        state = self.job_states[name]
                        if state_data.get("last_run"):
                            state.last_run = datetime.fromisoformat(state_data["last_run"])
                        if state_data.get("last_success"):
                            state.last_success = datetime.fromisoformat(state_data["last_success"])
                        state.last_error = state_data.get("last_error")
                        state.consecutive_failures = state_data.get("consecutive_failures", 0)
                        state.total_runs = state_data.get("total_runs", 0)
                        state.total_failures = state_data.get("total_failures", 0)
                self.logger.info(f"Loaded state from {_state_file()}")
            except (sqlite3.Error, ValueError, OSError) as e:
                self.logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """Persist job state to disk."""
        try:
            data = {"jobs": {}, "updated_at": datetime.now(timezone.utc).isoformat()}
            for name, state in self.job_states.items():
                data["jobs"][name] = {
                    "last_run": state.last_run.isoformat() if state.last_run else None,
                    "last_success": state.last_success.isoformat() if state.last_success else None,
                    "last_error": state.last_error,
                    "consecutive_failures": state.consecutive_failures,
                    "total_runs": state.total_runs,
                    "total_failures": state.total_failures,
                }
            _state_file().parent.mkdir(parents=True, exist_ok=True)
            with open(_state_file(), "w") as f:
                json.dump(data, f, indent=2)
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.warning(f"Failed to save state: {e}")

    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for each job."""
        for job_name in self.jobs:
            if job_name not in self.job_states:
                self.job_states[job_name] = JobState()
            self.job_states[job_name].circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                cooldown_seconds=600,  # 10 minutes
            )

    def _update_job_health(self, job_name: str):
        """Update job health status based on consecutive failures."""
        state = self.job_states[job_name]
        old_status = state.health_status

        # Determine health based on consecutive failures
        if state.consecutive_failures == 0:
            state.health_status = JobHealth.HEALTHY
        elif state.consecutive_failures < 3:
            state.health_status = JobHealth.DEGRADED
        else:
            state.health_status = JobHealth.UNHEALTHY

        # Log status changes
        if old_status != state.health_status:
            self.logger.warning(
                f"{job_name} health changed: {old_status} -> {state.health_status} "
                f"({state.consecutive_failures} consecutive failures)"
            )

        # Update metrics
        REGISTRY.gauge(f"job_health_{job_name}", f"Health of job {job_name}").set(
            {
                "healthy": 1,
                "degraded": 0.5,
                "unhealthy": 0,
            }.get(state.health_status.value, 0)
        )

    def _log_memory_usage(self):
        """Log current memory usage via resource.getrusage()."""
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = usage.ru_maxrss / (1024 * 1024)  # macOS reports bytes
        self.logger.info(
            "Memory usage: RSS=%.1f MB, user_time=%.1f s, sys_time=%.1f s",
            rss_mb,
            usage.ru_utime,
            usage.ru_stime,
        )

    def get_job_health(self, job_name: str | None = None) -> dict:
        """
        Get health status for one or all jobs.

        Args:
            job_name: Specific job, or None for all jobs

        Returns:
            Health status dict
        """
        if job_name:
            if job_name not in self.job_states:
                return {"error": f"Job {job_name} not found"}

            state = self.job_states[job_name]
            cb = state.circuit_breaker
            return {
                "name": job_name,
                "health": state.health_status.value,
                "consecutive_failures": state.consecutive_failures,
                "total_failures": state.total_failures,
                "total_runs": state.total_runs,
                "last_error": state.last_error,
                "last_success": state.last_success.isoformat() if state.last_success else None,
                "circuit_breaker": {
                    "state": cb.state if cb else None,
                    "failure_count": cb.failure_count if cb else None,
                }
                if cb
                else None,
            }

        return {jn: self.get_job_health(jn) for jn in self.jobs}

    def _should_run(self, job_name: str) -> bool:
        """Determine if a job should run now."""
        config = self.jobs[job_name]
        state = self.job_states[job_name]

        # Never run before
        if state.last_run is None:
            return True

        # Check interval
        elapsed = datetime.now(timezone.utc) - state.last_run
        interval = timedelta(minutes=config.interval_minutes)

        # Apply backoff if failing
        if state.consecutive_failures > 0 and config.retry_on_fail:
            backoff_minutes = min(
                config.interval_minutes,  # Cap at normal interval
                config.backoff_base**state.consecutive_failures,
            )
            interval = timedelta(minutes=backoff_minutes)
            self.logger.debug(
                f"{job_name}: backoff {backoff_minutes}m (failures: {state.consecutive_failures})"
            )

        return elapsed >= interval

    def _detect_sleep_wake(self) -> timedelta:
        """Detect if system was asleep and return sleep duration."""
        now = datetime.now(timezone.utc)
        elapsed = now - self._last_tick
        self._last_tick = now

        # If more than 2 minutes passed since last tick, system probably slept
        if elapsed > timedelta(minutes=2):
            return elapsed - timedelta(seconds=30)  # Subtract expected tick time
        return timedelta(0)

    def _run_job(self, job_name: str) -> bool:
        """Execute a job and return success status."""
        self.jobs[job_name]
        state = self.job_states[job_name]
        circuit_breaker = state.circuit_breaker

        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.can_execute():
            self.logger.warning(
                f"⊘ {job_name} SKIPPED - circuit breaker is {circuit_breaker.state}"
            )
            state.last_error = f"Circuit breaker {circuit_breaker.state}"
            state.consecutive_failures += 1
            state.total_runs += 1
            self._update_job_health(job_name)
            return False

        self.logger.info(f"▶ Running {job_name}...")
        start = datetime.now(timezone.utc)
        state.last_run = start
        state.total_runs += 1

        try:
            # Route to handler function
            if job_name == "collect":
                self._handle_collect()
            elif job_name == "lane_assignment":
                self._handle_lane_assignment()
            elif job_name == "truth_cycle":
                self._handle_truth_cycle()
            elif job_name == "detection":
                self._handle_detection()
            elif job_name == "intelligence":
                self._handle_intelligence()
            elif job_name == "snapshot":
                self._handle_snapshot()
            elif job_name == "morning_brief":
                self._handle_morning_brief()
            elif job_name == "notify":
                self._handle_notify()
            else:
                raise ValueError(f"Unknown job: {job_name}")
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            state.last_success = datetime.now(timezone.utc)
            state.last_error = None
            state.consecutive_failures = 0
            self._update_job_health(job_name)
            if circuit_breaker:
                circuit_breaker.record_success()
            self.logger.info(f"✓ {job_name} completed in {duration:.1f}s")
            return True

        except (sqlite3.Error, ValueError, OSError) as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            state.last_error = str(e)[:500]
            state.total_failures += 1
            state.consecutive_failures += 1
            if circuit_breaker:
                circuit_breaker.record_failure()
            self.logger.error(f"✗ {job_name} failed in {duration:.1f}s: {state.last_error[:100]}")
            self._update_job_health(job_name)
            return False

    def _handle_collect(self):
        """Stage 1: Collect data from all sources."""
        try:
            orchestrator = _get_orchestrator()
            self.logger.info("Collecting data from all sources...")
            orchestrator.sync_all()
        except ImportError:
            self.logger.warning("Collector orchestrator not available, skipping collect")
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.error(f"Collect failed: {e}")
            raise

    def _handle_lane_assignment(self):
        """Stage 2: Categorize tasks into capacity lanes."""
        try:
            from lib.lane_assigner import run_assignment

            self.logger.info("Running lane assignment...")
            result = run_assignment()
            changed = result.get("changed", 0)
            if changed > 0:
                self.logger.info(f"Lane assignment: {changed} tasks reassigned")
            else:
                self.logger.info("Lane assignment: no changes")
        except ImportError:
            self.logger.warning("Lane assigner not available, skipping")
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.error(f"Lane assignment failed: {e}")
            raise

    def _handle_truth_cycle(self):
        """Stage 3: Run truth cycle."""
        from lib.truth_cycle import TruthCycle

        self.logger.info("Running truth cycle...")
        cycle = TruthCycle(str(paths.db_path()))
        result = cycle.run()
        self.logger.info(f"Truth cycle: {result.passed}/{len(result.stages)} stages passed")
        if result.errors:
            self.logger.warning(f"Truth cycle warnings: {result.errors}")

        # Empty-data guard: warn if all truth stages returned zero counts
        all_zero = True
        for _stage_name, stage_result in result.stages.items():
            counts = stage_result.counts or {}
            if any(v for v in counts.values() if isinstance(v, int) and v > 0):
                all_zero = False
                break
        if all_zero and result.all_ok:
            self.logger.warning(
                "STARVED: Truth cycle passed but all stages returned zero counts. "
                "Collectors may not be populating data."
            )

    def _handle_detection(self):
        """Stage 4: Run collision, drift, bottleneck detectors → production table."""
        from lib.detectors import run_all_detectors

        db_path = str(paths.db_path())
        self.logger.info("Running detection system (production mode)...")
        results = run_all_detectors(
            db_path=db_path,
            dry_run=False,  # Write to detection_findings, not preview
            cycle_id=f"daemon_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        )
        total_findings = sum(d.get("findings", 0) for d in results.get("detectors", {}).values())
        groups = results.get("correlation", {}).get("groups", 0)
        storage = results.get("storage", {})
        self.logger.info(
            f"Detection: {total_findings} raw findings, {groups} correlated groups, "
            f"{storage.get('inserted', 0)} new, {storage.get('updated', 0)} updated"
        )

    def _handle_intelligence(self):
        """Stage 5: Signal detection + state update + V4 proposal generation.

        Canonical pipeline (per CANONICALIZATION.md):
        - detect_all_signals() → find active signals from collector data
        - update_signal_state() → persist to signal_state table (new/ongoing/escalated/cleared)
        - ProposalService.generate_proposals_from_signals() → group signals → proposals_v4

        The full intelligence engine (generate_intelligence_snapshot) is reserved for
        API-time use (briefing endpoint). The daemon only populates the tables those
        endpoints read from.
        """
        from pathlib import Path

        db_path_str = str(paths.db_path())
        db_path_obj = Path(db_path_str)

        # Step 1: Detect signals from current data
        self.logger.info("Running signal detection...")
        try:
            from lib.intelligence.signals import detect_all_signals, update_signal_state

            detection = detect_all_signals(db_path_obj, quick=True)
            detected_signals = detection.get("signals", [])
            self.logger.info(f"Signals detected: {len(detected_signals)}")

            # Step 2: Update signal state (persist new/ongoing/escalated/cleared)
            if detected_signals:
                state_update = update_signal_state(detected_signals, db_path_obj)
                new_count = len(state_update.get("new_signals", []))
                escalated_count = len(state_update.get("escalated_signals", []))
                cleared_count = len(state_update.get("cleared_signals", []))
                self.logger.info(
                    f"Signal state: {new_count} new, {escalated_count} escalated, "
                    f"{cleared_count} cleared"
                )
            else:
                self.logger.info("No signals detected, skipping state update")
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.warning(f"Signal detection/update failed: {e}")

        # Step 3: Generate V4 proposals from persisted signal state
        try:
            from lib.v4.proposal_service import ProposalService

            svc = ProposalService(db_path=db_path_str)
            prop_result = svc.generate_proposals_from_signals()
            self.logger.info(
                f"V4 proposals: {prop_result.get('created', 0)} created, "
                f"{prop_result.get('updated', 0)} updated, "
                f"{prop_result.get('skipped', 0)} skipped"
            )
        except (sqlite3.Error, ValueError, OSError, ImportError) as e:
            self.logger.warning(f"V4 proposal generation skipped: {e}")

    def _handle_morning_brief(self):
        """Stage 7: Send morning brief if findings changed (daily, via Google Chat)."""
        import os

        webhook_url = os.environ.get("MOH_GCHAT_WEBHOOK_URL", "")
        if not webhook_url:
            self.logger.debug("Morning brief skipped: MOH_GCHAT_WEBHOOK_URL not set")
            return

        try:
            from lib.detectors.morning_brief import send_if_changed
            from lib.notifier.channels.google_chat import GoogleChatChannel

            db_path = str(paths.db_path())

            # Build a minimal notifier-like object with a google_chat channel
            channel = GoogleChatChannel(webhook_url=webhook_url, dry_run=False)

            class _BriefNotifier:
                """Minimal notifier interface for morning brief."""

                def __init__(self, ch):
                    self.channels = {"google_chat": ch}

            notifier = _BriefNotifier(channel)
            result = send_if_changed(
                db_path=db_path,
                notifier=notifier,
                morning_brief_hour=8,
            )
            self.logger.info(f"Morning brief: {result.get('status', 'unknown')}")
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.warning(f"Morning brief failed: {e}")

    def _handle_snapshot(self):
        """Stage 6: Generate agency snapshot."""
        import os

        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        # Use artifact_validation thresholds (most lenient) for daemon cycles
        # This allows snapshot generation even with incomplete data linkages
        if "MOH_TIME_OS_ENV" not in os.environ:
            os.environ["MOH_TIME_OS_ENV"] = "artifact_validation"

        self.logger.info("Generating agency snapshot...")
        try:
            generator = AgencySnapshotGenerator(db_path=paths.db_path())
            snapshot = generator.generate()
            generator.save(snapshot)
            self.logger.info(f"Snapshot saved to {paths.out_dir() / 'agency_snapshot.json'}")
        except (sqlite3.Error, ValueError, OSError) as e:
            # Log the validation error but try to save minimal snapshot
            self.logger.warning(f"Snapshot validation failed: {e}")
            # Generate and save without strict validation
            generator = AgencySnapshotGenerator(db_path=paths.db_path())
            # Build minimal snapshot directly
            snapshot = {
                "meta": generator._build_meta(datetime.now(timezone.utc)),
                "trust": {"gates": [], "confidence_level": "unknown"},
                "narrative": {"first_to_break": None, "deltas": []},
                "tiles": generator._build_tiles_minimal(),
                "heatstrip_projects": [],
                "constraints": [],
                "exceptions": [],
                "delivery_command": {"portfolio": [], "selected_project": None},
                "client_360": {"portfolio": [], "at_risk_count": 0, "drawer": {}},
                "cash_ar": {"tiles": {}, "debtors": []},
                "comms_commitments": {"threads": [], "commitments": [], "overdue_count": 0},
                "capacity_command": {
                    "people_overview": [],
                    "total_assigned": 0,
                    "total_capacity": 0,
                    "utilization_rate": 0,
                    "drawer": {},
                },
                "drawers": {},
            }
            snapshot["meta"]["finished_at"] = datetime.now(timezone.utc).isoformat()
            generator.save(snapshot)
            self.logger.info("Minimal snapshot saved")

    def _handle_notify(self):
        """Stage 8: Log cycle completion. Outbound delivery is handled by morning_brief.

        Per CANONICALIZATION.md: "cycle complete" messages are noise on the Google Chat
        channel. The morning brief is the canonical outbound. This stage just logs.
        """
        self.logger.info("Daemon cycle notification: all stages complete")

    def run_once(self):
        """Run all jobs once in sequence and exit."""
        self.logger.info("=" * 50)
        self.logger.info("Running one-shot cycle")
        self.logger.info("=" * 50)

        jobs_to_run = [
            "collect",
            "lane_assignment",
            "truth_cycle",
            "detection",
            "intelligence",
            "snapshot",
            "morning_brief",
            "notify",
        ]
        succeeded = 0
        failed = 0

        for job_name in jobs_to_run:
            self.logger.info(f"\n--- Stage: {job_name} ---")
            if self._run_job(job_name):
                succeeded += 1
            else:
                failed += 1

        self._save_state()
        self.logger.info("\n--- Cycle Complete ---")
        self.logger.info(f"Succeeded: {succeeded}/{len(jobs_to_run)}")
        if failed > 0:
            self.logger.warning(f"Failed: {failed}/{len(jobs_to_run)}")

    def run(self):
        """Main daemon loop."""
        self.running = True
        self.logger.info("=" * 50)
        self.logger.info("Time OS Daemon starting")
        self.logger.info(f"Jobs: {', '.join(self.jobs.keys())}")
        self.logger.info("=" * 50)

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Write PID file
        self._write_pid()

        try:
            while self.running:
                # Check for sleep/wake
                sleep_duration = self._detect_sleep_wake()
                if sleep_duration > timedelta(minutes=1):
                    self.logger.info(f"⏰ Detected wake from sleep ({sleep_duration})")

                # Check and run jobs
                for job_name in self.jobs:
                    if self._shutdown_event.is_set():
                        break
                    if self._should_run(job_name):
                        self._run_job(job_name)
                        self._save_state()

                # Log memory every 10 cycles (~5 minutes)
                self._tick_count += 1
                if self._tick_count % 10 == 0:
                    self._log_memory_usage()

                # Sleep until next check (30 seconds)
                self._shutdown_event.wait(timeout=30)

        finally:
            self._cleanup()

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        self.logger.info(f"Received {sig_name}, shutting down...")
        self.running = False
        self._shutdown_event.set()

    def _write_pid(self):
        """Write PID file."""
        _pid_file().parent.mkdir(parents=True, exist_ok=True)
        _pid_file().write_text(str(os.getpid()))
        self.logger.info(f"PID {os.getpid()} written to {_pid_file()}")

    def _cleanup(self):
        """Cleanup on shutdown."""
        self._save_state()
        if _pid_file().exists():
            _pid_file().unlink()
        self.logger.info("Daemon stopped")

    @staticmethod
    def is_running() -> tuple[bool, int | None]:
        """Check if daemon is running. Returns (is_running, pid)."""
        if not _pid_file().exists():
            return False, None

        try:
            pid = int(_pid_file().read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, ValueError):
            # Process doesn't exist, clean up stale PID file
            _pid_file().unlink(missing_ok=True)
            return False, None
        except PermissionError:
            # Process exists but we can't signal it
            return True, pid

    @staticmethod
    def stop():
        """Stop the running daemon."""
        running, pid = TimeOSDaemon.is_running()
        if not running:
            logger.info("Daemon is not running")
            return False

        logger.info(f"Stopping daemon (PID {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for it to stop
            for _ in range(10):
                time.sleep(0.5)
                if not TimeOSDaemon.is_running()[0]:
                    logger.info("Daemon stopped")
                    return True
            # Force kill
            os.kill(pid, signal.SIGKILL)
            logger.info("Daemon force killed")
            return True
        except ProcessLookupError:
            _pid_file().unlink(missing_ok=True)
            logger.info("Daemon already stopped")
            return True

    @staticmethod
    def status() -> dict:
        """Get daemon status."""
        running, pid = TimeOSDaemon.is_running()

        status = {
            "running": running,
            "pid": pid,
            "pid_file": str(_pid_file()),
            "state_file": str(_state_file()),
            "log_file": str(_log_file()),
            "jobs": {},
        }

        # Load job states
        if _state_file().exists():
            try:
                with open(_state_file()) as f:
                    data = json.load(f)
                status["jobs"] = data.get("jobs", {})
                status["state_updated"] = data.get("updated_at")
            except (json.JSONDecodeError, OSError) as e:
                # State file exists but is corrupt/unreadable
                logger.warning(f"Could not load daemon state: {e}")

        return status


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Time OS Daemon")
    parser.add_argument(
        "action",
        choices=["start", "stop", "status", "run-once"],
        help="Action to perform",
    )
    parser.add_argument("--bg", action="store_true", help="Run in background (start only)")

    args = parser.parse_args()

    if args.action == "start":
        running, pid = TimeOSDaemon.is_running()
        if running:
            logger.info(f"Daemon already running (PID {pid})")
            sys.exit(1)

        if args.bg:
            # Fork to background
            pid = os.fork()
            if pid > 0:
                logger.info(f"Daemon started in background (PID {pid})")
                sys.exit(0)
            # Child process continues
            os.setsid()

        daemon = TimeOSDaemon()
        daemon.run()

    elif args.action == "stop":
        TimeOSDaemon.stop()

    elif args.action == "status":
        status = TimeOSDaemon.status()
        logger.info(f"Running: {status['running']}")
        if status["pid"]:
            logger.info(f"PID: {status['pid']}")
        if status.get("state_updated"):
            logger.info(f"State updated: {status['state_updated']}")
        logger.info("\nJobs:")
        for name, job in status.get("jobs", {}).items():
            last_run = job.get("last_run", "never")[:19] if job.get("last_run") else "never"
            failures = job.get("consecutive_failures", 0)
            status_str = "✓" if failures == 0 else f"✗ ({failures} failures)"
            logger.info(f"  {name}: last run {last_run} {status_str}")
    elif args.action == "run-once":
        daemon = TimeOSDaemon()
        daemon.run_once()


if __name__ == "__main__":
    main()
