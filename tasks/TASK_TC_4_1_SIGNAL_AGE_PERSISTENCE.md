# TC-4.1: Signal Age & Persistence Tracking

## Objective

Signals currently exist as snapshots — detected or not. There's no tracking of how long a signal has been active, whether it's escalating, or whether it's chronic. A signal that's been firing for 3 weeks is fundamentally different from one that appeared today, but the system treats them identically.

Add signal lifecycle tracking: first detection, current age, persistence classification, and escalation tracking.

## Dependencies

- TC-1.1 (BusinessCalendar — business days for age calculation)
- Brief 17 IW-1.1 (signal_state table — where signal lifecycle is stored)
- Brief 18 ID-4.1 (outcome tracking — signal resolution tracking)

## Deliverables

### New file: `lib/intelligence/signal_lifecycle.py`

```python
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional

class SignalPersistence(Enum):
    NEW = "new"               # first detection this cycle
    RECENT = "recent"         # 1-3 business days old
    ONGOING = "ongoing"       # 4-10 business days old
    CHRONIC = "chronic"       # 11+ business days old
    ESCALATING = "escalating" # severity increased since first detection
    RESOLVING = "resolving"   # metrics improving but still above threshold

@dataclass
class SignalLifecycle:
    """Complete lifecycle context for a signal."""
    signal_key: str
    signal_type: str
    entity_type: str
    entity_id: str
    first_detected_at: datetime
    last_detected_at: datetime
    current_severity: str           # critical/warning/watch
    initial_severity: str           # severity at first detection
    detection_count: int            # how many cycles this signal has fired
    consecutive_cycles: int         # unbroken streak of detections
    business_days_active: int       # age in business days
    calendar_days_active: int       # age in calendar days
    persistence: SignalPersistence  # classified persistence level
    escalation_history: list[dict]  # severity changes over time
    peak_severity: str              # highest severity reached
    acknowledged: bool
    acknowledged_at: Optional[datetime]

class SignalLifecycleTracker:
    """Tracks and classifies signal persistence and escalation."""

    def __init__(self, db_path: Path, calendar: BusinessCalendar): ...

    def get_lifecycle(self, signal_key: str) -> Optional[SignalLifecycle]:
        """Return full lifecycle context for a signal.
        Returns None if signal not found in signal_state.
        """

    def classify_persistence(self, signal_key: str) -> SignalPersistence:
        """Classify the signal's persistence level.
        Logic:
          - Not in signal_state → None
          - first_detected == current_cycle → NEW
          - business_days_active <= 3 → RECENT
          - current_severity > initial_severity → ESCALATING
          - metric value trending toward threshold → RESOLVING
          - business_days_active 4-10 → ONGOING
          - business_days_active > 10 → CHRONIC
        Note: ESCALATING and RESOLVING take priority over age-based classification.
        """

    def get_escalation_history(self, signal_key: str) -> list[dict]:
        """Return severity changes for a signal.
        Each entry: {
            "cycle_id": "...",
            "timestamp": "...",
            "old_severity": "watch",
            "new_severity": "warning",
            "trigger": "metric_value increased from 6 to 9"
        }
        """

    def update_lifecycle_on_detection(self, signal_key: str, current_severity: str,
                                       evidence: dict) -> SignalLifecycle:
        """Called during signal detection to update lifecycle tracking.
        Updates:
          - last_detected_at
          - detection_count += 1
          - consecutive_cycles += 1
          - severity change → append to escalation_history
        Returns updated lifecycle.
        """

    def update_lifecycle_on_clear(self, signal_key: str, resolution_type: str) -> None:
        """Called when a signal clears. Records resolution in lifecycle.
        Does NOT delete the signal_state row — marks it as cleared with resolution data.
        """

    def get_chronic_signals(self, min_business_days: int = 11) -> list[SignalLifecycle]:
        """Return all signals active for more than N business days.
        Sorted by business_days_active descending (oldest first).
        """

    def get_escalating_signals(self) -> list[SignalLifecycle]:
        """Return all signals whose severity has increased since detection.
        Sorted by most recent escalation first.
        """

    def get_signal_age_distribution(self) -> dict:
        """Distribution of active signal ages.
        Returns:
        {
            "new": 5,
            "recent": 8,
            "ongoing": 12,
            "chronic": 3,
            "escalating": 2,
            "resolving": 1,
            "total_active": 31,
            "avg_age_business_days": 6.2,
            "median_age_business_days": 4,
            "oldest_signal": { "key": "...", "age_business_days": 34 }
        }
        """
```

### Schema Updates to `signal_state`

Add columns (v34 migration, shared with AT-2.1):

```sql
ALTER TABLE signal_state ADD COLUMN first_detected_at TEXT;
ALTER TABLE signal_state ADD COLUMN detection_count INTEGER DEFAULT 1;
ALTER TABLE signal_state ADD COLUMN consecutive_cycles INTEGER DEFAULT 1;
ALTER TABLE signal_state ADD COLUMN initial_severity TEXT;
ALTER TABLE signal_state ADD COLUMN peak_severity TEXT;
ALTER TABLE signal_state ADD COLUMN escalation_history_json TEXT DEFAULT '[]';
ALTER TABLE signal_state ADD COLUMN resolved_at TEXT;
ALTER TABLE signal_state ADD COLUMN resolution_type TEXT;
```

Backfill existing rows: `first_detected_at = detected_at`, `initial_severity = severity`, `peak_severity = severity`.

### Integration with Signal Detection

In `lib/intelligence/signals.py`, after a signal is detected:

```python
# Current: just insert/update signal_state
# New: also update lifecycle
lifecycle = lifecycle_tracker.update_lifecycle_on_detection(
    signal_key=key,
    current_severity=severity,
    evidence=evidence
)
# Lifecycle persistence level feeds into signal severity escalation
if lifecycle.persistence == SignalPersistence.CHRONIC:
    # Auto-escalate chronic watch signals to warning
    if severity == "watch" and lifecycle.business_days_active > 14:
        severity = "warning"
```

### Integration with API (IA-4.1)

Signal list items include lifecycle fields:

```json
{
  "signal_key": "sig_client_overdue_tasks::client_abc",
  "persistence": "chronic",
  "business_days_active": 18,
  "detection_count": 12,
  "escalation_count": 1,
  "initial_severity": "watch",
  "current_severity": "warning"
}
```

## Validation

- New signal (first cycle) → persistence = NEW
- Signal active 2 business days → persistence = RECENT
- Signal active 7 business days → persistence = ONGOING
- Signal active 15 business days → persistence = CHRONIC
- Signal severity increased → persistence = ESCALATING (overrides age)
- Signal metrics trending down → persistence = RESOLVING (overrides age)
- Escalation history records each severity change with timestamp
- Chronic watch signal auto-escalates to warning after 14 business days
- `get_chronic_signals` returns only signals above threshold
- Signal cleared → lifecycle shows resolution, doesn't delete row
- Age calculation uses business days (weekend gap doesn't add to age)

## Estimated Effort

~200 lines
