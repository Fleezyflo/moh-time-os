"""
Canonical Time Policy for MOH TIME OS.

ALL code must use this module for timestamp generation. No direct datetime.now(),
datetime.utcnow(), or datetime.today() calls elsewhere.

Policy:
- Storage format: ISO 8601 UTC with 3-digit milliseconds and Z suffix
  Example: 2026-02-08T14:30:00.123Z (exactly 24 chars)
- Internal datetime objects: Always timezone-aware UTC
- Local time: Only for display, via org_tz conversion
- Naive datetimes: Rejected at boundaries; assumed UTC if encountered in legacy code

This module re-exports the canonical helpers from lib.ui_spec_v21.time_utils
and provides a thin, import-friendly API for the rest of the codebase.
"""

from datetime import datetime, timezone

from lib.ui_spec_v21.time_utils import (
    UTC,
    from_iso,
    normalize_timestamp,
    now_iso,
    now_utc,
    to_iso,
    validate_timestamp,
)

__all__ = [
    "UTC",
    "from_iso",
    "normalize_timestamp",
    "now_iso",
    "now_utc",
    "to_iso",
    "validate_timestamp",
    "ensure_aware",
]


def ensure_aware(dt: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware (UTC).

    If the datetime is naive, it is assumed to be UTC and tagged accordingly.
    If it's already aware, it's converted to UTC.

    This is a migration helper for legacy code that produces naive datetimes.
    New code should always produce aware datetimes via now_utc().
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
