"""
Collector Orchestrator - Manages all collectors and coordinates syncing.
This is the WIRING that connects external data to the state store.

All collection goes through class-based collectors in lib/collectors/.
No legacy scripts, no gog CLI, no importlib hacks.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yaml

from lib import paths
from lib.collector_registry import COLLECTOR_REGISTRY, CollectorLock, get_collector_map
from lib.collectors.resilience import COLLECTOR_ERRORS
from lib.collectors.result import CollectorResult, CollectorStatus, classify_error
from lib.state_tracker import mark_collected

from ..state_store import StateStore, get_store

# The canonical collector registry (lib/collector_registry.get_collector_map) is
# the single source of truth used at runtime by _init_collectors. These names are
# also re-exported here so callers/tests can patch e.g.
# `lib.collectors.orchestrator.AsanaCollector` and so the orchestrator module
# still names every collector class it orchestrates.
from .asana import AsanaCollector
from .calendar import CalendarCollector
from .chat import ChatCollector
from .contacts import ContactsCollector
from .drive import DriveCollector
from .gmail import GmailCollector
from .tasks import TasksCollector
from .xero import XeroCollector

__all__ = [
    "AsanaCollector",
    "CalendarCollector",
    "ChatCollector",
    "CollectorOrchestrator",
    "ContactsCollector",
    "DriveCollector",
    "GmailCollector",
    "TasksCollector",
    "XeroCollector",
]

logger = logging.getLogger(__name__)

# Per-collector timeout in seconds
COLLECTOR_TIMEOUT_SECONDS = 300

# Default inbox-enrichment batch size per collect cycle. Read at call time from
# MOH_INBOX_ENRICH_LIMIT so backlogs don't drain at a fixed 20/cycle (and so the
# env override is honored without a module reload).
DEFAULT_INBOX_ENRICH_LIMIT = 20


def _core_sources_from_registry() -> dict[str, dict]:
    """Derive {source: {enabled, sync_interval}} from the canonical registry.

    The registry (lib/collector_registry.py) is the single source of truth for
    which collectors exist and their default sync intervals. The orchestrator
    must not maintain a second copy.
    """
    return {
        name: {"enabled": spec.enabled, "sync_interval": spec.sync_interval_seconds}
        for name, spec in COLLECTOR_REGISTRY.items()
    }


def _resolve_collector_map() -> dict[str, type]:
    """Map each source name to its collector class, resolved at call time.

    The canonical key set comes from get_collector_map() (the registry). The
    class OBJECT, however, is taken from this module's globals when the same
    class is re-exported here (see the import block above), so that tests
    patching e.g. `lib.collectors.orchestrator.GmailCollector` are honored by
    both _init_collectors and reinit_failed_collectors. Names not re-exported
    here fall back to the registry's class.
    """
    registry_map = get_collector_map()
    module_globals = globals()
    resolved: dict[str, type] = {}
    for source_name, registry_class in registry_map.items():
        resolved[source_name] = module_globals.get(registry_class.__name__, registry_class)
    return resolved


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
        # name -> error message for collectors that raised during initialization.
        # Surfaced via get_status() and retried by reinit_failed_collectors().
        self.init_failures: dict[str, str] = {}

        self._init_collectors()

    def _load_config(self) -> dict:
        """Load source configuration from centralized config directory."""
        config_file = paths.config_dir() / "sources.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {"sources": {}}

    def _init_collectors(self):
        """Initialize enabled collectors from the canonical registry."""
        # _init_collectors owns init_failures: ensure it exists even when called
        # directly on an orchestrator built via __new__ (some tests bypass
        # __init__), so recording/clearing failures below never AttributeErrors.
        if not hasattr(self, "init_failures"):
            self.init_failures = {}
        collector_map = _resolve_collector_map()
        sources = self.config.get("sources", {})
        core_sources = _core_sources_from_registry()

        # Merge config over registry defaults. A source absent from sources.yaml
        # falls back to the registry default. An explicit enabled:false in
        # sources.yaml is HONORED (operators can disable a core collector).
        for name, default_cfg in core_sources.items():
            if name not in sources:
                sources[name] = dict(default_cfg)
            else:
                sources[name].setdefault("sync_interval", default_cfg["sync_interval"])

        for source_name, source_config in sources.items():
            if not source_config.get("enabled", False):
                continue

            collector_class = collector_map.get(source_name)
            if collector_class:
                try:
                    self.collectors[source_name] = collector_class(source_config, self.store)
                    self.init_failures.pop(source_name, None)
                    self.logger.info(f"Initialized collector: {source_name}")
                except COLLECTOR_ERRORS as e:
                    # Record the failure so get_status() can surface a degraded
                    # collector and reinit_failed_collectors() can retry it,
                    # instead of the collector silently vanishing from status.
                    self.init_failures[source_name] = str(e)
                    self.logger.error(f"Failed to initialize {source_name}: {e}")

    def reinit_failed_collectors(self) -> dict[str, str]:
        """Retry collectors that failed to initialize earlier.

        Iterates the recorded init_failures and attempts to construct each
        collector again (e.g. after expired creds were refreshed or a quota
        reset). A collector that now succeeds moves into self.collectors and is
        dropped from init_failures. One that still raises stays in init_failures
        with its new error message.

        Returns the collectors still failing after this attempt
        ({name: error_message}); an empty dict means everything recovered.
        No-op (returns {}) when there are no recorded failures.
        """
        if not self.init_failures:
            return {}

        collector_map = _resolve_collector_map()
        sources = self.config.get("sources", {})
        core_sources = _core_sources_from_registry()

        # Snapshot names up front: we mutate self.init_failures inside the loop.
        for name in list(self.init_failures.keys()):
            collector_class = collector_map.get(name)
            if collector_class is None:
                # No class for this name (unknown collector) — cannot retry it.
                self.logger.warning("Cannot reinit unknown collector: %s", name)
                continue

            # Recover the source config the same way _init_collectors does:
            # explicit sources.yaml entry wins, else the registry default.
            source_config = sources.get(name) or core_sources.get(name) or {}

            try:
                self.collectors[name] = collector_class(source_config, self.store)
                del self.init_failures[name]
                self.logger.info("Recovered collector on reinit: %s", name)
            except COLLECTOR_ERRORS as e:
                self.init_failures[name] = str(e)
                self.logger.warning("Collector %s still failing on reinit: %s", name, e)

        return dict(self.init_failures)

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
                    self._record_freshness(name, result.get("stored", 0) or 0)
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

    def _record_freshness(self, source: str, stored: int) -> None:
        """Record a successful collector run in the data_freshness table.

        Single choke point: every collector (including the standalone
        XeroCollector and the sync()-overriding Asana/Gmail collectors)
        funnels through _sync_one, so this is the one place that keeps the
        DataFreshnessTracker in lockstep with actual collection. Failure to
        record must never break a sync — log and move on.
        """
        try:
            from lib.intelligence.data_freshness import DataFreshnessTracker

            tracker = DataFreshnessTracker(db_path=paths.db_path())
            tracker.record_collection_for_source(source, record_count=stored)
        except COLLECTOR_ERRORS as e:
            self.logger.debug("Freshness record failed for %s: %s", source, e)

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

        # Before a full sync, retry any collectors that failed to initialize.
        # Transient init failures (expired creds, a quota that has since reset)
        # otherwise keep a collector out of every sync until the process
        # restarts. Recovered collectors join self.collectors and are synced
        # below in the same cycle. getattr guard: _sync_impl may run on an
        # orchestrator built via __new__ in tests that never ran __init__.
        if getattr(self, "init_failures", None):
            self.reinit_failed_collectors()

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

            # NOTE: future.result(timeout=...) frees this waiting caller but
            # does NOT kill a wedged worker thread. SIGALRM (watchdog.py) can't
            # interrupt a pool worker either (it only fires on the main thread).
            # The safety net is CollectorLock's 60s TTL self-heal: a hung worker
            # stops its heartbeat and the lock is reclaimed next cycle.
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

        # Surface collectors that failed to initialize (and did not recover via
        # the reinit above) under a reserved _init_failures key, so a full-sync
        # caller sees them as explicit failures rather than silently missing
        # collectors. Omitted entirely when there are no init failures.
        remaining_init_failures = getattr(self, "init_failures", None)
        if remaining_init_failures:
            results["_init_failures"] = {
                name: {"success": False, "error": error}
                for name, error in remaining_init_failures.items()
            }

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
            limit = int(os.environ.get("MOH_INBOX_ENRICH_LIMIT", str(DEFAULT_INBOX_ENRICH_LIMIT)))
            enrichment_stats = run_enrichment_batch(use_llm=True, limit=limit)
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
            # A collector without a circuit_breaker attribute (only the case for
            # lightweight test doubles; every real collector sets one in
            # base.py) is treated as "closed" so it can still report healthy.
            circuit_breaker = getattr(collector, "circuit_breaker", None)
            cb_state = circuit_breaker.state if circuit_breaker is not None else "closed"
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
                "sync_interval": getattr(collector, "sync_interval", None),
                "init_failed": False,
                "init_error": None,
            }

        # Surface collectors that never initialized. These are absent from
        # self.collectors (construction raised), so without this block a failed
        # collector would silently disappear from status instead of reporting
        # unhealthy. A name present in both collectors and init_failures (should
        # not happen, but be safe) keeps its healthy entry — init_failures only
        # fills in names not already reported above.
        # getattr guard: get_status may run on an orchestrator built via
        # __new__ in tests that never ran __init__ (so init_failures is unset).
        for name, error in getattr(self, "init_failures", {}).items():
            if name in status:
                continue
            status[name] = {
                "enabled": True,
                "status": "failed",
                "last_sync": None,
                "last_success": None,
                "items_synced": 0,
                "error": error,
                "healthy": False,
                "stale": False,
                "circuit_breaker_state": None,
                "sync_interval": None,
                "init_failed": True,
                "init_error": error,
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
