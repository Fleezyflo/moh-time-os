# AT-2.1: Threshold Adjustment Engine

## Objective

Automatically adjust signal thresholds based on effectiveness scores. This is the core calibration engine that reads effectiveness data from AT-1.1 and writes updated thresholds back to the system.

## Dependencies

- AT-1.1 (effectiveness scores provide the input)
- Brief 17 IW-1.1 (thresholds.yaml — the configuration being adjusted)
- Brief 22 SM-1.1 (decision journal — source of user response data)

## Deliverables

### New file: `lib/intelligence/calibration.py`

```python
class ThresholdCalibrator:
    """Adjusts signal thresholds based on effectiveness analysis."""

    def __init__(self, db_path: Path, thresholds_path: Path): ...

    def propose_adjustments(self, days: int = 90) -> list[dict]:
        """Generate proposed threshold adjustments without applying them.
        Returns:
        [
            {
                "signal_type": "client_overdue_tasks",
                "current_threshold": 5,
                "proposed_threshold": 7,
                "adjustment_pct": 0.40,  # +40% (will be capped to +30%)
                "capped_threshold": 6.5,  # after ±30% cap
                "final_threshold": 7,     # rounded to nearest integer
                "reason": "raise_threshold",
                "effectiveness": 0.28,
                "action_rate": 0.15,
                "evidence": {
                    "total_fires": 87,
                    "acted_on": 13,
                    "dismissed": 74,
                    "period_days": 90
                },
                "confidence": "high"  # high (>50 fires), medium (20-50), low (<20)
            }
        ]
        """

    def apply_adjustments(self, adjustments: list[dict], dry_run: bool = True) -> dict:
        """Apply proposed adjustments to thresholds.yaml.
        Returns:
        {
            "applied": 4,
            "skipped": 1,
            "skipped_reasons": [
                {"signal_type": "x", "reason": "low_confidence", "fires": 8}
            ],
            "backup_path": "thresholds.yaml.bak.2026-02-21",
            "dry_run": true,
            "changes": [...]
        }
        """

    def get_calibration_history(self, signal_type: str = None) -> list[dict]:
        """Return history of past calibrations from calibration_log table."""

    def rollback_last_calibration(self) -> dict:
        """Restore thresholds from the most recent backup.
        Returns the backup that was restored and the current that was replaced.
        """
```

### Safety Rules

1. **Cap:** No single adjustment exceeds ±30% of the current value
2. **Minimum data:** Skip adjustment if fewer than 20 signal fires in the period
3. **Backup:** Always write `thresholds.yaml.bak.{date}` before modifying
4. **Dry run default:** `apply_adjustments` defaults to `dry_run=True`
5. **No cascading:** Only adjust one threshold per signal type per calibration cycle
6. **Cooldown:** Don't re-adjust a threshold that was adjusted in the last 14 days
7. **Direction consistency:** If last 2 adjustments went in opposite directions, skip (oscillation detection)
8. **Rollback available:** Always keep the previous backup for manual recovery

### Threshold Modification Strategy

```
For numeric thresholds (e.g., overdue_tasks >= 5):
  raise: new_value = current × (1 + adjustment_factor)
  lower: new_value = current × 0.85
  Round to nearest integer for count-based thresholds
  Round to 1 decimal for percentage-based thresholds

For duration thresholds (e.g., invoice_aging >= 45 days):
  Same formula but round to nearest 5 (days) or 1 (hours)

For compound thresholds (multiple conditions):
  Adjust only the primary condition
  Log which condition was adjusted
```

### New table: `calibration_log` (v34 migration)

```sql
CREATE TABLE calibration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calibrated_at TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    previous_threshold REAL NOT NULL,
    new_threshold REAL NOT NULL,
    adjustment_pct REAL NOT NULL,
    effectiveness_score REAL NOT NULL,
    action_rate REAL NOT NULL,
    fires_in_period INTEGER NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,
    backup_path TEXT,
    rolled_back INTEGER DEFAULT 0
);
```

### Integration with Daemon

Calibration runs as a **weekly sub-step** (not every cycle):
- Condition: `datetime.now().weekday() == 0 and hour == 5` (Monday 5 AM)
- Or triggered manually via CLI: `python -m moh_time_os.cli calibrate --dry-run`
- On first run: report only, no adjustments (build baseline)

## Validation

- Propose adjustments returns correct direction for known effectiveness scores
- ±30% cap is enforced (verify with effectiveness=0.05 which would suggest large raise)
- Cooldown period is respected (no re-adjustment within 14 days)
- Oscillation detection works (skip after 2 opposite adjustments)
- Dry run makes no file changes
- Backup is created before any live adjustment
- Rollback restores the correct previous state
- Low-confidence adjustments (< 20 fires) are skipped
- calibration_log is populated correctly

## Estimated Effort

~300 lines
