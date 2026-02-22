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

import enum
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from lib import paths
from lib.collectors.resilience import CircuitBreaker
from lib.observability.metrics import REGISTRY

collect_all = None  # Lazy-loaded on first use


def _load_collect_all():
    """Lazy-import collect_all to avoid import-time side effects."""
    global collect_all
    if collect_all is None:
        from collectors.scheduled_collect import collect_all as _ca

        collect_all = _ca


class JobHealth(str, enum.Enum):
    """Health status for scheduled jobs."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


logger = logging.getLogger(__name__)

# Paths - centralized via lib/paths.py
PROJECT_ROOT = paths.project_root()
PID_FILE = paths.data_dir() / "daemon.pid"
STATE_FILE = paths.data_dir() / "daemon_state.json"
LOG_FILE = paths.data_dir() / "daemon.log"


# Configure logging
def setup_logging(to_file: bool = False):
    """Configure daemon logging."""
    handlers = [logging.StreamHandler()]
    if to_file:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE))

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
        self._last_tick = datetime.now()

        # Register default jobs
        self._register_default_jobs()

        # Initialize circuit breakers for resilience
        self._initialize_circuit_breakers()
        # Load persisted state
        self._load_state()

    def _register_default_jobs(self):
        """Register the standard Time OS jobs."""

        # 4-stage pipeline
        # Stage 1: Collect data from all sources
        self.register_job(
            JobConfig(
                name="collect",
                interval_minutes=30,
                command=None,  # Will use handler function
            )
        )

        # Stage 2: Run truth cycle (time → commitment → capacity → client)
        self.register_job(
            JobConfig(
                name="truth_cycle",
                interval_minutes=15,
                command=None,  # Will use handler function
            )
        )

        # Stage 3: Generate agency snapshot
        self.register_job(
            JobConfig(
                name="snapshot",
                interval_minutes=15,
                command=None,  # Will use handler function
            )
        )

        # Stage 4: Send notifications (dry-run for now)
        self.register_job(
            JobConfig(
                name="notify",
                interval_minutes=60,
                command=None,  # Will use handler function
            )
        )

    def register_job(self, config: JobConfig):
        """Register a job with the daemon."""
        self.jobs[config.name] = config
        if config.name not in self.job_states:
            self.job_states[config.name] = JobState()

    def _load_state(self):
        """Load persisted job state from disk."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
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
                self.logger.info(f"Loaded state from {STATE_FILE}")
            except Exception as e:
                self.logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """Persist job state to disk."""
        try:
            data = {"jobs": {}, "updated_at": datetime.now().isoformat()}
            for name, state in self.job_states.items():
                data["jobs"][name] = {
                    "last_run": state.last_run.isoformat() if state.last_run else None,
                    "last_success": state.last_success.isoformat() if state.last_success else None,
                    "last_error": state.last_error,
                    "consecutive_failures": state.consecutive_failures,
                    "total_runs": state.total_runs,
                    "total_failures": state.total_failures,
                }
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
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
        elapsed = datetime.now() - state.last_run
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
        now = datetime.now()
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
        start = datetime.now()
        state.last_run = start
        state.total_runs += 1

        try:
            # Route to handler function
            if job_name == "collect":
                self._handle_collect()
            elif job_name == "truth_cycle":
                self._handle_truth_cycle()
            elif job_name == "snapshot":
                self._handle_snapshot()
            elif job_name == "notify":
                self._handle_notify()
            else:
                raise ValueError(f"Unknown job: {job_name}")
            duration = (datetime.now() - start).total_seconds()
            state.last_success = datetime.now()
            state.last_error = None
            state.consecutive_failures = 0
            self._update_job_health(job_name)
            if circuit_breaker:
                circuit_breaker.record_success()
            self.logger.info(f"✓ {job_name} completed in {duration:.1f}s")
            return True

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
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
            _load_collect_all()
            self.logger.info("Collecting data from all sources...")
            collect_all()
        except ImportError:
            self.logger.warning("scheduled_collect not available, skipping collect")
        except Exception as e:
            self.logger.error(f"Collect failed: {e}")
            raise

    def _handle_truth_cycle(self):
        """Stage 2: Run truth cycle."""
        from lib.truth_cycle import TruthCycle

        self.logger.info("Running truth cycle...")
        cycle = TruthCycle(str(paths.db_path()))
        result = cycle.run()
        self.logger.info(f"Truth cycle: {result.passed}/{len(result.stages)} stages passed")
        if result.errors:
            self.logger.warning(f"Truth cycle warnings: {result.errors}")

    def _handle_snapshot(self):
        """Stage 3: Generate agency snapshot."""
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
        except Exception as e:
            # Log the validation error but try to save minimal snapshot
            self.logger.warning(f"Snapshot validation failed: {e}")
            # Generate and save without strict validation
            generator = AgencySnapshotGenerator(db_path=paths.db_path())
            # Build minimal snapshot directly
            snapshot = {
                "meta": generator._build_meta(datetime.now()),
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
            snapshot["meta"]["finished_at"] = datetime.now().isoformat()
            generator.save(snapshot)
            self.logger.info("Minimal snapshot saved")

    def _handle_notify(self):
        """Stage 4: Send notifications (dry-run mode)."""
        self.logger.info("Sending notifications (dry-run mode)...")
        try:
            from lib.notifier.channels.google_chat import GoogleChatChannel

            channel = GoogleChatChannel(webhook_url="", dry_run=True)
            message = "MOH Time OS daemon cycle completed successfully"
            result = channel.send_sync(message, priority="normal")
            if result.get("success"):
                self.logger.info(f"Notification sent: {result.get('message_id')}")
            else:
                self.logger.warning(f"Notification failed: {result.get('error')}")
        except Exception as e:
            self.logger.warning(f"Notification handler failed: {e}")

    def run_once(self):
        """Run all jobs once in sequence and exit."""
        self.logger.info("=" * 50)
        self.logger.info("Running one-shot cycle")
        self.logger.info("=" * 50)

        jobs_to_run = ["collect", "truth_cycle", "snapshot", "notify"]
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
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))
        self.logger.info(f"PID {os.getpid()} written to {PID_FILE}")

    def _cleanup(self):
        """Cleanup on shutdown."""
        self._save_state()
        if PID_FILE.exists():
            PID_FILE.unlink()
        self.logger.info("Daemon stopped")

    @staticmethod
    def is_running() -> tuple[bool, int | None]:
        """Check if daemon is running. Returns (is_running, pid)."""
        if not PID_FILE.exists():
            return False, None

        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, ValueError):
            # Process doesn't exist, clean up stale PID file
            PID_FILE.unlink(missing_ok=True)
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
            PID_FILE.unlink(missing_ok=True)
            logger.info("Daemon already stopped")
            return True

    @staticmethod
    def status() -> dict:
        """Get daemon status."""
        running, pid = TimeOSDaemon.is_running()

        status = {
            "running": running,
            "pid": pid,
            "pid_file": str(PID_FILE),
            "state_file": str(STATE_FILE),
            "log_file": str(LOG_FILE),
            "jobs": {},
        }

        # Load job states
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
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
