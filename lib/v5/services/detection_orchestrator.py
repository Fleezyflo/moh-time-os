"""
Time OS V5 — Detection Orchestrator

Orchestrates running of all signal detectors.
"""

import logging
import traceback
from typing import Any

from ..database import Database
from ..detectors.base import SignalDetector
from ..detectors.registry import DetectorRegistry, get_registry
from ..models import Signal, now_iso
from .signal_service import SignalService

logger = logging.getLogger(__name__)


class DetectionStats:
    """Statistics from a detection run."""

    def __init__(self):
        self.started_at: str = now_iso()
        self.completed_at: str | None = None
        self.detectors_run: int = 0
        self.detectors_failed: int = 0
        self.signals_detected: int = 0
        self.signals_stored: int = 0
        self.signals_duplicate: int = 0
        self.signals_error: int = 0
        self.errors: list[dict[str, str]] = []
        self.by_detector: dict[str, dict[str, int]] = {}

    def record_detector(
        self, detector_id: str, detected: int, stored: int, duplicates: int, errors: int
    ) -> None:
        """Record stats for a detector."""
        self.by_detector[detector_id] = {
            "detected": detected,
            "stored": stored,
            "duplicates": duplicates,
            "errors": errors,
        }
        self.signals_detected += detected
        self.signals_stored += stored
        self.signals_duplicate += duplicates
        self.signals_error += errors

    def record_error(self, detector_id: str, error: str) -> None:
        """Record an error."""
        self.errors.append(
            {
                "detector_id": detector_id,
                "error": error,
                "timestamp": now_iso(),
            }
        )
        self.detectors_failed += 1

    def complete(self) -> None:
        """Mark detection as complete."""
        self.completed_at = now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "detectors_run": self.detectors_run,
            "detectors_failed": self.detectors_failed,
            "signals_detected": self.signals_detected,
            "signals_stored": self.signals_stored,
            "signals_duplicate": self.signals_duplicate,
            "signals_error": self.signals_error,
            "errors": self.errors,
            "by_detector": self.by_detector,
        }


class DetectionOrchestrator:
    """
    Orchestrates signal detection across all detectors.

    Responsibilities:
    - Run all detectors (or specific ones)
    - Deduplicate signals
    - Store valid signals
    - Collect statistics
    - Handle errors gracefully
    """

    def __init__(self, db: Database, registry: DetectorRegistry | None = None):
        """
        Initialize orchestrator.

        Args:
            db: Database instance
            registry: Detector registry (default: global registry)
        """
        self.db = db
        self.registry = registry or get_registry(db)
        self.signal_service = SignalService(db)

        # Auto-register built-in detectors if registry is empty
        if self.registry.count() == 0:
            self._register_builtin_detectors()

    def _register_builtin_detectors(self) -> None:
        """Register all built-in detectors."""
        from ..detectors.asana_task_detector import AsanaTaskDetector
        from ..detectors.calendar_meet_detector import CalendarMeetDetector
        from ..detectors.gchat_detector import GoogleChatDetector
        from ..detectors.gmail_detector import GmailDetector
        from ..detectors.xero_financial_detector import XeroFinancialDetector

        self.registry.register(AsanaTaskDetector)
        self.registry.register(XeroFinancialDetector)
        self.registry.register(GoogleChatDetector)
        self.registry.register(CalendarMeetDetector)
        self.registry.register(GmailDetector)

        logger.info(f"Registered {self.registry.count()} built-in detectors")

    # =========================================================================
    # Detection Execution
    # =========================================================================

    def run_detection(
        self, detector_ids: list[str] | None = None, skip_duplicates: bool = True
    ) -> DetectionStats:
        """
        Run detection for all or specified detectors.

        Args:
            detector_ids: Optional list of detector IDs to run (default: all)
            skip_duplicates: Skip signals that already exist

        Returns:
            DetectionStats with results
        """
        stats = DetectionStats()

        # Get detectors to run
        if detector_ids:
            detectors = [self.registry.get(did) for did in detector_ids]
            detectors = [d for d in detectors if d is not None]
        else:
            detectors = self.registry.get_all()

        if not detectors:
            logger.warning("No detectors to run")
            stats.complete()
            return stats

        logger.info(f"Running {len(detectors)} detector(s)")

        # Run each detector
        for detector in detectors:
            try:
                self._run_single_detector(detector, stats, skip_duplicates)
                stats.detectors_run += 1
            except Exception as e:
                logger.error(f"Detector {detector.detector_id} failed: {e}")
                logger.debug(traceback.format_exc())
                stats.record_error(detector.detector_id, str(e))

        stats.complete()

        logger.info(
            f"Detection complete: {stats.signals_stored} stored, "
            f"{stats.signals_duplicate} duplicates, "
            f"{stats.signals_error} errors"
        )

        return stats

    def run_detector(
        self, detector_id: str, skip_duplicates: bool = True
    ) -> DetectionStats:
        """
        Run a single detector.

        Args:
            detector_id: Detector ID to run
            skip_duplicates: Skip duplicate signals

        Returns:
            DetectionStats with results
        """
        return self.run_detection([detector_id], skip_duplicates)

    def _run_single_detector(
        self, detector: SignalDetector, stats: DetectionStats, skip_duplicates: bool
    ) -> None:
        """
        Run a single detector and process results.

        Args:
            detector: Detector to run
            stats: Stats to update
            skip_duplicates: Skip duplicate signals
        """
        detector_id = detector.detector_id
        logger.info(f"Running detector: {detector_id}")

        # Pre-load existing signals for deduplication
        if skip_duplicates:
            detector.load_existing_signals()

        # Run detection
        signals = detector.detect()
        detected_count = len(signals)

        logger.info(f"[{detector_id}] Detected {detected_count} signals")

        # Process signals
        stored = 0
        duplicates = 0
        errors = 0

        for signal in signals:
            try:
                # Check for duplicate
                if skip_duplicates and self._is_duplicate(signal, detector):
                    duplicates += 1
                    continue

                # Store signal
                self.signal_service.store_signal(signal)
                stored += 1

            except Exception as e:
                logger.error(f"[{detector_id}] Failed to store signal: {e}")
                errors += 1

        stats.record_detector(detector_id, detected_count, stored, duplicates, errors)

        logger.info(
            f"[{detector_id}] Stored {stored}, duplicates {duplicates}, errors {errors}"
        )

    def _is_duplicate(self, signal: Signal, detector: SignalDetector) -> bool:
        """
        Check if a signal is a duplicate.

        Args:
            signal: Signal to check
            detector: Detector that created it (for cached lookup)

        Returns:
            True if duplicate
        """
        return detector.signal_exists(signal.signal_type, signal.entity_id)

    # =========================================================================
    # Maintenance
    # =========================================================================

    def expire_old_signals(self) -> int:
        """
        Expire signals past their expiry date.

        Returns:
            Number of signals expired
        """
        return self.signal_service.expire_old_signals()

    def cleanup_archived_signals(self, older_than_days: int = 365) -> int:
        """
        Delete archived signals older than N days.

        Args:
            older_than_days: Delete signals older than this

        Returns:
            Number of signals deleted
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                DELETE FROM signals_v5
                WHERE status = 'archived'
                  AND detected_at < datetime('now', ?)
            """,
                (f"-{older_than_days} days",),
            )

            count = cursor.rowcount

        if count > 0:
            logger.info(f"Deleted {count} old archived signals")

        return count

    # =========================================================================
    # Information
    # =========================================================================

    def get_detector_info(self) -> list[dict[str, Any]]:
        """
        Get information about registered detectors.

        Returns:
            List of detector info dicts
        """
        result = []

        for detector_id in self.registry.list_ids():
            detector = self.registry.get(detector_id)
            if detector:
                result.append(
                    {
                        "detector_id": detector.detector_id,
                        "detector_version": detector.detector_version,
                        "signal_types": detector.signal_types,
                        "signal_type_count": len(detector.signal_types),
                    }
                )

        return result

    def get_signal_type_coverage(self) -> dict[str, str]:
        """
        Get mapping of signal types to detectors.

        Returns:
            Dict of signal_type -> detector_id
        """
        result = {}

        for detector_id, signal_types in self.registry.get_signal_types().items():
            for st in signal_types:
                result[st] = detector_id

        return result
