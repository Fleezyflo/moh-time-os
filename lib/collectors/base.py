"""
Base Collector - Template for all data collectors.
Every collector MUST:
1. Collect raw data from external source
2. Transform to canonical format
3. Store in StateStore
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..state_store import StateStore, get_store


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(self, config: dict, store: StateStore = None):
        self.config = config
        self.store = store or get_store()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_sync: datetime | None = None
        self.sync_interval: int = config.get("sync_interval", 300)

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
        """
        pass

    @abstractmethod
    def transform(self, raw_data: dict) -> list[dict]:
        """
        Transform raw API data to canonical format.
        Returns list of items ready for storage.
        """
        pass

    def sync(self) -> dict[str, Any]:
        """
        Full sync cycle: collect → transform → store.
        This is the WIRING - data flows through here.
        """
        cycle_start = datetime.now()

        try:
            # Step 1: Collect from external source
            self.logger.info(f"Collecting from {self.source_name}")
            raw_data = self.collect()

            # Step 2: Transform to canonical format
            transformed = self.transform(raw_data)
            self.logger.info(f"Transformed {len(transformed)} items")

            # Step 3: Store in state (THE WIRING)
            stored = self.store.insert_many(self.target_table, transformed)

            # Step 4: Update sync state
            self.last_sync = datetime.now()
            self.store.update_sync_state(self.source_name, success=True, items=stored)

            duration_ms = (datetime.now() - cycle_start).total_seconds() * 1000

            return {
                "source": self.source_name,
                "success": True,
                "collected": len(
                    raw_data.get(
                        "items",
                        raw_data.get(
                            "tasks",
                            raw_data.get(
                                "events",
                                raw_data.get("messages", raw_data.get("threads", [])),
                            ),
                        ),
                    )
                ),
                "transformed": len(transformed),
                "stored": stored,
                "duration_ms": duration_ms,
                "timestamp": self.last_sync.isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.store.update_sync_state(self.source_name, success=False, error=str(e))
            return {
                "source": self.source_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

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
        except Exception as e:
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
            # Include GOG_ACCOUNT for gog CLI commands (from env or default)
            env = os.environ.copy()
            if "GOG_ACCOUNT" not in env:
                env["GOG_ACCOUNT"] = os.environ.get("DEFAULT_GOG_ACCOUNT", "")

            # Validate command exists (first element)
            if not cmd or not shutil.which(cmd[0]):
                raise Exception(f"Command not found: {cmd[0] if cmd else 'empty'}")

            result = subprocess.run(  # noqa: S603 - shell=False is secure
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
            raise Exception(f"Command timed out after {timeout}s")

    def _parse_json_output(self, output: str) -> Any:
        """Parse JSON from command output."""
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}\nOutput: {output[:500]}")
            raise
