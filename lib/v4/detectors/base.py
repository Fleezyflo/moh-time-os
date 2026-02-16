"""
Time OS V4 - Base Detector

Abstract base class for all detectors.
"""

import hashlib
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any

from ..signal_service import get_signal_service

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "moh_time_os.db")


class BaseDetector(ABC):
    """
    Base class for all signal detectors.

    Subclasses must implement:
    - detector_id: Unique identifier
    - version: Current version
    - signal_types: List of signal types this detector can produce
    - detect(): Main detection logic
    """

    detector_id: str = None
    version: str = "1.0.0"
    description: str = ""
    signal_types: list[str] = []

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.signal_svc = get_signal_service()
        self._register()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _register(self):
        """Register this detector version."""
        self.signal_svc.register_detector_version(
            self.detector_id, self.version, self.description, self.get_parameters()
        )

    def get_parameters(self) -> dict[str, Any]:
        """Return detector parameters (for versioning/audit)."""
        return {}

    def _compute_inputs_hash(self, scope: dict, data: Any) -> str:
        """Compute a hash of inputs for deduplication."""
        content = json.dumps({"scope": scope, "data_summary": str(data)[:1000]}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def run(self, scope: dict = None) -> dict[str, Any]:
        """
        Run the detector with timing and logging.

        Args:
            scope: Optional scope filters (entity types, time window, etc.)

        Returns:
            Run results including signals created
        """
        scope = scope or {}
        start_time = time.time()

        try:
            # Run detection
            signals_created = self.detect(scope)

            duration_ms = int((time.time() - start_time) * 1000)

            # Log run
            run_id = self.signal_svc.log_detector_run(
                detector_id=self.detector_id,
                detector_version=self.version,
                scope=scope,
                inputs_hash=self._compute_inputs_hash(scope, signals_created),
                output_counts={"signals_created": len(signals_created)},
                duration_ms=duration_ms,
                status="completed",
            )

            return {
                "run_id": run_id,
                "detector_id": self.detector_id,
                "version": self.version,
                "signals_created": len(signals_created),
                "signal_ids": [s["signal_id"] for s in signals_created],
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            # Log failed run
            self.signal_svc.log_detector_run(
                detector_id=self.detector_id,
                detector_version=self.version,
                scope=scope,
                inputs_hash="error",
                output_counts={"error": str(e)},
                duration_ms=duration_ms,
                status="failed",
            )

            raise

    @abstractmethod
    def detect(self, scope: dict) -> list[dict[str, Any]]:
        """
        Main detection logic. Must be implemented by subclasses.

        Args:
            scope: Detection scope (time window, entity filters)

        Returns:
            List of created signal records
        """
        pass

    def create_signal(
        self,
        signal_type: str,
        entity_ref_type: str,
        entity_ref_id: str,
        value: dict,
        severity: str,
        interpretation_confidence: float,
        linkage_confidence_floor: float,
        evidence_excerpt_ids: list[str] = None,
        evidence_artifact_ids: list[str] = None,
        expires_at: str = None,
    ) -> dict[str, Any]:
        """Helper to create a signal with this detector's ID/version."""
        return self.signal_svc.create_signal(
            signal_type=signal_type,
            entity_ref_type=entity_ref_type,
            entity_ref_id=entity_ref_id,
            value=value,
            severity=severity,
            interpretation_confidence=interpretation_confidence,
            linkage_confidence_floor=linkage_confidence_floor,
            evidence_excerpt_ids=evidence_excerpt_ids or [],
            evidence_artifact_ids=evidence_artifact_ids or [],
            detector_id=self.detector_id,
            detector_version=self.version,
            expires_at=expires_at,
        )
