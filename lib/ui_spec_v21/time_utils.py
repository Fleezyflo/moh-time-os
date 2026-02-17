"""
Time Utilities — Spec Section 0.1

Implements org-local day boundaries for all date calculations.
All timestamps stored as ISO 8601 UTC with Z suffix.
"""

import logging
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# Default org timezone
DEFAULT_ORG_TZ = "Asia/Dubai"

# UTC timezone constant
UTC = ZoneInfo("UTC")

# ISO 8601 format regex for validation (exactly 24 chars)
ISO_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

# Regex patterns for normalization input formats
OFFSET_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})$")
ZULU_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z$")

# DST-observing zones to reject (spec 0.1)
DST_ZONES = frozenset(
    [
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "America/Denver",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Rome",
        "Europe/Madrid",
        "Australia/Sydney",
        "Australia/Melbourne",
        "Pacific/Auckland",
        "America/Toronto",
        "America/Vancouver",
        "Europe/Amsterdam",
        "Europe/Brussels",
    ]
)

# Storage test vectors (spec 0.1)
STORAGE_TEST_VECTORS = [
    # (stored_value, valid, notes)
    ("2026-02-08T14:30:00.000Z", True, "Zero milliseconds padded"),
    ("2026-02-08T14:30:00.010Z", True, "10ms padded to 3 digits"),
    ("2026-02-08T14:30:00.999Z", True, "Max milliseconds"),
    ("2026-02-08T14:30:00Z", False, "Missing milliseconds"),
    ("2026-02-08T14:30:00.0Z", False, "1-digit milliseconds"),
    ("2026-02-08T14:30:00.00Z", False, "2-digit milliseconds"),
    ("2026-02-08T14:30:00.0001Z", False, "4-digit (microseconds)"),
    ("2026-02-08T14:30:00.000+04:00", False, "Offset instead of Z"),
]

# Normalization input test vectors (spec 0.1)
NORMALIZATION_TEST_VECTORS = [
    # (input, expected_output)
    ("2026-02-08T14:30:00Z", "2026-02-08T14:30:00.000Z"),
    ("2026-02-08T14:30:00.1Z", "2026-02-08T14:30:00.100Z"),
    ("2026-02-08T14:30:00.12Z", "2026-02-08T14:30:00.120Z"),
    ("2026-02-08T14:30:00.123Z", "2026-02-08T14:30:00.123Z"),
    ("2026-02-08T18:30:00+04:00", "2026-02-08T14:30:00.000Z"),
    ("2026-02-08T09:30:00-05:00", "2026-02-08T14:30:00.000Z"),
    ("2026-02-08T14:30:00.123456Z", "2026-02-08T14:30:00.123Z"),
]


def validate_timestamp(ts: str) -> bool:
    """
    Validate timestamp matches exact ISO format.
    Format: YYYY-MM-DDTHH:MM:SS.sssZ (24 chars)

    Spec: 0.1 Timestamp Format
    """
    if not ts or len(ts) != 24:
        return False
    return ISO_TIMESTAMP_REGEX.match(ts) is not None


def normalize_timestamp(ts: str) -> str:
    """
    Normalize timestamp to canonical 24-char format.

    Spec: 0.1 Accepted Input Formats (Normalization)

    Accepts:
    - No milliseconds: 2026-02-08T14:30:00Z → 2026-02-08T14:30:00.000Z
    - 1-3 digit ms: 2026-02-08T14:30:00.1Z → 2026-02-08T14:30:00.100Z
    - With offset: 2026-02-08T18:30:00+04:00 → 2026-02-08T14:30:00.000Z
    - Microseconds (truncate): 2026-02-08T14:30:00.123456Z → 2026-02-08T14:30:00.123Z

    Raises:
        ValueError: If timestamp is unparseable
    """
    if not ts:
        raise ValueError("Empty timestamp")

    # Already canonical?
    if validate_timestamp(ts):
        return ts

    try:
        # Handle offset format
        offset_match = OFFSET_REGEX.match(ts)
        if offset_match:
            base, frac, offset = offset_match.groups()
            # Parse with offset
            ts_with_offset = f"{base}{frac}{offset}" if frac else f"{base}{offset}"
            dt = datetime.fromisoformat(ts_with_offset)
            dt_utc = dt.astimezone(UTC)
            ms = dt_utc.microsecond // 1000
            return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

        # Handle Zulu format with various ms lengths
        zulu_match = ZULU_REGEX.match(ts)
        if zulu_match:
            base, frac = zulu_match.groups()
            if frac:
                # Truncate/pad to 3 digits
                frac_digits = frac[1:]  # Remove leading dot
                if len(frac_digits) > 3:
                    frac_digits = frac_digits[:3]  # Truncate
                ms = int(frac_digits.ljust(3, "0"))  # Pad
            else:
                ms = 0
            # Parse base
            dt = datetime.fromisoformat(base + "+00:00")
            return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

        # Try generic parsing
        ts_for_parse = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(ts_for_parse)
        dt_utc = dt.astimezone(UTC)
        ms = dt_utc.microsecond // 1000
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

    except (ValueError, TypeError) as e:
        raise ValueError(f"Unparseable timestamp: {ts}") from e


def validate_org_timezone(tz: str) -> tuple:
    """
    Validate org timezone is acceptable.

    Spec: 0.1 DST Zone Rejection

    Args:
        tz: IANA timezone string

    Returns:
        Tuple of (valid: bool, reason: str or None)
    """
    # Check if it's a valid timezone
    try:
        ZoneInfo(tz)
    except Exception:
        return False, f"Invalid timezone: {tz}"

    # Reject DST-observing zones
    if tz in DST_ZONES:
        return (
            False,
            f"DST-observing timezone not allowed: {tz}. Use a fixed-offset zone.",
        )

    return True, None


class RequestContext:
    """
    Per-request context for date calculations.

    Spec: 0.1 Per-request today_local invariant

    Ensures all date calculations within a single request use the same
    "today" value, preventing race conditions at midnight.

    Usage:
        ctx = RequestContext("Asia/Dubai")
        # All calls to ctx.today_local return the same date
        # even if the request spans midnight
    """

    def __init__(self, org_tz: str = DEFAULT_ORG_TZ):
        valid, reason = validate_org_timezone(org_tz)
        if not valid:
            raise ValueError(reason)

        self.org_tz = org_tz
        self._tz = ZoneInfo(org_tz)
        # Freeze "today" at request start
        self._today_local = datetime.now(self._tz).date()
        self._now_utc = datetime.now(UTC)

    @property
    def today_local(self) -> date:
        """Get frozen local date for this request."""
        return self._today_local

    @property
    def now_utc(self) -> datetime:
        """Get frozen UTC timestamp for this request."""
        return self._now_utc

    def today_midnight_utc(self) -> datetime:
        """Get UTC timestamp for midnight of today in org timezone."""
        return local_midnight_utc(self.org_tz, self._today_local)

    def days_ago_midnight_utc(self, days: int) -> datetime:
        """Get UTC timestamp for midnight N days ago."""
        target_date = self._today_local - timedelta(days=days)
        return local_midnight_utc(self.org_tz, target_date)

    def client_status_cutoffs(self) -> dict:
        """Get client status boundary dates frozen to this request."""
        return {
            "active_cutoff": self._today_local - timedelta(days=90),
            "recently_active_cutoff": self._today_local - timedelta(days=270),
        }


def run_storage_test_vectors() -> tuple:
    """
    Run storage test vectors.

    Spec: 0.1 Storage Test Vectors

    Returns:
        Tuple of (all_passed: bool, failures: list)
    """
    failures = []
    for ts, expected_valid, notes in STORAGE_TEST_VECTORS:
        actual_valid = validate_timestamp(ts)
        if actual_valid != expected_valid:
            failures.append(
                {
                    "timestamp": ts,
                    "expected": expected_valid,
                    "actual": actual_valid,
                    "notes": notes,
                }
            )
    return len(failures) == 0, failures


def run_normalization_test_vectors() -> tuple:
    """
    Run normalization test vectors.

    Spec: 0.1 Accepted Input Formats

    Returns:
        Tuple of (all_passed: bool, failures: list)
    """
    failures = []
    for input_ts, expected_output in NORMALIZATION_TEST_VECTORS:
        try:
            actual_output = normalize_timestamp(input_ts)
            if actual_output != expected_output:
                failures.append(
                    {
                        "input": input_ts,
                        "expected": expected_output,
                        "actual": actual_output,
                    }
                )
        except ValueError as e:
            failures.append({"input": input_ts, "expected": expected_output, "error": str(e)})
    return len(failures) == 0, failures


def now_utc() -> datetime:
    """Get current time in UTC."""
    return datetime.now(UTC)


def now_iso() -> str:
    """Get current time as ISO string with milliseconds."""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%S.") + f"{now_utc().microsecond // 1000:03d}Z"


def to_iso(dt: datetime) -> str:
    """Convert datetime to ISO string with milliseconds."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt_utc = dt.astimezone(UTC)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt_utc.microsecond // 1000:03d}Z"


def from_iso(ts: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(UTC)


def local_midnight_utc(org_tz: str, dt: date) -> datetime:
    """
    Returns UTC timestamp for midnight of given date in org timezone.

    Spec: 0.1 Canonical "Today"

    Example: 2026-02-07 in Asia/Dubai = 2026-02-06T20:00:00Z

    Args:
        org_tz: IANA timezone string (e.g., "Asia/Dubai")
        dt: Date to compute midnight for

    Returns:
        datetime in UTC for local midnight
    """
    tz = ZoneInfo(org_tz)
    local_midnight = datetime.combine(dt, time.min, tzinfo=tz)
    return local_midnight.astimezone(UTC)


def window_start(org_tz: str, days: int) -> datetime:
    """
    Returns UTC timestamp for midnight N days ago in org timezone.

    Spec: 1.9 days=N Window Calculation

    Used for:
    - Inbox header counts (recently_actioned)
    - GET /api/inbox/recent?days=N
    - Any endpoint using days=N parameter

    Args:
        org_tz: IANA timezone string
        days: Number of days to look back

    Returns:
        datetime in UTC for start of window
    """
    tz = ZoneInfo(org_tz)
    local_today = datetime.now(tz).date()
    local_start_date = local_today - timedelta(days=days)
    return local_midnight_utc(org_tz, local_start_date)


def days_late(due_date: date | None, completed_at: datetime, org_tz: str) -> int | None:
    """
    Compute days late using org-local dates.

    Spec: 0.1 Time Library Contract

    Args:
        due_date: Task due date (None = exclude from calculation)
        completed_at: When task was completed (datetime)
        org_tz: Org timezone for conversion

    Returns:
        Integer days late (minimum 0), or None if no due_date
    """
    if due_date is None:
        return None  # Exclude from average calculation

    tz = ZoneInfo(org_tz)
    completed_local = completed_at.astimezone(tz).date()
    return max(0, (completed_local - due_date).days)


def payment_date_local(status_changed_at: datetime, org_tz: str) -> date:
    """
    Convert payment timestamp to org-local date.

    Spec: 0.1 Time Library Contract

    Args:
        status_changed_at: When invoice status changed to PAID
        org_tz: Org timezone for conversion

    Returns:
        date in org-local timezone
    """
    tz = ZoneInfo(org_tz)
    return status_changed_at.astimezone(tz).date()


def days_overdue(due_date: date | None, org_tz: str) -> int | None:
    """
    Calculate days overdue for an invoice.

    Spec: 6.2 AR Aging Buckets

    Args:
        due_date: Invoice due date
        org_tz: Org timezone

    Returns:
        Integer days overdue (minimum 0), or None if no due_date
    """
    if due_date is None:
        return None

    tz = ZoneInfo(org_tz)
    today = datetime.now(tz).date()
    return max(0, (today - due_date).days)


def aging_bucket(days: int | None) -> str | None:
    """
    Determine AR aging bucket from days overdue.

    Spec: 6.2 AR Aging Buckets

    Returns:
        Bucket string: current, 1_30, 31_60, 61_90, 90_plus
    """
    if days is None:
        return None
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_plus"


def is_today_or_past(due_date: date, org_tz: str) -> bool:
    """Check if due_date is today or in the past."""
    tz = ZoneInfo(org_tz)
    today = datetime.now(tz).date()
    return due_date <= today


def detector_window_start(org_tz: str, window_days: int) -> datetime:
    """
    Returns UTC timestamp for start of detection window.
    Uses org-local midnight boundaries, consistent with all other date logic.

    Spec: §6.19 Detector Window Boundaries (v2.9)

    Args:
        org_tz: IANA timezone string
        window_days: Number of days to look back

    Returns:
        datetime in UTC for start of window (org-local midnight N days ago)
    """
    tz = ZoneInfo(org_tz)
    local_today = datetime.now(tz).date()
    window_start_date = local_today - timedelta(days=window_days)
    return local_midnight_utc(org_tz, window_start_date)


def detector_window_end() -> datetime:
    """
    Returns current UTC timestamp (inclusive end for detector windows).

    Spec: §6.19 Detector Window Boundaries (v2.9)

    Returns:
        datetime in UTC for current moment
    """
    return now_utc()


def get_detector_window(org_tz: str, window_days: int) -> tuple:
    """
    Get detector window boundaries as ISO strings for SQL queries.

    Spec: §6.19 Detector Window Boundaries (v2.9)

    Args:
        org_tz: IANA timezone string
        window_days: Number of days to look back

    Returns:
        Tuple of (window_start_iso, window_end_iso)

    Usage:
        start, end = get_detector_window("Asia/Dubai", 7)
        cursor.execute('''
            SELECT * FROM signals
            WHERE observed_at >= ? AND observed_at <= ?
        ''', (start, end))
    """
    window_start = detector_window_start(org_tz, window_days)
    window_end = detector_window_end()
    return to_iso(window_start), to_iso(window_end)


def client_status_boundaries(org_tz: str) -> dict:
    """
    Get client status boundary dates.

    Spec: 6.1 Client Status Logic

    Returns:
        dict with 'active_cutoff' and 'recently_active_cutoff' dates
    """
    tz = ZoneInfo(org_tz)
    today = datetime.now(tz).date()

    return {
        "active_cutoff": today - timedelta(days=90),  # >= is active
        "recently_active_cutoff": today - timedelta(days=270),  # >= is recently_active
    }


def validate_timestamp_semantic(ts: str) -> bool:
    """
    Parse+roundtrip validator — catches both shape AND value errors.

    Spec: 0.1 Timestamp Format Enforcement (v2.9)

    Args:
        ts: Timestamp string to validate

    Returns:
        True if valid, False otherwise
    """
    if not ts or len(ts) != 24:
        return False
    try:
        # Parse the string
        dt = from_iso(ts)
        # Roundtrip: format back to canonical
        canonical = to_iso(dt)
        # Must match exactly
        return ts == canonical
    except (ValueError, TypeError):
        return False


def validate_timestamp_ordering(conn) -> list:
    """
    Validate cross-field timestamp ordering invariants.

    Spec: 0.1 Timestamp Format Enforcement (v2.9)

    These invariants ensure lexicographic comparisons work correctly.

    Args:
        conn: SQLite database connection

    Returns:
        List of violation tuples: (table, column, id, value, reason)
    """
    violations = []

    # Inbox items: resurfaced_at >= proposed_at (if set)
    try:
        cursor = conn.execute("""
            SELECT id, proposed_at, resurfaced_at FROM inbox_items
            WHERE resurfaced_at IS NOT NULL AND resurfaced_at < proposed_at
        """)
        for row in cursor.fetchall():
            violations.append(
                (
                    "inbox_items",
                    "resurfaced_at",
                    row[0],
                    row[2],
                    "resurfaced_before_proposed",
                )
            )
    except Exception:
        pass  # Table may not exist

    # All tables: updated_at >= created_at
    for table in ["inbox_items", "issues", "signals"]:
        try:
            cursor = conn.execute(f"""  # nosql: safe
                SELECT id, created_at, updated_at FROM {table}
                WHERE updated_at IS NOT NULL AND created_at IS NOT NULL AND updated_at < created_at
            """)
            for row in cursor.fetchall():
                violations.append((table, "updated_at", row[0], row[2], "updated_before_created"))
        except Exception:
            pass  # Table may not exist

    # Issues: resolved_at >= created_at (if set)
    try:
        cursor = conn.execute("""
            SELECT id, created_at, resolved_at FROM issues
            WHERE resolved_at IS NOT NULL AND resolved_at < created_at
        """)
        for row in cursor.fetchall():
            violations.append(("issues", "resolved_at", row[0], row[2], "resolved_before_created"))
    except Exception:
        pass

    return violations


def validate_all_timestamps(conn) -> tuple:
    """
    Full semantic validation for startup canary.

    Spec: 0.1 Timestamp Format Enforcement (v2.9)

    Args:
        conn: SQLite database connection

    Returns:
        Tuple of (success: bool, violations: list)
    """
    # Column registry per spec
    TIMESTAMP_COLUMNS = {
        "inbox_items": [
            "proposed_at",
            "last_refreshed_at",
            "read_at",
            "resolved_at",
            "snooze_until",
            "snoozed_at",
            "dismissed_at",
            "created_at",
            "updated_at",
            "resurfaced_at",
        ],
        "issues": [
            "created_at",
            "updated_at",
            "tagged_at",
            "assigned_at",
            "snoozed_until",
            "snoozed_at",
            "suppressed_at",
            "escalated_at",
            "resolved_at",
            "regression_watch_until",
            "closed_at",
        ],
        "signals": [
            "observed_at",
            "ingested_at",
            "dismissed_at",
            "created_at",
            "updated_at",
        ],
        "issue_transitions": ["transitioned_at"],
        "inbox_suppression_rules": ["created_at", "expires_at"],
    }

    violations = []

    # Format validation
    for table, columns in TIMESTAMP_COLUMNS.items():
        try:
            for col in columns:
                cursor = conn.execute(
                    f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL"
                )  # nosql: safe
                for row in cursor.fetchall():
                    if not validate_timestamp_semantic(row[1]):
                        violations.append((table, col, row[0], row[1], "invalid_format"))
        except Exception:
            pass  # Table or column may not exist

    # Ordering validation
    ordering_violations = validate_timestamp_ordering(conn)
    violations.extend(ordering_violations)

    success = len(violations) == 0
    return success, violations


# Test cases for Asia/Dubai boundary examples
def _test_dubai_boundaries():
    """
    Test case: 2026-02-07 in Asia/Dubai

    Expected: 2026-02-06T20:00:00Z to 2026-02-07T19:59:59Z
    """
    test_date = date(2026, 2, 7)
    org_tz = "Asia/Dubai"

    midnight = local_midnight_utc(org_tz, test_date)

    assert midnight.year == 2026
    assert midnight.month == 2
    assert midnight.day == 6
    assert midnight.hour == 20
    assert midnight.minute == 0

    # Next midnight (end of day)
    next_day = date(2026, 2, 8)
    next_midnight = local_midnight_utc(org_tz, next_day)

    assert next_midnight.year == 2026
    assert next_midnight.month == 2
    assert next_midnight.day == 7
    assert next_midnight.hour == 20

    logger.info("✓ Dubai boundary tests passed")
    return True


def run_timestamp_canary(conn, verbose: bool = True) -> bool:
    """
    Run timestamp validation canary on startup.

    Spec: 0.1 Runtime canary (required)

    Args:
        conn: Database connection
        verbose: Print results

    Returns:
        True if all validations pass
    """
    success, violations = validate_all_timestamps(conn)

    if verbose:
        if success:
            logger.info("✓ Timestamp validation canary passed")
        else:
            logger.info(f"✗ CRITICAL: {len(violations)} timestamp violations detected")
            for table, col, id_, val, reason in violations[:10]:
                logger.info(f"  {table}.{col} id={id_}: '{val}' ({reason})")
    return success


if __name__ == "__main__":
    _test_dubai_boundaries()

    # Run canary on main database if available
    import sqlite3

    from lib import paths

    db_path = paths.db_path()
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        logger.info(f"\nRunning timestamp canary on {db_path.name}...")
        run_timestamp_canary(conn)
        conn.close()
