"""
Typed result types for data operations.

Every function that can fail should return a typed result instead of bare
``[]`` or ``{}``.  This ensures callers can always distinguish "no data"
from "operation failed."

The pattern mirrors ``lib/collectors/result.py`` (proven in production)
but is simpler — no collector-specific fields.

Usage::

    from lib.common.result_types import DataResult, ResultStatus

    def get_items(db) -> DataResult[list[Item]]:
        try:
            items = db.execute("SELECT ...").fetchall()
            return DataResult.ok(items)
        except sqlite3.Error as e:
            logger.error("get_items failed: %s", e, exc_info=True)
            return DataResult.fail(str(e), error_type="storage")
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResultStatus(enum.Enum):
    """Outcome of a data operation."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class DataResult(Generic[T]):
    """Typed result from any data operation.

    Attributes:
        status: SUCCESS or FAILED.
        data: The payload on success, ``None`` on failure.
        error: Human-readable error message (only on failure).
        error_type: Machine-readable category (e.g. "storage", "auth").
    """

    status: ResultStatus
    data: T | None = field(default=None)
    error: str | None = field(default=None)
    error_type: str | None = field(default=None)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def ok(cls, data: T) -> DataResult[T]:
        """Create a successful result with data."""
        return cls(status=ResultStatus.SUCCESS, data=data)

    @classmethod
    def fail(
        cls,
        error: str,
        error_type: str | None = None,
    ) -> DataResult[T]:
        """Create a failed result with an error message."""
        return cls(
            status=ResultStatus.FAILED,
            data=None,
            error=error,
            error_type=error_type,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def succeeded(self) -> bool:
        """True when the operation succeeded."""
        return self.status == ResultStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """True when the operation failed."""
        return self.status == ResultStatus.FAILED

    def __bool__(self) -> bool:
        """Truthy when the operation succeeded.

        This allows idiomatic ``if result:`` checks while still forcing
        callers to access ``.data`` explicitly for the payload.
        """
        return self.succeeded
