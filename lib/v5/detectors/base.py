"""
Time OS V5 — Base Signal Detector

Abstract base class for all signal detectors.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..database import Database
from ..models import Signal, SignalSource, generate_id, get_signal_category, now_iso

logger = logging.getLogger(__name__)


class SignalDetector(ABC):
    """
    Abstract base class for all signal detectors.

    Detectors analyze data from a specific source (Asana, Xero, etc.)
    and emit signals with valence and magnitude.

    Subclasses must implement:
    - detector_id: Unique identifier
    - detector_version: Version string
    - signal_types: List of signal types this detector can emit
    - detect(): Main detection logic
    """

    # Must be overridden by subclasses
    detector_id: str = ""
    detector_version: str = ""
    signal_types: list[str] = []

    def __init__(self, db: Database):
        """
        Initialize detector with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self._existing_signals: set[str] | None = None

    # =========================================================================
    # Abstract Methods
    # =========================================================================

    @abstractmethod
    def detect(self) -> list[Signal]:
        """
        Run detection and return list of signals.

        Must be implemented by subclasses.

        Returns:
            List of Signal objects
        """
        pass

    # =========================================================================
    # Signal Creation Helpers
    # =========================================================================

    def create_signal(
        self,
        signal_type: str,
        valence: int,
        magnitude: float,
        entity_type: str,
        entity_id: str,
        source_type: SignalSource,
        source_id: str | None = None,
        value: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        # Scope chain
        scope_task_id: str | None = None,
        scope_project_id: str | None = None,
        scope_retainer_id: str | None = None,
        scope_brand_id: str | None = None,
        scope_client_id: str | None = None,
        scope_person_id: str | None = None,
        # Optional fields
        source_url: str | None = None,
        source_excerpt: str | None = None,
        detection_confidence: float = 0.9,
        attribution_confidence: float = 0.9,
        expires_at: datetime | None = None,
    ) -> Signal:
        """
        Create a signal with proper defaults and validation.

        Args:
            signal_type: Type of signal (e.g., "task_overdue")
            valence: Direction (-1 negative, 0 neutral, 1 positive)
            magnitude: Intensity (0.0 to 1.0)
            entity_type: Type of entity this signal is about
            entity_id: ID of the entity
            source_type: Where this signal came from
            source_id: ID in the source system
            value: Signal-specific payload data
            occurred_at: When the underlying event happened
            scope_*: Scope chain for aggregation
            source_url: Direct link to source
            source_excerpt: Summary or quote from source
            detection_confidence: How confident we are this is a real signal
            attribution_confidence: How confident we are about the entity
            expires_at: When this signal becomes stale

        Returns:
            Signal object (not yet persisted)
        """
        # Validate valence
        if valence not in (-1, 0, 1):
            raise ValueError(f"Valence must be -1, 0, or 1, got {valence}")

        # Validate magnitude
        if not (0.0 <= magnitude <= 1.0):
            raise ValueError(f"Magnitude must be 0.0-1.0, got {magnitude}")

        # Get category from type
        category = get_signal_category(signal_type)

        # Create signal
        signal = Signal(
            id=generate_id("sig"),
            signal_type=signal_type,
            signal_category=category,
            valence=valence,
            magnitude=magnitude,
            entity_type=entity_type,
            entity_id=entity_id,
            scope_task_id=scope_task_id,
            scope_project_id=scope_project_id,
            scope_retainer_id=scope_retainer_id,
            scope_brand_id=scope_brand_id,
            scope_client_id=scope_client_id,
            scope_person_id=scope_person_id,
            source_type=source_type,
            source_id=source_id,
            source_url=source_url,
            source_excerpt=source_excerpt,
            detection_confidence=detection_confidence,
            attribution_confidence=attribution_confidence,
            occurred_at=(occurred_at or datetime.now()).isoformat(),
            detected_at=now_iso(),
            expires_at=expires_at.isoformat() if expires_at else None,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
        )

        # Set value
        if value:
            signal.value = value

        return signal

    # =========================================================================
    # Deduplication
    # =========================================================================

    def load_existing_signals(self, signal_types: list[str] | None = None) -> None:
        """
        Load existing active signals for deduplication.

        Args:
            signal_types: Signal types to load (default: this detector's types)
        """
        types = signal_types or self.signal_types
        if not types:
            self._existing_signals = set()
            return

        placeholders = ",".join(["?" for _ in types])
        rows = self.db.fetch_all(
            f"""
            SELECT signal_type, entity_id
            FROM signals_v5
            WHERE signal_type IN ({placeholders})
              AND status = 'active'
        """,
            tuple(types),
        )

        # Create lookup keys
        self._existing_signals = {f"{row['signal_type']}:{row['entity_id']}" for row in rows}

    def signal_exists(self, signal_type: str, entity_id: str) -> bool:
        """
        Check if an active signal already exists.

        Args:
            signal_type: Type of signal
            entity_id: Entity ID

        Returns:
            True if signal exists
        """
        if self._existing_signals is None:
            self.load_existing_signals()

        key = f"{signal_type}:{entity_id}"
        return key in self._existing_signals

    def has_recent_signal(self, signal_type: str, entity_id: str, within_hours: int = 24) -> bool:
        """
        Check if a signal was detected recently.

        Args:
            signal_type: Type of signal
            entity_id: Entity ID
            within_hours: Hours to look back

        Returns:
            True if recent signal exists
        """
        row = self.db.fetch_one(
            """
            SELECT 1 FROM signals_v5
            WHERE signal_type = ?
              AND entity_id = ?
              AND detected_at > datetime('now', ?)
            LIMIT 1
        """,
            (signal_type, entity_id, f"-{within_hours} hours"),
        )

        return row is not None

    # =========================================================================
    # Scope Chain Resolution
    # =========================================================================

    def resolve_task_scope(self, task_id: str) -> dict[str, str | None]:
        """
        Resolve full scope chain from a task.

        Args:
            task_id: Task ID

        Returns:
            Dict with scope_* fields
        """
        row = self.db.fetch_one(
            """
            SELECT id, project_id, retainer_cycle_id, brand_id, client_id, assignee_id
            FROM tasks_v5
            WHERE id = ?
        """,
            (task_id,),
        )

        if not row:
            return {
                "task_id": task_id,
                "project_id": None,
                "retainer_id": None,
                "brand_id": None,
                "client_id": None,
                "person_id": None,
            }

        return {
            "task_id": task_id,
            "project_id": row["project_id"],
            "retainer_id": row["retainer_cycle_id"],
            "brand_id": row["brand_id"],
            "client_id": row["client_id"],
            "person_id": row["assignee_id"],
        }

    def resolve_project_scope(self, project_id: str) -> dict[str, str | None]:
        """
        Resolve scope chain from a project.

        Args:
            project_id: Project ID

        Returns:
            Dict with scope_* fields
        """
        row = self.db.fetch_one(
            """
            SELECT id, brand_id, client_id
            FROM projects_v5
            WHERE id = ?
        """,
            (project_id,),
        )

        if not row:
            return {
                "project_id": project_id,
                "brand_id": None,
                "client_id": None,
            }

        return {
            "project_id": project_id,
            "brand_id": row["brand_id"],
            "client_id": row["client_id"],
        }

    def resolve_invoice_scope(self, invoice_id: str) -> dict[str, str | None]:
        """
        Resolve scope chain from an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            Dict with scope_* fields
        """
        row = self.db.fetch_one(
            """
            SELECT id, project_id, retainer_cycle_id, client_id
            FROM xero_invoices
            WHERE id = ?
        """,
            (invoice_id,),
        )

        if not row:
            return {
                "project_id": None,
                "retainer_id": None,
                "client_id": None,
            }

        # Get brand from project or retainer
        brand_id = None
        if row["project_id"]:
            proj = self.db.fetch_one(
                "SELECT brand_id FROM projects_v5 WHERE id = ?", (row["project_id"],)
            )
            if proj:
                brand_id = proj["brand_id"]

        return {
            "project_id": row["project_id"],
            "retainer_id": row["retainer_cycle_id"],
            "brand_id": brand_id,
            "client_id": row["client_id"],
        }

    def resolve_space_scope(self, space_id: str) -> dict[str, str | None]:
        """
        Resolve scope chain from a chat space.

        Args:
            space_id: Space ID

        Returns:
            Dict with scope_* fields
        """
        row = self.db.fetch_one(
            """
            SELECT space_id, client_id, brand_id, project_id
            FROM gchat_sync_state
            WHERE space_id = ?
        """,
            (space_id,),
        )

        if not row:
            return {
                "project_id": None,
                "brand_id": None,
                "client_id": None,
            }

        return {
            "project_id": row["project_id"],
            "brand_id": row["brand_id"],
            "client_id": row["client_id"],
        }

    # =========================================================================
    # Magnitude Helpers
    # =========================================================================

    @staticmethod
    def scale_magnitude(
        value: float,
        min_val: float,
        max_val: float,
        min_mag: float = 0.3,
        max_mag: float = 1.0,
    ) -> float:
        """
        Scale a value to a magnitude range.

        Args:
            value: Value to scale
            min_val: Minimum input value
            max_val: Maximum input value
            min_mag: Minimum output magnitude
            max_mag: Maximum output magnitude

        Returns:
            Scaled magnitude (clamped to min_mag-max_mag)
        """
        if max_val <= min_val:
            return min_mag

        ratio = (value - min_val) / (max_val - min_val)
        ratio = max(0.0, min(1.0, ratio))  # Clamp to 0-1

        return min_mag + ratio * (max_mag - min_mag)

    @staticmethod
    def overdue_magnitude(days: int) -> float:
        """
        Calculate magnitude for overdue days.

        1-3 days: 0.3
        4-7 days: 0.5
        8-14 days: 0.7
        15-30 days: 0.85
        31+ days: 1.0
        """
        if days <= 0:
            return 0.0
        if days <= 3:
            return 0.3
        if days <= 7:
            return 0.5
        if days <= 14:
            return 0.7
        if days <= 30:
            return 0.85
        return 1.0

    @staticmethod
    def amount_magnitude(amount: float) -> float:
        """
        Calculate magnitude based on monetary amount.

        < 5,000: 0.3
        5,000 - 20,000: 0.5
        20,000 - 50,000: 0.7
        50,000 - 100,000: 0.85
        100,000+: 1.0
        """
        if amount < 5000:
            return 0.3
        if amount < 20000:
            return 0.5
        if amount < 50000:
            return 0.7
        if amount < 100000:
            return 0.85
        return 1.0

    # =========================================================================
    # Logging
    # =========================================================================

    def log_detection_start(self) -> None:
        """Log start of detection."""
        logger.info(f"[{self.detector_id}] Starting detection (v{self.detector_version})")

    def log_detection_end(self, count: int) -> None:
        """Log end of detection with count."""
        logger.info(f"[{self.detector_id}] Detected {count} signals")

    def log_signal(self, signal: Signal) -> None:
        """Log a detected signal."""
        logger.debug(
            f"[{self.detector_id}] Signal: {signal.signal_type} "
            f"valence={signal.valence} magnitude={signal.magnitude:.2f} "
            f"entity={signal.entity_type}:{signal.entity_id}"
        )
