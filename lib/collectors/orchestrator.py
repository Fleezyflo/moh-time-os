"""
Collector Orchestrator - Manages all collectors and coordinates syncing.
This is the WIRING that connects external data to the state store.
"""

import logging
from typing import Any

import yaml

from lib import paths

from ..state_store import StateStore, get_store
from .asana import AsanaCollector
from .calendar import CalendarCollector
from .gmail import GmailCollector
from .tasks import TasksCollector
from .xero import XeroCollector

logger = logging.getLogger(__name__)


class CollectorOrchestrator:
    """
    Orchestrates all data collectors.

    This is WIRING POINT #1:
    External Systems → Collectors → State Store
    """

    def __init__(self, config_path: str = None, store: StateStore = None):
        self.config_path = config_path or str(paths.config_dir())
        self.store = store or get_store()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = self._load_config()
        self.collectors: dict[str, Any] = {}

        self._init_collectors()

    def _load_config(self) -> dict:
        """Load source configuration from centralized config directory."""
        config_file = paths.config_dir() / "sources.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {"sources": {}}

    def _init_collectors(self):
        """Initialize enabled collectors."""
        # Map config names to collector classes
        collector_map = {
            "tasks": TasksCollector,  # Google Tasks
            "calendar": CalendarCollector,
            "gmail": GmailCollector,
            "asana": AsanaCollector,
            "xero": XeroCollector,
        }

        sources = self.config.get("sources", {})

        # Always enable core collectors
        core_sources = {
            "tasks": {"enabled": True, "sync_interval": 300},
            "calendar": {"enabled": True, "sync_interval": 60},
            "gmail": {"enabled": True, "sync_interval": 120},
            "asana": {"enabled": True, "sync_interval": 300},
            "xero": {"enabled": True, "sync_interval": 300},  # AR/Invoice sync
        }

        # Merge config with core
        for name, default_cfg in core_sources.items():
            if name not in sources:
                sources[name] = default_cfg
            elif not sources[name].get("enabled"):
                sources[name]["enabled"] = True

        for source_name, source_config in sources.items():
            if not source_config.get("enabled", False):
                continue

            collector_class = collector_map.get(source_name)
            if collector_class:
                try:
                    self.collectors[source_name] = collector_class(source_config, self.store)
                    self.logger.info(f"Initialized collector: {source_name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {source_name}: {e}")

    def sync_all(self) -> dict[str, Any]:
        """
        Sync all collectors — delegates to canonical runner.
        """
        return self.force_sync(source=None)

    def sync(self, source: str = None) -> dict[str, Any]:
        """
        Sync one or all collectors — delegates to canonical runner.
        Alias for force_sync (API compatibility).
        """
        return self.force_sync(source=source)

    def force_sync(self, source: str = None) -> dict[str, Any]:
        """
        Force sync — delegates to canonical runner (scheduled_collect.py).

        This ensures all sync requests go through ONE path that:
        1. Writes JSON for V5 detectors
        2. Writes to DB tables (invoices, etc.)
        3. Runs V4/V5 pipeline
        """
        from collectors.scheduled_collect import collect_all

        self.logger.info(f"Force sync delegating to canonical runner (source={source})")

        sources = [source] if source else None
        try:
            # v4_ingest=False for API-triggered syncs (run pipeline separately)
            result = collect_all(sources=sources, v4_ingest=False)
            if isinstance(result, dict) and result.get("error") == "locked":
                return {
                    source or "all": {
                        "success": False,
                        "error": "Another collector is running",
                    }
                }
            return {source or "all": {"success": True, "result": result}}
        except Exception as e:
            self.logger.error(f"Force sync failed: {e}")
            return {source or "all": {"success": False, "error": str(e)}}

    def get_status(self) -> dict[str, Any]:
        """Get status of all collectors."""
        sync_states = self.store.get_sync_states()

        status = {}
        for name, collector in self.collectors.items():
            state = sync_states.get(name, {})
            status[name] = {
                "enabled": True,
                "last_sync": state.get("last_sync"),
                "last_success": state.get("last_success"),
                "items_synced": state.get("items_synced", 0),
                "error": state.get("error"),
                "healthy": state.get("error") is None,
                "sync_interval": collector.sync_interval,
            }

        return status

    def health_check(self) -> dict[str, bool]:
        """Check health of all collectors."""
        results = {}
        for name, collector in self.collectors.items():
            try:
                results[name] = collector.health_check()
            except Exception as e:
                self.logger.warning(f"Health check failed for {name}: {e}")
                results[name] = False
        return results


def main():
    """CLI entry point."""
    import json
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: python -m lib.collectors.orchestrator <sync|status>")
        sys.exit(1)

    command = sys.argv[1]
    orchestrator = CollectorOrchestrator()

    if command == "sync":
        results = orchestrator.sync_all()
        logger.info(json.dumps(results, indent=2, default=str))
    elif command == "status":
        status = orchestrator.get_status()
        logger.info(json.dumps(status, indent=2, default=str))
    else:
        logger.info(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
