"""
Time OS V5 — Detector Registry

Registry for signal detectors.
"""

import logging

from ..database import Database
from .base import SignalDetector

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """
    Registry for managing signal detectors.

    Allows registering, retrieving, and running detectors by ID.
    """

    def __init__(self, db: Database):
        """
        Initialize registry.

        Args:
            db: Database instance for detector initialization
        """
        self.db = db
        self._detectors: dict[str, SignalDetector] = {}
        self._detector_classes: dict[str, type[SignalDetector]] = {}

    # =========================================================================
    # Registration
    # =========================================================================

    def register_class(self, detector_class: type[SignalDetector]) -> None:
        """
        Register a detector class.

        The detector will be instantiated lazily when first accessed.

        Args:
            detector_class: Detector class to register
        """
        # Get detector_id from class attribute
        detector_id = detector_class.detector_id

        if not detector_id:
            raise ValueError(
                f"Detector class {detector_class.__name__} has no detector_id"
            )

        self._detector_classes[detector_id] = detector_class
        logger.debug(f"Registered detector class: {detector_id}")

    def register_instance(self, detector: SignalDetector) -> None:
        """
        Register a detector instance.

        Args:
            detector: Detector instance to register
        """
        if not detector.detector_id:
            raise ValueError(f"Detector {detector} has no detector_id")

        self._detectors[detector.detector_id] = detector
        logger.debug(f"Registered detector instance: {detector.detector_id}")

    def register(self, detector_or_class) -> None:
        """
        Register a detector (class or instance).

        Args:
            detector_or_class: Detector class or instance
        """
        if isinstance(detector_or_class, type):
            self.register_class(detector_or_class)
        else:
            self.register_instance(detector_or_class)

    # =========================================================================
    # Retrieval
    # =========================================================================

    def get(self, detector_id: str) -> SignalDetector | None:
        """
        Get a detector by ID.

        Lazily instantiates class-registered detectors.

        Args:
            detector_id: Detector ID

        Returns:
            Detector instance or None
        """
        # Check for existing instance
        if detector_id in self._detectors:
            return self._detectors[detector_id]

        # Check for registered class
        if detector_id in self._detector_classes:
            detector_class = self._detector_classes[detector_id]
            detector = detector_class(self.db)
            self._detectors[detector_id] = detector
            return detector

        return None

    def get_all(self) -> list[SignalDetector]:
        """
        Get all registered detectors.

        Instantiates all class-registered detectors.

        Returns:
            List of detector instances
        """
        # Instantiate all classes
        for detector_id in self._detector_classes:
            if detector_id not in self._detectors:
                self.get(detector_id)

        return list(self._detectors.values())

    def list_ids(self) -> list[str]:
        """
        List all registered detector IDs.

        Returns:
            List of detector IDs
        """
        ids = set(self._detectors.keys())
        ids.update(self._detector_classes.keys())
        return sorted(ids)

    # =========================================================================
    # Queries
    # =========================================================================

    def has(self, detector_id: str) -> bool:
        """
        Check if a detector is registered.

        Args:
            detector_id: Detector ID

        Returns:
            True if registered
        """
        return detector_id in self._detectors or detector_id in self._detector_classes

    def count(self) -> int:
        """
        Get count of registered detectors.

        Returns:
            Number of detectors
        """
        ids = set(self._detectors.keys())
        ids.update(self._detector_classes.keys())
        return len(ids)

    def get_signal_types(self) -> dict[str, list[str]]:
        """
        Get signal types by detector.

        Returns:
            Dict of detector_id -> signal_types list
        """
        result = {}

        for detector_id in self.list_ids():
            detector = self.get(detector_id)
            if detector:
                result[detector_id] = detector.signal_types

        return result

    def find_detector_for_signal_type(self, signal_type: str) -> str | None:
        """
        Find which detector handles a signal type.

        Args:
            signal_type: Signal type to find

        Returns:
            Detector ID or None
        """
        for detector_id, types in self.get_signal_types().items():
            if signal_type in types:
                return detector_id
        return None

    # =========================================================================
    # Removal
    # =========================================================================

    def unregister(self, detector_id: str) -> bool:
        """
        Unregister a detector.

        Args:
            detector_id: Detector ID

        Returns:
            True if unregistered
        """
        removed = False

        if detector_id in self._detectors:
            del self._detectors[detector_id]
            removed = True

        if detector_id in self._detector_classes:
            del self._detector_classes[detector_id]
            removed = True

        return removed

    def clear(self) -> None:
        """Clear all registered detectors."""
        self._detectors.clear()
        self._detector_classes.clear()


# Global registry instance
_registry: DetectorRegistry | None = None


def get_registry(db: Database = None) -> DetectorRegistry:
    """
    Get the global detector registry.

    Args:
        db: Database instance (required on first call)

    Returns:
        DetectorRegistry instance
    """
    global _registry

    if _registry is None:
        if db is None:
            raise ValueError("Database required to initialize registry")
        _registry = DetectorRegistry(db)

    return _registry


def set_registry(registry: DetectorRegistry) -> None:
    """
    Set the global detector registry.

    Args:
        registry: Registry instance
    """
    global _registry
    _registry = registry
