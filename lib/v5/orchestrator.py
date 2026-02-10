"""
Time OS V5 — Main Orchestrator

Coordinates all V5 components: detection, balancing, issue formation, resolution.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import Database, get_db
from .issues.formation_service import IssueFormationService
from .resolution.balance_service import BalanceService
from .resolution.resolution_service import ResolutionService
from .services.detection_orchestrator import DetectionOrchestrator
from .services.signal_service import SignalService

logger = logging.getLogger(__name__)


class TimeOSOrchestrator:
    """
    Main orchestrator for Time OS V5.

    Coordinates the full pipeline:
    1. Detection — Scan sources for signals
    2. Balancing — Process positive signals against negatives
    3. Issue Formation — Form issues from signal patterns
    4. Resolution Check — Auto-resolve balanced issues, check regressions
    """

    def __init__(self, db: Database | None = None, auto_migrate: bool = True):
        """
        Initialize orchestrator.

        Args:
            db: Database instance (uses singleton if not provided)
            auto_migrate: Run migrations if needed (default True)
        """
        self.db = db or get_db()

        # Auto-migrate on first run
        if auto_migrate:
            self._ensure_schema()

        # Initialize services
        self.detection = DetectionOrchestrator(self.db)
        self.signal_service = SignalService(self.db)
        self.balance_service = BalanceService(self.db)
        self.issue_formation = IssueFormationService(self.db)
        self.resolution_service = ResolutionService(self.db)

    def _ensure_schema(self) -> None:
        """Run migrations if V5 tables don't exist."""
        # Check if signals_v5 table exists
        exists = self.db.fetch_value("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name='signals_v5'
        """)

        if not exists:
            logger.info("V5 schema not found, running migrations...")
            migration_dir = Path(__file__).parent / "migrations"
            sql_file = migration_dir / "001_create_v5_schema.sql"

            if sql_file.exists():
                sql = sql_file.read_text()
                # Split by semicolons and execute each statement
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        try:
                            self.db.execute(stmt)
                        except Exception as e:
                            # Ignore "already exists" errors
                            if "already exists" not in str(e):
                                logger.warning(f"Migration statement warning: {e}")
                logger.info("V5 schema created successfully")
            else:
                logger.warning(f"Migration file not found: {sql_file}")

    # =========================================================================
    # Full Pipeline
    # =========================================================================

    def run_full_pipeline(self) -> dict[str, Any]:
        """
        Run the complete Time OS pipeline.

        Returns:
            Dict with stats from each stage
        """
        start_time = datetime.now()
        results = {
            "started_at": start_time.isoformat(),
            "detection": {},
            "balancing": {},
            "issue_formation": {},
            "resolution": {},
            "duration_seconds": 0,
        }

        logger.info("Starting Time OS V5 full pipeline...")

        try:
            # Stage 1: Detection
            logger.info("Stage 1: Detection")
            detection_stats = self.run_detection()
            results["detection"] = (
                detection_stats.to_dict()
                if hasattr(detection_stats, "to_dict")
                else detection_stats
            )

            # Stage 2: Balancing
            logger.info("Stage 2: Balancing")
            results["balancing"] = self.run_balancing()

            # Stage 3: Issue Formation
            logger.info("Stage 3: Issue Formation")
            results["issue_formation"] = self.run_issue_formation()

            # Stage 4: Resolution Check
            logger.info("Stage 4: Resolution Check")
            results["resolution"] = self.run_resolution_check()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            results["error"] = str(e)

        end_time = datetime.now()
        results["duration_seconds"] = (end_time - start_time).total_seconds()

        logger.info(f"Pipeline complete in {results['duration_seconds']:.1f}s")

        return results

    # =========================================================================
    # Individual Stages
    # =========================================================================

    def run_detection(self, detector_ids: list[str] | None = None) -> dict[str, Any]:
        """
        Run signal detection.

        Args:
            detector_ids: Optional list of detector IDs to run (all if None)

        Returns:
            Detection stats
        """
        return self.detection.run_detection(detector_ids)

    def run_balancing(self) -> dict[str, int]:
        """
        Run signal balancing for recent positive signals.

        Returns:
            Balancing stats
        """
        stats = {"processed": 0, "balanced": 0, "errors": 0}

        # Get unprocessed positive signals
        positive_signals = self.db.fetch_all("""
            SELECT id, signal_type, valence, scope_client_id, scope_brand_id,
                   scope_project_id, scope_retainer_id, scope_task_id,
                   entity_type, entity_id
            FROM signals_v5
            WHERE valence = 1
              AND status = 'active'
              AND detected_at > datetime('now', '-1 day')
        """)

        for signal in positive_signals:
            stats["processed"] += 1
            try:
                balanced = self.balance_service.process_new_signal(signal)
                if balanced:
                    stats["balanced"] += (
                        len(balanced) if isinstance(balanced, list) else 1
                    )
            except Exception as e:
                logger.warning(f"Balancing error for signal {signal.get('id')}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Balancing: {stats['balanced']}/{stats['processed']} signals balanced"
        )

        return stats

    def run_issue_formation(self) -> dict[str, int]:
        """
        Run issue formation.

        Returns:
            Formation stats
        """
        return self.issue_formation.run_formation()

    def run_resolution_check(self) -> dict[str, Any]:
        """
        Run resolution checks.

        Returns:
            Resolution stats
        """
        stats = {"auto_resolved": 0, "regressions": 0, "closed_after_monitoring": 0}

        # Check for auto-resolution
        resolution_stats = self.resolution_service.run_resolution_check()
        stats["auto_resolved"] = resolution_stats.get("auto_resolved", 0)

        # Check for regressions
        regressed_ids = self.resolution_service.check_regressions()
        stats["regressions"] = len(regressed_ids)

        return stats

    # =========================================================================
    # Status & Health
    # =========================================================================

    def get_system_status(self) -> dict[str, Any]:
        """
        Get overall system status.

        Returns:
            Status information
        """
        # Signal counts
        signal_counts = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN valence = -1 THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN valence = 0 THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN valence = 1 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
            FROM signals_v5
        """)

        # Issue counts
        issue_counts = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN state = 'surfaced' THEN 1 ELSE 0 END) as surfaced,
                SUM(CASE WHEN state = 'acknowledged' THEN 1 ELSE 0 END) as acknowledged,
                SUM(CASE WHEN state = 'addressing' THEN 1 ELSE 0 END) as addressing,
                SUM(CASE WHEN state = 'monitoring' THEN 1 ELSE 0 END) as monitoring,
                SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed
            FROM issues_v5
        """)

        # Client health
        client_health = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN health_status = 'healthy' THEN 1 ELSE 0 END) as healthy,
                SUM(CASE WHEN health_status = 'at_risk' THEN 1 ELSE 0 END) as at_risk,
                SUM(CASE WHEN health_status = 'critical' THEN 1 ELSE 0 END) as critical
            FROM clients
            WHERE archived_at IS NULL
        """)

        return {
            "signals": {
                "total": signal_counts["total"] or 0,
                "negative": signal_counts["negative"] or 0,
                "neutral": signal_counts["neutral"] or 0,
                "positive": signal_counts["positive"] or 0,
                "active": signal_counts["active"] or 0,
            },
            "issues": {
                "total": issue_counts["total"] or 0,
                "surfaced": issue_counts["surfaced"] or 0,
                "acknowledged": issue_counts["acknowledged"] or 0,
                "addressing": issue_counts["addressing"] or 0,
                "monitoring": issue_counts["monitoring"] or 0,
                "closed": issue_counts["closed"] or 0,
            },
            "clients": {
                "total": client_health["total"] or 0,
                "healthy": client_health["healthy"] or 0,
                "at_risk": client_health["at_risk"] or 0,
                "critical": client_health["critical"] or 0,
            },
        }

    def get_critical_issues(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get most critical active issues.

        Args:
            limit: Maximum issues to return

        Returns:
            List of critical issues
        """
        rows = self.db.fetch_all(
            """
            SELECT i.*, c.name as client_name
            FROM issues_v5 i
            LEFT JOIN clients c ON i.scope_client_id = c.id
            WHERE i.state IN ('surfaced', 'acknowledged', 'addressing')
            ORDER BY i.priority_score DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in rows]


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """CLI entry point for running the orchestrator."""
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Time OS V5 Orchestrator")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--detect", action="store_true", help="Run detection only")
    parser.add_argument("--balance", action="store_true", help="Run balancing only")
    parser.add_argument(
        "--issues", action="store_true", help="Run issue formation only"
    )
    parser.add_argument(
        "--resolve", action="store_true", help="Run resolution check only"
    )
    parser.add_argument("--status", action="store_true", help="Show system status")

    args = parser.parse_args()

    orchestrator = TimeOSOrchestrator()

    if args.status:
        import json

        status = orchestrator.get_system_status()
        logger.info(json.dumps(status, indent=2))
        return

    if args.detect:
        result = orchestrator.run_detection()
    elif args.balance:
        result = orchestrator.run_balancing()
    elif args.issues:
        result = orchestrator.run_issue_formation()
    elif args.resolve:
        result = orchestrator.run_resolution_check()
    else:
        # Default: full pipeline
        result = orchestrator.run_full_pipeline()

    import json

    logger.info(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
