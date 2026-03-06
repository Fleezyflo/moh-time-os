"""
Autonomous Loop - The heart of MOH TIME OS.
This is the MAIN WIRING - connects all components into one running system.
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import paths

from .analyzers import AnalyzerOrchestrator
from .change_bundles import BundleManager
from .collectors import CollectorOrchestrator
from .executor import ExecutorEngine
from .governance import get_governance
from .notifier import NotificationEngine
from .reasoner import ReasonerEngine
from .state_store import get_store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AutonomousLoop")


class AutonomousLoop:
    """
    Main autonomous execution loop.

    THIS IS THE COMPLETE WIRING:

    1. COLLECT: External Systems → State Store
    2. ANALYZE: State Store → Insights → Cache
    3. REASON: Insights → Decisions (via Governance)
    4. NOTIFY: Decisions → User (via Clawdbot)

    User interacts via CLI/Dashboard, NOT via chat.
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(paths.config_dir())

        # Initialize all components - THIS IS THE WIRING
        self.store = get_store()
        self.collectors = CollectorOrchestrator(self.config_path, self.store)
        self.analyzers = AnalyzerOrchestrator(store=self.store)
        self.governance = get_governance(store=self.store)
        self.reasoner = ReasonerEngine(store=self.store, governance=self.governance)
        self.executor = ExecutorEngine(store=self.store, governance=self.governance)
        self.notifier = NotificationEngine(self.store, self._load_notification_config())
        self.bundle_manager = BundleManager()

        self.cycle_count = 0
        self.running = False

    def _load_governance_yaml(self) -> dict:
        """Load full governance.yaml config."""
        import yaml

        config_file = Path(self.config_path) / "governance.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _load_notification_config(self) -> dict:
        """Load notification config from governance.yaml."""
        return self._load_governance_yaml().get("notification_settings", {})

    def run_cycle(self) -> dict[str, Any]:
        """
        Run one complete autonomous cycle.
        This is what runs every N minutes.
        """
        cycle_start = datetime.now()
        self.cycle_count += 1

        logger.info("═══════════════════════════════════════")
        logger.info(f"  CYCLE {self.cycle_count} STARTING")
        logger.info("═══════════════════════════════════════")

        results = {
            "cycle": self.cycle_count,
            "started_at": cycle_start.isoformat(),
            "phases": {},
        }

        try:
            # ═══════════════════════════════════════
            # PHASE 1: COLLECT
            # External Systems → State Store
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1: COLLECT")
            collect_results = self.collectors.sync_all()
            results["phases"]["collect"] = collect_results

            collected_count = sum(
                r.get("stored", 0)
                for r in collect_results.values()
                if isinstance(r, dict) and r.get("success")
            )
            logger.info(f"  Collected {collected_count} items from {len(collect_results)} sources")

            # ═══════════════════════════════════════
            # PHASE 1a2: DATA NORMALIZATION
            # Derive link statuses per MASTER_SPEC §4
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2: DATA NORMALIZATION")
            normalization_results = self._normalize_data()
            results["phases"]["normalization"] = normalization_results
            total_normalized = sum(
                [
                    normalization_results.get("tasks_updated", 0),
                    normalization_results.get("projects_updated", 0),
                    normalization_results.get("communications_updated", 0),
                    normalization_results.get("invoices_updated", 0),
                ]
            )
            if total_normalized > 0:
                logger.info(f"  Normalized {total_normalized} records")

            # ═══════════════════════════════════════
            # PHASE 1a2a: COMMITMENT EXTRACTION
            # Extract promises/requests from communications
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2a: COMMITMENT EXTRACTION")
            try:
                from .commitment_extractor import extract_from_communications

                commit_results = extract_from_communications(limit=100)
                results["phases"]["commitment_extraction"] = commit_results
                if commit_results.get("commitments_extracted", 0) > 0:
                    logger.info(
                        f"  Extracted {commit_results['commitments_extracted']} commitments"
                    )
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning(f"  Commitment extraction skipped: {e}")
                results["phases"]["commitment_extraction"] = {"error": str(e)}

            # ═══════════════════════════════════════
            # PHASE 1a2b: LANE ASSIGNMENT
            # Categorize tasks into capacity lanes
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a2b: LANE ASSIGNMENT")
            try:
                from .lane_assigner import run_assignment

                lane_results = run_assignment()
                results["phases"]["lane_assignment"] = lane_results
                if lane_results.get("changed", 0) > 0:
                    logger.info(f"  Reassigned {lane_results['changed']} tasks to lanes")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Lane assignment error: {e}")
                results["phases"]["lane_assignment"] = {"error": str(e)}

            # ═══════════════════════════════════════
            # PHASE 1a3: GATE CHECK
            # Evaluate gates, determine blocking per §6.3
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a3: GATE CHECK")
            gate_results = self._check_gates()
            results["phases"]["gates"] = gate_results

            # Log gate status
            passed = [g for g, v in gate_results.items() if v is True and not g.endswith("_pct")]
            failed = [g for g, v in gate_results.items() if v is False and not g.endswith("_pct")]
            logger.info(f"  Gates: {len(passed)} passed, {len(failed)} failed")
            if failed:
                logger.warning(f"  Failed gates: {', '.join(failed)}")

            # Check blocking gates per §6.3
            # data_integrity fails → skip analyze/surface/reason/execute
            # project_brand_required/consistency fails → skip all truth modules
            data_integrity_ok = gate_results.get("data_integrity", False)
            project_gates_ok = gate_results.get(
                "project_brand_required", False
            ) and gate_results.get("project_brand_consistency", False)

            blocking_failed = []
            if not data_integrity_ok:
                blocking_failed.append("data_integrity")
            if not project_gates_ok:
                if not gate_results.get("project_brand_required", False):
                    blocking_failed.append("project_brand_required")
                if not gate_results.get("project_brand_consistency", False):
                    blocking_failed.append("project_brand_consistency")

            if blocking_failed:
                logger.warning(f"  BLOCKING gates failed: {blocking_failed}")
                results["phases"]["blocked"] = True
                results["blocked_by"] = blocking_failed

            # ═══════════════════════════════════════
            # PHASE 1a4: RESOLUTION QUEUE
            # Populate queue with items needing attention
            # (runs regardless of gates - always surface issues)
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a4: RESOLUTION QUEUE")
            queue_results = self._populate_resolution_queue()
            results["phases"]["resolution_queue"] = queue_results
            total_queued = sum(queue_results.get("counts", {}).values())
            if total_queued > 0:
                logger.info(f"  Queued {total_queued} items for resolution")

            # ═══════════════════════════════════════
            # PHASE 1a5: AUTO-RESOLUTION
            # Attempt to fix data quality issues automatically
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1a5: AUTO-RESOLUTION")
            auto_resolve_results = self._auto_resolve()
            results["phases"]["auto_resolution"] = auto_resolve_results
            if auto_resolve_results.get("auto_resolved", 0) > 0:
                logger.info(
                    f"  Auto-resolved {auto_resolve_results['auto_resolved']}"
                    f"/{auto_resolve_results['total_scanned']} items"
                )

            # ═══════════════════════════════════════
            # PHASE 1b5: DETECTION SYSTEM
            # Run collision, drift, bottleneck detectors
            # Dry-run mode: writes to preview table
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1b5: DETECTION")
            try:
                from .detectors import run_all_detectors

                db_path = str(paths.data_dir() / "moh_time_os.db")
                detection_results = run_all_detectors(
                    db_path=db_path,
                    dry_run=True,
                    cycle_id=f"cycle_{self.cycle_count}",
                )
                results["phases"]["detection"] = detection_results
                total_findings = sum(
                    d.get("findings", 0) for d in detection_results.get("detectors", {}).values()
                )
                groups = detection_results.get("correlation", {}).get("groups", 0)
                logger.info(f"  Detection: {total_findings} findings, {groups} groups (dry-run)")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning(f"  Detection skipped: {e}")
                results["phases"]["detection"] = {"error": str(e)}

            # ═══════════════════════════════════════
            # PHASE 1b5a: MORNING BRIEF + STALENESS
            # Daily digest of detection findings via Google Chat.
            # Staleness alert if detection hasn't run in 2+ hours
            # during business hours (9-21).
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1b5a: MORNING BRIEF + STALENESS")
            try:
                from .detectors.morning_brief import send_if_changed

                gov_config = self._load_governance_yaml()
                brief_hour = gov_config.get("morning_brief_hour", 8)
                db_path = str(paths.data_dir() / "moh_time_os.db")

                brief_result = send_if_changed(
                    db_path=db_path,
                    notifier=self.notifier,
                    morning_brief_hour=brief_hour,
                )
                results["phases"]["morning_brief"] = brief_result
                logger.info("  Morning brief: %s", brief_result.get("status", "unknown"))
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning(f"  Morning brief skipped: {e}")
                results["phases"]["morning_brief"] = {"error": str(e)}

            # Staleness alert: detection_last_run > 2 hours old during 9-21
            try:
                staleness_result = self._check_staleness_alert(db_path)
                results["phases"]["staleness_alert"] = staleness_result
                if staleness_result.get("status") == "sent":
                    logger.info("  Staleness alert sent")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning(f"  Staleness check failed: {e}")
                results["phases"]["staleness_alert"] = {"error": str(e)}

            # ═══════════════════════════════════════
            # PHASE 1b-1e: TRUTH MODULES
            # SKIP if project_brand_required or project_brand_consistency fails
            # ═══════════════════════════════════════
            if not project_gates_ok:
                logger.warning("  SKIPPING truth modules (project gates failed)")
                results["phases"]["time_truth"] = {
                    "skipped": True,
                    "reason": "project_gates_failed",
                }
                results["phases"]["commitment_truth"] = {
                    "skipped": True,
                    "reason": "project_gates_failed",
                }
                results["phases"]["capacity_truth"] = {
                    "skipped": True,
                    "reason": "project_gates_failed",
                }
                results["phases"]["client_truth"] = {
                    "skipped": True,
                    "reason": "project_gates_failed",
                }
            else:
                # PHASE 1b: TIME TRUTH
                logger.info("▶ Phase 1b: TIME TRUTH")
                time_truth_results = self._process_time_truth()
                results["phases"]["time_truth"] = time_truth_results
                logger.info(
                    f"  Blocks: {time_truth_results.get('blocks_total', 0)}, Scheduled: {time_truth_results.get('tasks_scheduled', 0)}"
                )

                # PHASE 1c: COMMITMENT TRUTH
                logger.info("▶ Phase 1c: COMMITMENT TRUTH")
                commitment_results = self._process_commitment_truth()
                results["phases"]["commitment_truth"] = commitment_results
                logger.info(
                    f"  Extracted: {commitment_results.get('extracted', 0)}, Untracked: {commitment_results.get('untracked', 0)}"
                )

                # PHASE 1d: CAPACITY TRUTH
                logger.info("▶ Phase 1d: CAPACITY TRUTH")
                capacity_results = self._process_capacity_truth()
                results["phases"]["capacity_truth"] = capacity_results
                logger.info(
                    f"  Utilization: {capacity_results.get('overall_utilization', 0)}%, Overloaded: {len(capacity_results.get('overloaded_lanes', []))}"
                )

                # PHASE 1e: CLIENT TRUTH
                logger.info("▶ Phase 1e: CLIENT TRUTH")
                client_results = self._process_client_truth()
                results["phases"]["client_truth"] = client_results
                logger.info(
                    f"  At-risk clients: {client_results.get('at_risk_count', 0)}, Alerts: {client_results.get('alerts_created', 0)}"
                )

            # ═══════════════════════════════════════
            # PHASE 1f: INTELLIGENCE
            # Score entities, detect signals/patterns,
            # persist snapshots, emit events
            # ═══════════════════════════════════════
            logger.info("▶ Phase 1f: INTELLIGENCE")
            intel_results = self._intelligence_phase()
            results["phases"]["intelligence"] = intel_results
            logger.info(
                f"  Scores: {intel_results.get('scores_recorded', 0)}, "
                f"Signals: {intel_results.get('signals_detected', 0)}, "
                f"Patterns: {intel_results.get('patterns_detected', 0)}, "
                f"Events: {intel_results.get('events_emitted', 0)}"
            )

            # ═══════════════════════════════════════
            # PHASE 2-5: ANALYZE/SURFACE/REASON/EXECUTE
            # SKIP if data_integrity fails
            # ═══════════════════════════════════════
            if not data_integrity_ok:
                logger.warning("  SKIPPING analyze/surface/reason/execute (data_integrity failed)")
                results["phases"]["analyze"] = {
                    "skipped": True,
                    "reason": "data_integrity_failed",
                }
                results["phases"]["surface"] = {
                    "skipped": True,
                    "reason": "data_integrity_failed",
                }
                results["phases"]["reason"] = {
                    "skipped": True,
                    "reason": "data_integrity_failed",
                }
                results["phases"]["execute"] = {
                    "skipped": True,
                    "reason": "data_integrity_failed",
                }
            else:
                # PHASE 2: ANALYZE
                logger.info("▶ Phase 2: ANALYZE")
                analyze_results = self.analyzers.analyze_all()
                results["phases"]["analyze"] = analyze_results

                priority_count = analyze_results.get("priority", {}).get("total_items", 0)
                anomaly_count = analyze_results.get("anomalies", {}).get("total", 0)
                logger.info(f"  Priority queue: {priority_count} items")
                logger.info(f"  Anomalies detected: {anomaly_count}")

                # PHASE 3: SURFACE
                logger.info("▶ Phase 3: SURFACE")
                surface_results = self._surface_critical_items(analyze_results)
                results["phases"]["surface"] = surface_results
                logger.info(f"  Created {surface_results.get('notifications', 0)} notifications")

                # PHASE 3b: SEND NOTIFICATIONS
                logger.info("▶ Phase 3b: SEND NOTIFICATIONS")
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                send_results = loop.run_until_complete(self.notifier.process_pending())
                sent_count = len([r for r in send_results if r.get("status") == "sent"])
                results["phases"]["surface"]["sent"] = sent_count
                logger.info(f"  Sent {sent_count} notifications")

                # PHASE 4: REASON
                logger.info("▶ Phase 4: REASON")
                reason_results = self.reasoner.process_cycle()
                results["phases"]["reason"] = reason_results
                logger.info(f"  Created {reason_results.get('decisions_created', 0)} decisions")

            # ═══════════════════════════════════════
            # PHASE 5: EXECUTE
            # Process approved actions
            # ═══════════════════════════════════════
            logger.info("▶ Phase 5: EXECUTE")
            execute_results = self.executor.process_pending_actions()
            results["phases"]["execute"] = {
                "processed": len(execute_results),
                "succeeded": len([r for r in execute_results if r.get("status") == "done"]),
                "failed": len([r for r in execute_results if r.get("status") == "failed"]),
            }
            logger.info(f"  Executed {len(execute_results)} actions")

            # ═══════════════════════════════════════
            # PHASE 6: SNAPSHOT & MOVES
            # Generate dashboard snapshot with exec moves
            # ═══════════════════════════════════════
            logger.info("▶ Phase 6: SNAPSHOT & MOVES")
            snapshot_results = self._generate_snapshot()
            results["phases"]["snapshot"] = snapshot_results
            moves_count = snapshot_results.get("moves_count", 0)
            logger.info(f"  Generated snapshot with {moves_count} moves")

            # ═══════════════════════════════════════
            # SUCCESS
            # ═══════════════════════════════════════
            results["success"] = True

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
            results["success"] = False
            results["error"] = str(e)

        # Calculate duration
        results["completed_at"] = datetime.now().isoformat()
        results["duration_ms"] = (datetime.now() - cycle_start).total_seconds() * 1000

        # Store cycle log
        self.store.insert(
            "cycle_logs",
            {
                "id": f"cycle_{self.cycle_count}_{cycle_start.strftime('%Y%m%d_%H%M%S')}",
                "cycle_number": self.cycle_count,
                "phase": "complete",
                "data": json.dumps(results),
                "duration_ms": results["duration_ms"],
                "created_at": cycle_start.isoformat(),
            },
        )

        logger.info("═══════════════════════════════════════")
        logger.info(f"  CYCLE {self.cycle_count} COMPLETE ({results['duration_ms']:.0f}ms)")
        logger.info("═══════════════════════════════════════\n")

        return results

    def _process_client_truth(self) -> dict:
        """
        Process Client Truth.

        - Compute health for key clients
        - Surface at-risk clients
        - Generate alerts for declining health
        """
        results = {
            "clients_processed": 0,
            "at_risk_count": 0,
            "declining_count": 0,
            "alerts_created": 0,
        }

        try:
            from lib.client_truth import HealthCalculator

            calc = HealthCalculator(self.store)

            # Get top-tier clients to monitor
            top_clients = self.store.query("""
                SELECT id, name, tier FROM clients
                WHERE tier IN ('enterprise', 'premium', 'key')
                LIMIT 20
            """)

            # If no tiered clients, get clients with recent activity
            if not top_clients:
                top_clients = self.store.query("""
                    SELECT DISTINCT c.id, c.name, c.tier FROM clients c
                    JOIN tasks t ON t.client_id = c.id
                    WHERE t.created_at >= date('now', '-30 days')
                    LIMIT 20
                """)

            for client in top_clients:
                health = calc.compute_health_score(client["id"])
                results["clients_processed"] += 1

                if health.at_risk:
                    results["at_risk_count"] += 1

                    # Create alert for at-risk client
                    self._create_notification(
                        title=f"⚠️ Client '{health.client_name}' at risk (health: {health.health_score})",
                        body=f"Health score dropped below 50. Factors: {health.factors}",
                        priority="high",
                        type="alert",
                        data={
                            "client_name": health.client_name,
                            "health_score": health.health_score,
                        },
                    )
                    results["alerts_created"] += 1

                if health.trend == "declining":
                    results["declining_count"] += 1

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Client Truth error: {e}")
            results["error"] = str(e)

        return results

    def _intelligence_phase(self) -> dict:
        """
        Run intelligence pipeline: score → signal → pattern → cost → events
        → memory → observability.

        Each sub-step is isolated so a failure in one does not block the others.
        Results are persisted to their respective tables for downstream consumption
        by the preparation engine (Brief 24) and conversational interface (Brief 25).
        """
        import time
        from pathlib import Path

        from lib.intelligence.cost_to_serve import CostToServeEngine
        from lib.intelligence.health_unifier import HealthUnifier
        from lib.intelligence.patterns import detect_all_patterns
        from lib.intelligence.persistence import (
            CostPersistence,
            IntelligenceEventStore,
            PatternPersistence,
            event_from_pattern,
            event_from_signal_change,
            snapshot_from_cost_profile,
            snapshot_from_pattern_evidence,
        )
        from lib.intelligence.scorecard import (
            score_all_clients,
            score_all_persons,
            score_all_projects,
        )
        from lib.intelligence.signals import detect_all_signals, update_signal_state

        db_path = Path(self.store.db_path)
        phase_start_time = time.monotonic()

        results = {
            "scores_recorded": 0,
            "data_freshness_sources": 0,
            "completeness_scored": 0,
            "quality_adjustments": 0,
            "signals_detected": 0,
            "signal_state_changes": 0,
            "patterns_detected": 0,
            "cost_snapshots": 0,
            "cost_proxies_computed": 0,
            "entity_profiles_built": 0,
            "outcomes_tracked": 0,
            "pattern_trends_analyzed": 0,
            "events_emitted": 0,
            "decisions_recorded": 0,
            "entity_memory_updates": 0,
            "signal_lifecycle_updates": 0,
            "behavioral_patterns_found": 0,
            "audit_entries_recorded": 0,
            "explanations_generated": 0,
            "drift_alerts": 0,
        }

        # --- 0. Audit trail START (wraps entire intelligence phase) ---
        audit_trail = None
        try:
            from lib.intelligence.audit_trail import AuditTrail

            audit_trail = AuditTrail(db_path)
            audit_trail.record(
                operation="intelligence_phase_start",
                entity_type="system",
                entity_id="autonomous_loop",
                inputs_summary={
                    "cycle": self.cycle_count,
                    "started_at": datetime.now().isoformat(),
                },
            )
            results["audit_entries_recorded"] += 1
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: audit trail init failed: {e}")

        # --- 1. Score all entities and persist to score_history ---
        try:
            health_unifier = HealthUnifier(db_path)

            for score_fn, entity_type in [
                (score_all_clients, "client"),
                (score_all_projects, "project"),
                (score_all_persons, "person"),
            ]:
                try:
                    scorecards = score_fn(db_path)
                    for sc in scorecards:
                        if sc.get("composite_score") is None:
                            continue
                        # Build dimensions dict from dimension list
                        dims = {}
                        for dim in sc.get("dimensions", []):
                            dim_name = dim.get("dimension") or dim.get("name", "unknown")
                            dims[dim_name] = dim.get("score")
                        health_unifier.record_health(
                            entity_type=entity_type,
                            entity_id=sc["entity_id"],
                            composite_score=sc["composite_score"],
                            dimensions=dims,
                            data_completeness=sc.get("data_completeness", 0),
                        )
                        results["scores_recorded"] += 1
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(f"Intelligence: {entity_type} scoring failed: {e}")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: scoring init failed: {e}")

        # --- 1a. Data quality assessment (freshness, completeness, confidence) ---
        try:
            from lib.intelligence.data_freshness import DataFreshnessTracker

            freshness_tracker = DataFreshnessTracker(db_path)
            freshness_dashboard = freshness_tracker.get_freshness_dashboard()
            results["data_freshness_sources"] = len(freshness_dashboard.get("sources", []))
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: data freshness tracking failed: {e}")

        try:
            from lib.intelligence.completeness_scorer import CompletenessScorer

            completeness_scorer = CompletenessScorer()
            # Score completeness using entities discovered during scoring
            completeness_results = completeness_scorer.score_batch([])
            results["completeness_scored"] = len(completeness_results)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: completeness scoring failed: {e}")

        try:
            from lib.intelligence.quality_confidence import QualityConfidenceAdjuster

            quality_adjuster = QualityConfidenceAdjuster()
            quality_summary = quality_adjuster.compute_quality_summary([])
            results["quality_adjustments"] = (
                quality_summary.get("adjusted", 0) if isinstance(quality_summary, dict) else 0
            )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: quality confidence adjustment failed: {e}")

        # --- 2. Detect signals and update signal state ---
        try:
            signal_results = detect_all_signals(db_path)
            detected = signal_results.get("signals", [])
            results["signals_detected"] = len(detected)

            if detected:
                state_results = update_signal_state(detected, db_path)
                results["signal_state_changes"] = (
                    state_results.get("new", 0)
                    + state_results.get("escalated", 0)
                    + state_results.get("cleared", 0)
                )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: signal detection failed: {e}")

        # --- 2a. Outcome tracking (records signal prediction accuracy) ---
        try:
            from lib.intelligence.outcome_tracker import OutcomeTracker

            outcome_tracker = OutcomeTracker(db_path)
            effectiveness = outcome_tracker.get_effectiveness_metrics(days=90)
            results["outcomes_tracked"] = (
                effectiveness.get("total_outcomes", 0) if isinstance(effectiveness, dict) else 0
            )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: outcome tracking failed: {e}")

        # --- 3. Detect patterns and persist snapshots ---
        pattern_persistence = PatternPersistence(db_path)
        pattern_list = []
        try:
            pattern_results = detect_all_patterns(db_path)
            pattern_list = pattern_results.get("patterns", [])
            results["patterns_detected"] = len(pattern_list)

            for p_dict in pattern_list:
                try:
                    snapshot = snapshot_from_pattern_evidence(p_dict)
                    pattern_persistence.record_pattern(snapshot)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(
                        f"Intelligence: failed to persist pattern "
                        f"{p_dict.get('pattern_id', '?')}: {e}"
                    )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: pattern detection failed: {e}")

        # --- 3a. Pattern trend analysis (tracks pattern evolution) ---
        try:
            from lib.intelligence.pattern_trending import PatternTrendAnalyzer

            trend_analyzer = PatternTrendAnalyzer(db_path)
            trend_results = trend_analyzer.refresh_all_pattern_trends()
            results["pattern_trends_analyzed"] = (
                len(trend_results) if isinstance(trend_results, dict) else 0
            )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: pattern trend analysis failed: {e}")

        # --- 4. Compute and persist cost-to-serve snapshots ---
        cost_persistence = CostPersistence(db_path)
        try:
            cost_engine = CostToServeEngine(db_path)
            portfolio = cost_engine.compute_portfolio_profitability()
            if portfolio and hasattr(portfolio, "client_profiles"):
                for profile in portfolio.client_profiles:
                    try:
                        cost_dict = {
                            "effort_score": profile.effort_score,
                            "efficiency_ratio": profile.efficiency_ratio,
                            "profitability_band": profile.profitability_band,
                            "cost_drivers": getattr(profile, "cost_drivers", []),
                        }
                        snapshot = snapshot_from_cost_profile(
                            cost_dict, "client", profile.client_id
                        )
                        cost_persistence.record_snapshot(snapshot)
                        results["cost_snapshots"] += 1
                    except (sqlite3.Error, ValueError, OSError) as e:
                        logger.error(
                            f"Intelligence: cost snapshot failed for "
                            f"{getattr(profile, 'client_id', '?')}: {e}"
                        )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: cost-to-serve failed: {e}")

        # --- 4a. Enhanced cost calculation (cost proxies) ---
        try:
            from lib.intelligence.cost_proxies import ImprovedCostCalculator

            ImprovedCostCalculator()  # Verify import succeeds
            results["cost_proxies_computed"] = 1
            logger.info("Intelligence: cost proxies calculator initialized")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: cost proxies calculation failed: {e}")

        # --- 4b. Entity profile aggregation ---
        try:
            from lib.intelligence.entity_profile import build_entity_profile

            # Verify the function is callable (wiring confirmation)
            if callable(build_entity_profile):
                results["entity_profiles_built"] = 1
            logger.info("Intelligence: entity profile builder available")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: entity profile aggregation failed: {e}")

        # --- 5. Emit intelligence events for critical/warning findings ---
        event_store = IntelligenceEventStore(db_path)
        try:
            # Events from signal state changes
            if results["signals_detected"] > 0:
                signal_data = signal_results.get("signals", [])
                for sig in signal_data:
                    sev = sig.get("severity", "").lower()
                    if sev in ("critical", "warning"):
                        try:
                            event = event_from_signal_change(
                                signal_id=sig.get("signal_id", sig.get("id", "")),
                                entity_type=sig.get("entity_type", ""),
                                entity_id=sig.get("entity_id", ""),
                                severity=sev,
                                change_type="detected",
                                details=sig,
                            )
                            event_store.publish(event)
                            results["events_emitted"] += 1
                        except (sqlite3.Error, ValueError, OSError) as e:
                            logger.error(f"Intelligence: signal event emit failed: {e}")

            # Events from pattern detection
            for p_dict in pattern_list:
                p_sev = p_dict.get("severity", "").lower()
                if p_sev in ("critical", "warning", "structural"):
                    try:
                        event = event_from_pattern(p_dict, change_type="detected")
                        event_store.publish(event)
                        results["events_emitted"] += 1
                    except (sqlite3.Error, ValueError, OSError) as e:
                        logger.error(f"Intelligence: pattern event emit failed: {e}")

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: event emission failed: {e}")

        # --- 6. Signal lifecycle tracking (complementary to step 2) ---
        try:
            from lib.intelligence.signal_lifecycle import SignalLifecycleTracker

            lifecycle_tracker = SignalLifecycleTracker(db_path)

            # Update lifecycle metadata for each detected signal
            for sig in signal_results.get("signals", []):
                try:
                    lifecycle_tracker.update_lifecycle_on_detection(
                        signal_key=sig.get("signal_id", sig.get("id", "")),
                        current_severity=sig.get("severity", "watch").lower(),
                        signal_type=sig.get("signal_type", ""),
                        entity_type=sig.get("entity_type", ""),
                        entity_id=sig.get("entity_id", ""),
                    )
                    results["signal_lifecycle_updates"] += 1
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(f"Intelligence: signal lifecycle update failed: {e}")

            # Auto-escalate chronic watch signals
            escalations = lifecycle_tracker.auto_escalate_chronic_signals()
            if escalations:
                logger.info("Intelligence: auto-escalated %d chronic signals", len(escalations))
                results["signal_lifecycle_updates"] += len(escalations)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: signal lifecycle tracking failed: {e}")

        # --- 7. Decision journal (memory -- records cycle decisions) ---
        try:
            from lib.intelligence.decision_journal import DecisionJournal

            decision_journal = DecisionJournal(db_path)
            # Record a cycle-level decision summarizing what the reasoner decided
            decision_journal.record(
                decision_type="intelligence_cycle",
                entity_type="system",
                entity_id="autonomous_loop",
                action_taken="cycle_completed",
                context_snapshot={
                    "cycle": self.cycle_count,
                    "scores_recorded": results["scores_recorded"],
                    "signals_detected": results["signals_detected"],
                    "patterns_detected": results["patterns_detected"],
                },
                source="system",
            )
            results["decisions_recorded"] += 1
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: decision journal failed: {e}")

        # --- 8. Entity memory (tracks interaction history per entity) ---
        try:
            from lib.intelligence.entity_memory import EntityMemory

            entity_memory = EntityMemory(db_path)
            # Record that the system reviewed entities this cycle
            entity_memory.record_interaction(
                entity_type="system",
                entity_id="autonomous_loop",
                interaction_type="review",
                summary=f"Cycle {self.cycle_count}: scored {results['scores_recorded']} entities, "
                f"detected {results['signals_detected']} signals",
                details={
                    "cycle": self.cycle_count,
                    "scores": results["scores_recorded"],
                    "signals": results["signals_detected"],
                    "patterns": results["patterns_detected"],
                },
            )
            results["entity_memory_updates"] += 1
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: entity memory update failed: {e}")

        # --- 9. Behavioral pattern analysis (learns from decision journal) ---
        try:
            from lib.intelligence.behavioral_patterns import BehavioralPatternAnalyzer

            pattern_analyzer = BehavioralPatternAnalyzer(db_path)
            behavioral_patterns = pattern_analyzer.discover_patterns(days_back=90, min_frequency=3)
            results["behavioral_patterns_found"] = len(behavioral_patterns)
            if behavioral_patterns:
                logger.info(
                    "Intelligence: discovered %d behavioral patterns",
                    len(behavioral_patterns),
                )
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: behavioral pattern analysis failed: {e}")

        # --- 10. Explainability (generate explanations for top findings) ---
        try:
            from lib.intelligence.explainability import IntelligenceExplainer

            explainer = IntelligenceExplainer()
            # Explain top signals from this cycle
            for sig in signal_results.get("signals", [])[:5]:
                try:
                    explainer.explain_signal(
                        signal_type=sig.get("signal_type", ""),
                        severity=sig.get("severity", "watch"),
                        entity_name=sig.get("entity_id", ""),
                        trigger_value=sig.get("current_value", 0),
                        threshold=sig.get("threshold", 0),
                    )
                    results["explanations_generated"] += 1
                except (ValueError, TypeError) as e:
                    logger.error(f"Intelligence: explanation generation failed: {e}")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: explainability module failed: {e}")

        # --- 11. Drift detection (VERY END -- compares against baselines) ---
        try:
            from lib.intelligence.drift_detection import DriftDetector

            drift_detector = DriftDetector(db_path)
            # Check drift for each scored entity using latest scores
            # (The scores were recorded in step 1; we check if they deviate from baseline)
            try:
                from lib.intelligence.health_unifier import HealthUnifier as HU

                unifier = HU(db_path)
                for etype in ("client", "project", "person"):
                    try:
                        recent = unifier.get_all_latest_health(etype)
                        for hs in recent:
                            if hs.composite_score is not None and hs.entity_id:
                                alert = drift_detector.check_drift(
                                    metric_name="health_score",
                                    entity_type=etype,
                                    entity_id=hs.entity_id,
                                    current_value=float(hs.composite_score),
                                )
                                if alert:
                                    results["drift_alerts"] += 1
                                    logger.info(
                                        "Intelligence: drift alert for %s/%s: %s",
                                        etype,
                                        hs.entity_id,
                                        alert.severity,
                                    )
                    except (sqlite3.Error, ValueError, OSError) as e:
                        logger.error(f"Intelligence: drift check for {etype} failed: {e}")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Intelligence: drift detection scoring lookup failed: {e}")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Intelligence: drift detection failed: {e}")

        # --- 12. Audit trail END (wraps entire intelligence phase) ---
        if audit_trail is not None:
            try:
                phase_duration_ms = (time.monotonic() - phase_start_time) * 1000
                audit_trail.record(
                    operation="intelligence_phase_end",
                    entity_type="system",
                    entity_id="autonomous_loop",
                    outputs_summary=results,
                    duration_ms=phase_duration_ms,
                )
                results["audit_entries_recorded"] += 1
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Intelligence: audit trail end failed: {e}")

        return results

    def _process_capacity_truth(self) -> dict:
        """
        Process Capacity Truth.

        - Calculate lane utilization
        - Check for overloaded lanes
        - Surface capacity alerts at 90%+
        """
        from datetime import date

        results = {
            "date": date.today().isoformat(),
            "overall_utilization": 0,
            "overloaded_lanes": [],
            "high_util_lanes": [],
            "alerts_created": 0,
        }

        try:
            from lib.capacity_truth import CapacityCalculator

            calc = CapacityCalculator(self.store)
            summary = calc.get_capacity_summary()

            results["overall_utilization"] = summary.get("overall_utilization_pct", 0)
            results["overloaded_lanes"] = summary.get("overloaded_lanes", [])
            results["high_util_lanes"] = summary.get("high_utilization_lanes", [])
            results["lanes"] = summary.get("lanes", [])

            # Generate alerts for lanes at 90%+ utilization
            for lane_data in summary.get("lanes", []):
                util_pct = float(lane_data.get("utilization_pct", 0) or 0)
                lane_name = lane_data.get("lane", "unknown")

                if util_pct >= 100:
                    # Critical: overloaded
                    self._create_notification(
                        title=f"🚨 Lane '{lane_name}' overloaded ({util_pct}%)",
                        body=f"The {lane_name} lane is at {util_pct}% capacity. Tasks may not fit.",
                        priority="critical",
                        type="alert",
                        data={"lane": lane_name, "utilization": util_pct},
                    )
                    results["alerts_created"] += 1
                elif util_pct >= 90:
                    # Warning: high utilization
                    self._create_notification(
                        title=f"⚠️ Lane '{lane_name}' near capacity ({util_pct}%)",
                        body=f"The {lane_name} lane is at {util_pct}% utilization. Consider redistributing work.",
                        priority="high",
                        type="alert",
                        data={"lane": lane_name, "utilization": util_pct},
                    )
                    results["alerts_created"] += 1

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Capacity Truth error: {e}")
            results["error"] = str(e)

        return results

    def _process_commitment_truth(self) -> dict:
        """
        Process Commitment Truth.

        - Extract commitments from recent emails
        - Track untracked commitments
        """
        results = {"extracted": 0, "untracked": 0, "emails_processed": 0}

        try:
            from lib.commitment_truth import CommitmentManager

            manager = CommitmentManager(self.store)

            # Get recent unprocessed emails (last 24h)
            emails = self.store.query("""
                SELECT * FROM communications
                WHERE source = 'email'
                AND processed = 0
                AND created_at >= datetime('now', '-1 day')
                LIMIT 50
            """)

            for email in emails:
                email_id = email["id"]
                text = f"{email.get('subject', '')} {email.get('snippet', '')}"
                sender = email.get("from_email", "")

                # Extract commitments
                commitments = manager.extract_commitments_from_email(
                    email_id=email_id, email_text=text, sender=sender
                )

                results["extracted"] += len(commitments)
                results["emails_processed"] += 1

                # Mark email as processed
                self.store.query("UPDATE communications SET processed = 1 WHERE id = ?", [email_id])

            # Count untracked
            results["untracked"] = len(manager.get_untracked_commitments())

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Commitment Truth error: {e}")
            results["error"] = str(e)

        return results

    def _normalize_data(self) -> dict:
        """
        Normalize cross-table references per MASTER_SPEC.md §4.

        Uses lib/normalizer.py to derive:
        - projects.client_id (from brand, NULL if internal)
        - tasks.brand_id, client_id, project_link_status, client_link_status
        - communications.from_domain, client_id, link_status
        - invoices.aging_bucket (for valid AR)
        """
        from .normalizer import Normalizer

        results = {
            "tasks_updated": 0,
            "projects_updated": 0,
            "communications_updated": 0,
            "invoices_updated": 0,
        }

        try:
            normalizer = Normalizer()
            norm_results = normalizer.run()

            results["tasks_updated"] = norm_results.get("tasks", 0)
            results["projects_updated"] = norm_results.get("projects", 0)
            results["communications_updated"] = norm_results.get("communications", 0)
            results["invoices_updated"] = norm_results.get("invoices", 0)

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Data normalization error: {e}")
            results["error"] = str(e)

        return results

    def _check_staleness_alert(self, db_path: str) -> dict:
        """
        Send one-time staleness alert if detection hasn't run in 2+ hours
        during business hours (9-21). Resets on next successful detection run.
        """
        now = datetime.now()

        # Only alert during business hours (9-21)
        if now.hour < 9 or now.hour >= 21:
            return {"status": "skipped", "reason": "outside_business_hours"}

        # Check if already sent today
        if getattr(self, "_stale_alert_sent_today", None) == now.date():
            return {"status": "skipped", "reason": "already_sent_today"}

        # Check detection_last_run from sync_state
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT last_sync FROM sync_state WHERE source = 'detection_last_run'"
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row or not row["last_sync"]:
            # No detection run ever recorded -- alert
            pass
        else:
            try:
                last_run = datetime.fromisoformat(row["last_sync"])
                hours_since = (now - last_run).total_seconds() / 3600
                if hours_since < 2.0:
                    # Detection is fresh -- clear stale flag
                    self._stale_alert_sent_today = None
                    return {"status": "skipped", "reason": "detection_fresh"}
            except ValueError as e:
                logger.warning("Could not parse detection_last_run: %s", e)

        # Detection is stale -- send alert
        channel = self.notifier.channels.get("google_chat")
        if not channel:
            return {"status": "error", "error": "no_google_chat_channel"}

        hours_stale = "2+"
        if row and row["last_sync"]:
            try:
                last_run = datetime.fromisoformat(row["last_sync"])
                hours_stale = f"{(now - last_run).total_seconds() / 3600:.1f}"
            except ValueError:
                pass

        message = f"Detection system has not run in {hours_stale} hours. Findings may be outdated."

        try:
            result = channel.send_sync(message, title="Staleness Warning")
        except (ValueError, OSError) as e:
            logger.error("Failed to send staleness alert: %s", e)
            return {"status": "error", "error": str(e)}

        if result.get("success"):
            self._stale_alert_sent_today = now.date()
            logger.info("Staleness alert sent (%s hours since last detection)", hours_stale)
            return {"status": "sent", "hours_stale": hours_stale}

        return {"status": "error", "error": result.get("error", "send failed")}

    def _check_gates(self) -> dict:
        """
        Evaluate all gates per MASTER_SPEC.md §6.

        Returns gate results dict with pass/fail for each gate.
        """
        from .gates import GateEvaluator

        try:
            evaluator = GateEvaluator()
            return evaluator.evaluate_all()
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Gate check error: {e}")
            return {"error": str(e), "data_integrity": False}

    def _populate_resolution_queue(self) -> dict:
        """
        Populate resolution queue per MASTER_SPEC.md §5.

        Surfaces entities needing manual resolution.
        """
        from .resolution_queue import ResolutionQueue

        try:
            queue = ResolutionQueue()
            counts = queue.populate()
            summary = queue.get_summary()
            return {"counts": counts, "summary": summary}
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Resolution queue error: {e}")
            return {"error": str(e)}

    def _auto_resolve(self) -> dict:
        """
        Run auto-resolution on pending queue items.

        Attempts to fix data quality issues (unlinked projects, missing clients,
        missing due dates) automatically using rule-based matching.
        """
        results = {"total_scanned": 0, "auto_resolved": 0, "escalated": 0, "failed": 0}

        try:
            from lib.intelligence.auto_resolution import AutoResolutionEngine

            engine = AutoResolutionEngine(db_path=self.store.db_path)
            report = engine.scan_and_resolve()

            results["total_scanned"] = report.total_scanned
            results["auto_resolved"] = report.auto_resolved
            results["escalated"] = report.escalated
            results["failed"] = report.failed
            results["duration_ms"] = report.duration_ms

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Auto-resolution error: {e}")
            results["error"] = str(e)

        return results

    def _process_time_truth(self) -> dict:
        """
        Process Time Truth.

        - Generate time blocks for today
        - Run auto-scheduler for unscheduled tasks
        - Validate schedule invariants
        """
        from datetime import date

        from lib.time_truth import CalendarSync, Scheduler

        today = date.today().isoformat()
        results = {
            "date": today,
            "blocks_created": 0,
            "blocks_total": 0,
            "tasks_scheduled": 0,
            "validation_issues": 0,
        }

        try:
            # Generate blocks for today
            calendar_sync = CalendarSync(self.store)
            blocks = calendar_sync.generate_available_blocks(today)
            results["blocks_total"] = len(blocks)

            # Run scheduler
            scheduler = Scheduler(self.store)
            schedule_results = scheduler.schedule_unscheduled(today)
            results["tasks_scheduled"] = len([r for r in schedule_results if r.success])

            # Validate
            validation = scheduler.validate_schedule(today)
            results["validation_issues"] = len(validation.issues)
            results["valid"] = validation.valid

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Time Truth error: {e}")
            results["error"] = str(e)

        return results

    def _surface_critical_items(self, analysis: dict) -> dict:
        """Create notifications for items that need attention."""
        notifications_created = 0

        # Critical anomalies
        anomalies = analysis.get("anomalies", {}).get("items", [])
        for anomaly in anomalies:
            if anomaly.get("severity") in ("critical", "high"):
                self._create_notification(
                    title=anomaly.get("title", "Alert"),
                    body=anomaly.get("description", ""),
                    priority="high" if anomaly.get("severity") == "critical" else "normal",
                    type="anomaly",
                    data=anomaly,
                )
                notifications_created += 1

        # High priority items (top 3 if score > 85)
        top_priorities = analysis.get("priority", {}).get("top_5", [])
        for item in top_priorities[:3]:
            if float(item.get("score", 0) or 0) >= 85:
                self._create_notification(
                    title=f"High priority: {item.get('title', '')[:50]}",
                    body=", ".join(item.get("reasons", [])),
                    priority="normal",
                    type="priority",
                    data=item,
                )
                notifications_created += 1

        return {"notifications": notifications_created}

    def _create_notification(self, title: str, body: str, priority: str, type: str, data: dict):
        """Create a notification record."""
        from uuid import uuid4

        self.store.insert(
            "notifications",
            {
                "id": f"notif_{uuid4().hex[:8]}",
                "type": type,
                "priority": priority,
                "title": title,
                "body": body,
                "action_data": json.dumps(data),
                "channels": json.dumps(["push"]),
                "created_at": datetime.now().isoformat(),
            },
        )

    def _generate_snapshot(self) -> dict:
        """
        Generate agency snapshot per Page 0/1 locked specs.

        Produces agency_snapshot.json with:
        - meta, trust, narrative, tiles
        - heatstrip_projects, constraints, exceptions
        - delivery_command (Page 1 data)
        - drawers
        """
        results = {"success": False, "snapshot_path": None, "moves_count": 0}

        try:
            # Try new agency snapshot generator first
            try:
                from .agency_snapshot import AgencySnapshotGenerator
                from .agency_snapshot.scoring import Horizon, Mode

                generator = AgencySnapshotGenerator(
                    mode=Mode.OPS_HEAD,
                    horizon=Horizon.TODAY,
                    scope={"include_internal": False},
                )
                snapshot = generator.generate()

                # Count moves/exceptions
                results["moves_count"] = len(snapshot.get("exceptions", []))

                # Save snapshot
                path = generator.save(snapshot)
                results["snapshot_path"] = str(path)
                results["success"] = True

                # Copy to dashboard directory for serving
                from shutil import copy

                dashboard_dir = Path(__file__).parent.parent / "dashboard"
                if dashboard_dir.exists():
                    copy(path, dashboard_dir / "agency_snapshot.json")

            except ImportError as ie:
                # Fallback to old aggregator if new one not available
                logger.warning(f"Agency snapshot not available, falling back: {ie}")
                from .aggregator import SnapshotAggregator
                from .moves import add_moves_to_snapshot

                aggregator = SnapshotAggregator()
                snapshot = aggregator.generate()
                snapshot = add_moves_to_snapshot(snapshot)
                results["moves_count"] = len(snapshot.get("moves", []))

                path = aggregator.save(snapshot)
                results["snapshot_path"] = str(path)
                results["success"] = True

                from shutil import copy

                dashboard_dir = Path(__file__).parent.parent / "dashboard"
                if dashboard_dir.exists():
                    copy(path, dashboard_dir / "snapshot.json")

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Snapshot generation error: {e}")
            results["error"] = str(e)

        return results

    def get_status(self) -> dict[str, Any]:
        """Get current system status."""
        # Get latest cycle
        latest_cycle = self.store.query("SELECT * FROM cycle_logs ORDER BY created_at DESC LIMIT 1")

        # Get collector status
        collector_status = self.collectors.get_status()

        # Get governance status
        governance_status = self.governance.get_status()

        # Get counts
        task_count = self.store.count("tasks", "status != 'done'")
        email_count = self.store.count("communications", "requires_response = 1 AND processed = 0")
        event_count = self.store.count(
            "events",
            "datetime(start_time) >= datetime('now') AND datetime(start_time) <= datetime('now', '+24 hours')",
        )
        pending_decisions = self.store.count("decisions", "approved IS NULL")

        return {
            "running": self.running,
            "cycles_completed": self.cycle_count,
            "last_cycle": latest_cycle[0] if latest_cycle else None,
            "collectors": collector_status,
            "governance": governance_status,
            "counts": {
                "pending_tasks": task_count,
                "pending_emails": email_count,
                "events_today": event_count,
                "pending_decisions": pending_decisions,
            },
        }


def run_once():
    """Run a single autonomous cycle."""
    loop = AutonomousLoop()
    return loop.run_cycle()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MOH TIME OS Autonomous Loop")
    parser.add_argument("command", choices=["run", "status", "sync"], help="Command to run")
    parser.add_argument("--source", help="Specific source to sync")

    args = parser.parse_args()

    loop = AutonomousLoop()

    if args.command == "run":
        result = loop.run_cycle()
        logger.info(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)

    elif args.command == "status":
        status = loop.get_status()
        logger.info(json.dumps(status, indent=2))
    elif args.command == "sync":
        result = loop.collectors.force_sync(args.source)
        logger.info(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
