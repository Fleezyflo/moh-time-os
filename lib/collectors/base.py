"""
Base Collector - Template for all data collectors.
Every collector MUST:
1. Collect raw data from external source
2. Transform to canonical format
3. Store in StateStore
4. Return a typed CollectorResult (never a plain dict)
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..state_store import StateStore, get_store
from .resilience import COLLECTOR_ERRORS, CircuitBreaker, RetryConfig, retry_with_backoff
from .result import CollectorResult, CollectorStatus, classify_error


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(self, config: dict, store: StateStore | None = None):
        self.config = config
        self.store = store or get_store()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_sync: datetime | None = None
        self.sync_interval: int = config.get("sync_interval", 300)

        # Resilience infrastructure
        self.retry_config = RetryConfig(
            max_retries=config.get("max_retries", 3),
            base_delay=config.get("base_delay", 1.0),
            max_delay=config.get("max_delay", 60.0),
            exponential_base=config.get("exponential_base", 2.0),
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("failure_threshold", 5),
            cooldown_seconds=config.get("cooldown_seconds", 300),
        )

        # Metrics tracking
        self.metrics = {
            "retries": 0,
            "circuit_opens": 0,
            "partial_failures": 0,
        }

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        pass

    @property
    @abstractmethod
    def target_table(self) -> str:
        """Which table to store collected data."""
        pass

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """
        Collect raw data from source.
        Returns dict with collected items.

        MUST raise on failure — never return empty data to fake success.
        """
        pass

    @abstractmethod
    def transform(self, raw_data: dict) -> list[dict]:
        """
        Transform raw API data to canonical format.
        Returns list of items ready for storage.
        """
        pass

    def _count_collected(self, raw_data: dict) -> int:
        """Count collected items from raw data dict.

        Looks for common keys: items, tasks, events, messages, threads, files, contacts.
        """
        for key in ("items", "tasks", "events", "messages", "threads", "files", "contacts"):
            val = raw_data.get(key)
            if isinstance(val, list):
                return len(val)
        return 0

    def sync(self) -> dict[str, Any]:
        """
        Full sync cycle: collect -> transform -> store.
        This is the WIRING - data flows through here.

        Uses circuit breaker to prevent cascading failures and retry logic
        with exponential backoff on transient errors.

        Returns a CollectorResult.to_dict() — typed, never ambiguous.
        """
        cycle_start = datetime.now()

        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker is {self.circuit_breaker.state}. Skipping sync.")
            self.metrics["circuit_opens"] += 1
            result = CollectorResult(
                source=self.source_name,
                status=CollectorStatus.STALE,
                error=f"Circuit breaker {self.circuit_breaker.state}",
                error_type="circuit_breaker",
                circuit_breaker_state=self.circuit_breaker.state,
            )
            return result.to_dict()

        try:
            # Step 1: Collect from external source with retry
            self.logger.info(f"Collecting from {self.source_name}")

            def collect_with_retry():
                return self.collect()

            try:
                raw_data = retry_with_backoff(collect_with_retry, self.retry_config, self.logger)
            except COLLECTOR_ERRORS as e:
                self.logger.error(f"Collect failed after retries: {e}")
                self.circuit_breaker.record_failure()
                err_type = classify_error(e)
                self.store.update_sync_state(
                    self.source_name,
                    success=False,
                    error=str(e),
                    error_type=err_type,
                    status="failed",
                )
                result = CollectorResult(
                    source=self.source_name,
                    status=CollectorStatus.FAILED,
                    error=str(e),
                    error_type=err_type,
                    circuit_breaker_state=self.circuit_breaker.state,
                    duration_ms=(datetime.now() - cycle_start).total_seconds() * 1000,
                )
                return result.to_dict()

            # Step 2: Transform to canonical format
            transform_failed = False
            try:
                transformed = self.transform(raw_data)
            except COLLECTOR_ERRORS as e:
                self.logger.warning(f"Transform failed: {e}. Storing 0 items.")
                transformed = []
                transform_failed = True
                self.metrics["partial_failures"] += 1

            self.logger.info(f"Transformed {len(transformed)} items")

            # Step 3: Store in state (THE WIRING)
            stored = self.store.insert_many(self.target_table, transformed)

            # Step 4: Determine status, update sync state, record success
            self.last_sync = datetime.now()
            # Transform failure means we collected but couldn't process —
            # that's PARTIAL (primary data lost), not SUCCESS.
            status = CollectorStatus.PARTIAL if transform_failed else CollectorStatus.SUCCESS
            self.store.update_sync_state(
                self.source_name,
                success=(status == CollectorStatus.SUCCESS),
                items=stored,
                error_type="data_error" if transform_failed else None,
                status=status.value,
            )
            self.circuit_breaker.record_success()

            duration_ms = (datetime.now() - cycle_start).total_seconds() * 1000

            result = CollectorResult(
                source=self.source_name,
                status=status,
                collected=self._count_collected(raw_data),
                transformed=len(transformed),
                stored=stored,
                duration_ms=duration_ms,
                timestamp=self.last_sync.isoformat(),
                circuit_breaker_state=self.circuit_breaker.state,
                error="Transform failed" if transform_failed else None,
                error_type="data_error" if transform_failed else None,
            )
            return result.to_dict()

        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.circuit_breaker.record_failure()
            err_type = classify_error(e)
            self.store.update_sync_state(
                self.source_name,
                success=False,
                error=str(e),
                error_type=err_type,
                status="failed",
            )
            result = CollectorResult(
                source=self.source_name,
                status=CollectorStatus.FAILED,
                error=str(e),
                error_type=classify_error(e),
                circuit_breaker_state=self.circuit_breaker.state,
                duration_ms=(datetime.now() - cycle_start).total_seconds() * 1000,
            )
            return result.to_dict()

    def should_sync(self) -> bool:
        """Check if this collector needs to sync."""
        if not self.last_sync:
            return True
        elapsed = (datetime.now() - self.last_sync).total_seconds()
        return elapsed >= self.sync_interval

    def health_check(self) -> bool:
        """Check if collector can reach its source."""
        try:
            # Default: try a minimal collect
            self.collect()
            return True
        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def _run_command(self, cmd: list[str], timeout: int = 30) -> str:
        """
        Run a command and return output.

        Args:
            cmd: Command as list of arguments (NOT a shell string).
                 Example: ["gog", "tasks", "lists", "--json"]
            timeout: Timeout in seconds

        Returns:
            Command stdout

        Security: No shell=True. Commands are executed directly without
        shell interpretation, preventing command injection.
        """
        import os
        import shutil

        try:
            # Include GOG_ACCOUNT for gog CLI commands
            env = os.environ.copy()
            env["GOG_ACCOUNT"] = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")

            # Validate command exists (first element)
            if not cmd or not shutil.which(cmd[0]):
                raise Exception(f"Command not found: {cmd[0] if cmd else 'empty'}")

            result = subprocess.run(
                cmd,
                shell=False,  # SECURE: no shell interpretation
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            if result.returncode != 0:
                raise Exception(f"Command failed: {result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise Exception(f"Command timed out after {timeout}s") from None

    def _parse_json_output(self, output: str) -> Any:
        """Parse JSON from command output."""
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}\nOutput: {output[:500]}")
            raise
