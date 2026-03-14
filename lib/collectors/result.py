"""
Typed collector result model.

Every collector sync() must return a CollectorResult — not a plain dict.
This ensures callers can always distinguish:
  - success  (fresh data, all tables populated)
  - partial  (primary table OK, one or more secondary tables failed)
  - skipped  (sync not attempted: lock contention, disabled, etc.)
  - stale    (refresh failed but prior data exists; circuit breaker open)
  - failed   (collection failed entirely; no usable data)

The status field is the single source of truth. The `success` compatibility
field is ONLY true for SUCCESS — not for PARTIAL, STALE, or anything else.
Callers that need "did we get any data" should check status explicitly.
"""

from __future__ import annotations

import enum
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CollectorStatus(enum.Enum):
    """Collector sync outcome.

    Values are ordered by severity — higher ordinal = worse.
    """

    SUCCESS = "success"  # All data fresh, all tables populated
    PARTIAL = "partial"  # Primary table stored, one+ secondary tables failed
    SKIPPED = "skipped"  # Sync not attempted (lock held, disabled, etc.)
    STALE = "stale"  # Refresh failed; prior data retained but aging
    FAILED = "failed"  # Collection failed entirely; no new data written


@dataclass
class SecondaryTableResult:
    """Result of storing data into a single secondary table."""

    table: str
    stored: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class CollectorResult:
    """Typed result from a collector sync() cycle.

    Replaces the untyped dict that collectors previously returned.
    Includes enough metadata for monitoring, API responses, and debugging.
    """

    source: str
    status: CollectorStatus
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Counts — meaningful only when status is SUCCESS or PARTIAL
    collected: int = 0
    transformed: int = 0
    stored: int = 0

    # Timing
    duration_ms: float = 0.0

    # Error info — populated when status is FAILED, STALE, or PARTIAL
    error: str | None = None
    error_type: str | None = None  # e.g. "auth", "transport", "rate_limit", "parse", "timeout"

    # Secondary table results — populated when collector writes to multiple tables
    secondary_tables: dict[str, SecondaryTableResult] = field(default_factory=dict)

    # Metrics snapshot
    circuit_breaker_state: str | None = None
    retry_count: int = 0

    def add_secondary(self, table: str, stored: int = 0, error: str | None = None) -> None:
        """Record a secondary table write result."""
        self.secondary_tables[table] = SecondaryTableResult(table=table, stored=stored, error=error)

    @property
    def secondary_failures(self) -> list[str]:
        """Tables that failed to store."""
        return [name for name, r in self.secondary_tables.items() if not r.ok]

    @property
    def has_secondary_failures(self) -> bool:
        return len(self.secondary_failures) > 0

    def escalate_to_partial(self) -> None:
        """If there are secondary failures and status is SUCCESS, escalate to PARTIAL."""
        if self.status == CollectorStatus.SUCCESS and self.has_secondary_failures:
            self.status = CollectorStatus.PARTIAL

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses and JSON logging.

        The `success` field is ONLY true when status == SUCCESS.
        PARTIAL returns success=false because data is incomplete — callers
        must check `status` to distinguish partial from failed.
        """
        result: dict[str, Any] = {
            "source": self.source,
            "status": self.status.value,
            "success": self.status == CollectorStatus.SUCCESS,
            "timestamp": self.timestamp,
            "collected": self.collected,
            "transformed": self.transformed,
            "stored": self.stored,
            "duration_ms": self.duration_ms,
        }

        if self.error:
            result["error"] = self.error
        if self.error_type:
            result["error_type"] = self.error_type

        if self.secondary_tables:
            result["secondary_tables"] = {
                name: {"stored": r.stored, "error": r.error}
                for name, r in self.secondary_tables.items()
            }

        if self.secondary_failures:
            result["secondary_failures"] = self.secondary_failures

        if self.circuit_breaker_state:
            result["circuit_breaker_state"] = self.circuit_breaker_state

        if self.retry_count:
            result["retry_count"] = self.retry_count

        return result


def classify_error(error: BaseException) -> str:
    """Classify an exception into an error_type string for CollectorResult.

    Categories:
      auth       — credential / token / permission errors
      transport  — network connectivity, DNS, socket errors
      rate_limit — HTTP 429 or API quota exceeded
      timeout    — operation timed out
      parse      — JSON decode, data format errors
      storage    — SQLite / database errors
      unknown    — anything else

    Classification priority: type-based checks first, string fallback second.
    """
    error_str = str(error).lower()

    # Type-based classification (reliable) ---------------------------------

    # Google API errors (optional import)
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.exceptions import TransportError as AuthTransportError

        if isinstance(error, RefreshError):
            return "auth"
        if isinstance(error, AuthTransportError):
            return "transport"
    except ImportError:
        pass

    try:
        from googleapiclient.errors import HttpError

        if isinstance(error, HttpError):
            status = getattr(error, "status_code", None) or getattr(error, "resp", {}).get(
                "status", ""
            )
            status_int = int(status) if status else 0
            if status_int in (401, 403):
                return "auth"
            if status_int == 429:
                return "rate_limit"
            if status_int >= 500:
                return "transport"
            return "api_error"
    except ImportError:
        pass

    # Storage errors
    if isinstance(error, sqlite3.Error):
        return "storage"

    # Timeout (type check)
    if isinstance(error, TimeoutError):
        return "timeout"

    # Network / transport (type check)
    if isinstance(error, ConnectionError):
        return "transport"

    # OSError is a superclass of ConnectionError — only classify as transport
    # for clearly network-related subtypes, not arbitrary filesystem errors
    if isinstance(error, OSError) and not isinstance(error, (FileNotFoundError, PermissionError)):
        if any(w in error_str for w in ("connection", "network", "unreachable", "refused")):
            return "transport"

    # Parse errors (type check)
    if isinstance(error, (KeyError, TypeError)):
        return "data_error"
    if isinstance(error, ValueError):
        if "json" in error_str or "decode" in error_str:
            return "parse"
        return "data_error"

    if type(error).__name__ == "JSONDecodeError":
        return "parse"

    # String-based fallback (less reliable) --------------------------------

    if "timeout" in error_str or "timed out" in error_str:
        return "timeout"

    if "rate limit" in error_str or "quota" in error_str:
        return "rate_limit"

    if any(w in error_str for w in ("unauthorized", "forbidden", "token expired")):
        return "auth"

    return "unknown"
