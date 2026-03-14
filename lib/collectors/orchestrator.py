"""
Collector Orchestrator - Manages all collectors and coordinates syncing.
This is the WIRING that connects external data to the state store.

All collection goes through class-based collectors in lib/collectors/.
No legacy scripts, no gog CLI, no importlib hacks.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yaml

from lib import paths
from lib.collector_registry import CollectorLock
from lib.collectors.resilience import COLLECTOR_ERRORS
from lib.collectors.result import CollectorResult, CollectorStatus, classify_error
from lib.state_tracker import mark_collected

from ..state_store import StateStore, get_store
from .asana import AsanaCollector
from .calendar import CalendarCollector
from .chat import ChatCollector
from .contacts import ContactsCollector
from .drive import DriveCollector
from .gmail import GmailCollector
from .tasks import TasksCollector
from .xero import XeroCollector

logger = logging.getLogger(__name__)

# Per-collector timeout in seconds
COLLECTOR_TIMEOUT_SECONDS = 300


class CollectorOrchestrator:
    """
    Orchestrates all data collectors.

    This is WIRING POINT #1:
    External Systems → Collectors → State Store
    """

    def __init__(self, config_path: str | None = None, store: StateStore | None = None):
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
            "tasks": TasksCollector,
            "calendar": CalendarCollector,
            "chat": ChatCollector,
            "gmail": GmailCollector,
            "asana": AsanaCollector,
            "xero": XeroCollector,
            "drive": DriveCollector,
            "contacts": ContactsCollector,
        }

        sources = self.config.get("sources", {})

        # Always enable core collectors
        core_sources = {
            "tasks": {"enabled": True, "sync_interval": 300},
            "calendar": {"enabled": True, "sync_interval": 60},
            "chat": {"enabled": True, "sync_interval": 300},
            "gmail": {"enabled": True, "sync_interval": 120},
            "asana": {"enabled": True, "sync_interval": 300},
            "xero": {"enabled": True, "sync_interval": 300},
            "drive": {"enabled": True, "sync_interval": 600},
            "contacts": {"enabled": True, "sync_interval": 600},
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
                except COLLECTOR_ERRORS as e:
                    self.logger.error(f"Failed to initialize {source_name}: {e}")

    def _sync_one(self, name: str, *, force: bool = False) -> dict[str, Any]:
        """Sync a single collector under a per-collector lock."""
        lock_obj = CollectorLock(name)
        if force:
            lock_obj.break_lock()
        with lock_obj as lock:
            if not lock.acquired:
                self.logger.warning("Collector %s is already running, skipping", name)
                cr = CollectorResult(
                    source=name,
                    status=CollectorStatus.SKIPPED,
                    error=f"{name} collector is already running",
                    error_type="lock_contention",
                )
                return cr.to_dict()

            collector = self.collectors.get(name)
            if not collector:
                cr = CollectorResult(
                    source=name,
                    status=CollectorStatus.FAILED,
                    error=f"Unknown collector: {name}",
                    error_type="configuration",
                )
                return cr.to_dict()

            try:
                result: dict[str, Any] = collector.sync()
                # Mark collected for SUCCESS or PARTIAL — both wrote primary data
                if result.get("status") in ("success", "partial"):
                    mark_collected(name)
                return result
            except COLLECTOR_ERRORS as e:
                self.logger.error("Sync failed for %s: %s", name, e)
                cr = CollectorResult(
                    source=name,
                    status=CollectorStatus.FAILED,
                    error=str(e),
                    error_type=classify_error(e),
                )
                return cr.to_dict()

    def sync_all(self, *, force: bool = False) -> dict[str, Any]:
        """Sync all collectors in parallel with per-collector locks."""
        return self.force_sync(source=None, force=force)

    def sync(self, source: str | None = None, *, force: bool = False) -> dict[str, Any]:
        """Sync one or all collectors. Alias for force_sync."""
        return self.force_sync(source=source, force=force)

    def force_sync(self, source: str | None = None, *, force: bool = False) -> dict[str, Any]:
        """
        Force sync — runs class-based collectors directly.

        All collectors use service account auth (no gog CLI).
        Each collector acquires its own lock in _sync_one, so a slow
        collector (e.g. Asana) never blocks faster ones.

        Args:
            source: Collector name, or None for all.
            force: Break existing locks before acquiring.
        """
        return self._sync_impl(source, force=force)

    def _sync_impl(self, source: str | None = None, *, force: bool = False) -> dict[str, Any]:
        """Internal sync implementation. Each collector locks independently."""
        if source:
            # Single source sync
            result = self._sync_one(source, force=force)
            return {source: result}

        # All sources in parallel
        sources_to_sync = list(self.collectors.keys())
        results = {}

        if force:
            self.logger.info("Force mode: breaking all collector locks")

        self.logger.info(f"Starting parallel sync of {len(sources_to_sync)} collectors")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._sync_one, name, force=force): name for name in sources_to_sync
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=COLLECTOR_TIMEOUT_SECONDS)
                except TimeoutError:
                    self.logger.error(
                        "Collector %s timed out after %ds", name, COLLECTOR_TIMEOUT_SECONDS
                    )
                    cr = CollectorResult(
                        source=name,
                        status=CollectorStatus.FAILED,
                        error=f"timeout after {COLLECTOR_TIMEOUT_SECONDS}s",
                        error_type="timeout",
                    )
                    results[name] = cr.to_dict()
                except COLLECTOR_ERRORS as e:
                    self.logger.warning("Collector %s failed: %s", name, e)
                    cr = CollectorResult(
                        source=name,
                        status=CollectorStatus.FAILED,
                        error=str(e),
                        error_type=classify_error(e),
                    )
                    results[name] = cr.to_dict()

        # Post-collection: entity linking
        self._run_entity_linking(results)

        # Post-collection: inbox enrichment
        self._run_inbox_enrichment(results)

        return results

    def _run_entity_linking(self, results: dict) -> None:
        """Run entity linking after collection."""
        try:
            from lib.entity_linker import run_linking

            self.logger.info("Running entity linking")
            linking_results = run_linking(dry_run=False)
            results["entity_linking"] = linking_results.get("stats", {})
        except COLLECTOR_ERRORS as e:
            self.logger.warning("Entity linking failed: %s", e)
            results["entity_linking"] = {"error": str(e)}

    def _run_inbox_enrichment(self, results: dict) -> None:
        """Run inbox enrichment after collection."""
        try:
            from lib.ui_spec_v21.inbox_enricher import run_enrichment_batch

            self.logger.info("Running inbox enrichment")
            enrichment_stats = run_enrichment_batch(use_llm=True, limit=20)
            results["inbox_enrichment"] = enrichment_stats
        except COLLECTOR_ERRORS as e:
            self.logger.warning("Inbox enrichment failed: %s", e)
            results["inbox_enrichment"] = {"error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Get status of all collectors with degraded-state signaling.

        Each collector entry includes:
          - status: "healthy", "degraded", or "failed"
          - circuit_breaker_state: current state of the circuit breaker
          - stale: True if data freshness has lapsed

        Freshness rule: data is stale when last_success is older than
        3x sync_interval. This gives two missed cycles of grace before
        marking stale, avoiding false alarms from single slow cycles.
        """
        sync_states = self.store.get_sync_states()

        status = {}
        for name, collector in self.collectors.items():
            state = sync_states.get(name, {})
            has_error = state.get("error") is not None
            last_success = state.get("last_success")

            # Freshness check: stale if no successful sync within 3x interval.
            # 3x gives two missed cycles of grace before declaring stale.
            is_stale = False
            stale_threshold = collector.sync_interval * 3
            if last_success:
                try:
                    from datetime import datetime, timezone

                    last_success_dt = datetime.fromisoformat(last_success)
                    if last_success_dt.tzinfo is None:
                        last_success_dt = last_success_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - last_success_dt).total_seconds()
                    is_stale = elapsed > stale_threshold
                except (ValueError, TypeError):
                    is_stale = True
            else:
                # Never succeeded — no data at all, not stale (it's failed)
                is_stale = False

            # Derive collector health status from observed signals:
            # - failed: has error and has never succeeded (no data to serve)
            # - degraded: has error, or data is stale, or circuit breaker not closed
            # - healthy: no error, data is fresh, circuit breaker closed
            cb_state = collector.circuit_breaker.state
            if has_error and not last_success:
                health = "failed"
            elif has_error or is_stale or cb_state != "closed":
                health = "degraded"
            else:
                health = "healthy"

            status[name] = {
                "enabled": True,
                "status": health,
                "last_sync": state.get("last_sync"),
                "last_success": last_success,
                "items_synced": state.get("items_synced", 0),
                "error": state.get("error"),
                "healthy": health == "healthy",
                "stale": is_stale,
                "circuit_breaker_state": cb_state,
                "sync_interval": collector.sync_interval,
            }

        return status

    def health_check(self) -> dict[str, bool]:
        """Check health of all collectors."""
        results = {}
        for name, collector in self.collectors.items():
            try:
                results[name] = collector.health_check()
            except COLLECTOR_ERRORS as e:
                self.logger.warning(f"Health check failed for {name}: {e}")
                results[name] = False
        return results


def main():
    """CLI entry point. All errors print to stderr — never fails silently."""
    import argparse
    import json
    import sys
    import traceback

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        parser = argparse.ArgumentParser(description="Collector Orchestrator")
        parser.add_argument("command", choices=["sync", "status"])
        parser.add_argument(
            "--force", action="store_true", help="Break existing locks before syncing"
        )
        parser.add_argument("--source", help="Sync a single collector by name")
        args = parser.parse_args()

        orchestrator = CollectorOrchestrator()

        if args.command == "sync":
            results = orchestrator.sync(source=args.source, force=args.force)
            print(json.dumps(results, indent=2, default=str))
        elif args.command == "status":
            status = orchestrator.get_status()
            print(json.dumps(status, indent=2, default=str))
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
