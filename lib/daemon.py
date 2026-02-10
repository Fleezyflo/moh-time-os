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
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from lib import paths

logger = logging.getLogger(__name__)

# Paths - centralized via lib/paths.py
PID_FILE = paths.data_dir() / "daemon.pid"
STATE_FILE = paths.data_dir() / "daemon_state.json"
LOG_FILE = paths.data_dir() / "daemon.log"
VENV_PYTHON = paths.project_root() / ".venv" / "bin" / "python3"


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

        # Load persisted state
        self._load_state()

    def _register_default_jobs(self):
        """Register the standard Time OS jobs."""

        # Collection: Pull from all sources
        self.register_job(
            JobConfig(
                name="collect",
                interval_minutes=30,
                command=[
                    str(VENV_PYTHON),
                    str(PROJECT_ROOT / "collectors" / "scheduled_collect.py"),
                ],
            )
        )

        # Autonomous cycle: Normalize → Gates → Queue → Snapshot
        self.register_job(
            JobConfig(
                name="autonomous",
                interval_minutes=15,
                command=[str(VENV_PYTHON), "-m", "lib.autonomous_loop", "run"],
            )
        )

        # Backup: Daily (we'll check time-of-day in should_run)
        self.register_job(
            JobConfig(
                name="backup",
                interval_minutes=1440,  # 24 hours
                command=[str(VENV_PYTHON), "cli_v2.py", "backup"],
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
                            state.last_run = datetime.fromisoformat(
                                state_data["last_run"]
                            )
                        if state_data.get("last_success"):
                            state.last_success = datetime.fromisoformat(
                                state_data["last_success"]
                            )
                        state.last_error = state_data.get("last_error")
                        state.consecutive_failures = state_data.get(
                            "consecutive_failures", 0
                        )
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
                    "last_success": state.last_success.isoformat()
                    if state.last_success
                    else None,
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
        config = self.jobs[job_name]
        state = self.job_states[job_name]

        self.logger.info(f"▶ Running {job_name}...")
        start = datetime.now()
        state.last_run = start
        state.total_runs += 1

        try:
            result = subprocess.run(
                config.command, capture_output=True, text=True, cwd=str(PROJECT_ROOT)
            )

            duration = (datetime.now() - start).total_seconds()

            if result.returncode == 0:
                state.last_success = datetime.now()
                state.last_error = None
                state.consecutive_failures = 0
                self.logger.info(f"✓ {job_name} completed in {duration:.1f}s")
                return True
            state.last_error = (
                result.stderr[:500]
                if result.stderr
                else f"Exit code {result.returncode}"
            )
            state.consecutive_failures += 1
            state.total_failures += 1
            self.logger.error(
                f"✗ {job_name} failed (exit {result.returncode}): {state.last_error[:100]}"
            )
            return False

        except Exception as e:
            state.last_error = str(e)
            state.consecutive_failures += 1
            state.total_failures += 1
            self.logger.exception(f"✗ {job_name} error: {e}")
            return False

    def run_once(self):
        """Run all due jobs once and exit."""
        self.logger.info("Running one-shot cycle...")
        for job_name in self.jobs:
            if self._should_run(job_name):
                self._run_job(job_name)
        self._save_state()
        self.logger.info("One-shot cycle complete")

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
    parser.add_argument(
        "--bg", action="store_true", help="Run in background (start only)"
    )

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
            last_run = (
                job.get("last_run", "never")[:19] if job.get("last_run") else "never"
            )
            failures = job.get("consecutive_failures", 0)
            status_str = "✓" if failures == 0 else f"✗ ({failures} failures)"
            logger.info(f"  {name}: last run {last_run} {status_str}")
    elif args.action == "run-once":
        daemon = TimeOSDaemon()
        daemon.run_once()


if __name__ == "__main__":
    main()
