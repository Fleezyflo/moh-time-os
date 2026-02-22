# AT-4.1: Calibration Reporting

## Objective

Make calibration transparent. Molham should be able to see what thresholds changed, why, and what effect it had. Calibration without visibility is a black box — and Molham needs to trust the system's self-tuning.

## Dependencies

- AT-1.1 (effectiveness scores — the "why")
- AT-2.1 (calibration engine — the "what changed")
- AT-3.1 (seasonal modifiers — context for adjustments)
- Brief 28 IO-1.1 (audit trail — stores calibration events)

## Deliverables

### New file: `lib/intelligence/calibration_report.py`

```python
class CalibrationReporter:
    """Generates calibration reports for transparency and review."""

    def __init__(self, db_path: Path): ...

    def generate_weekly_report(self, week_of: date = None) -> dict:
        """Generate the weekly calibration summary.
        Returns:
        {
            "week_of": "2026-02-16",
            "calibration_ran": true,
            "adjustments_applied": 3,
            "adjustments_skipped": 2,
            "adjustments": [
                {
                    "signal_type": "client_overdue_tasks",
                    "direction": "raised",
                    "old_threshold": 5,
                    "new_threshold": 7,
                    "reason": "Only 15% of fires were acted on (87 fires, 13 actions in 90 days)",
                    "expected_impact": "~35% fewer false alarms for overdue task signals",
                    "confidence": "high"
                }
            ],
            "skipped": [
                {
                    "signal_type": "invoice_aging",
                    "reason": "insufficient_data",
                    "detail": "Only 8 fires in 90 days (minimum: 20)"
                }
            ],
            "active_seasonal_modifiers": ["ramadan_2026"],
            "signals_excluded_from_analysis": 12,
            "next_calibration": "2026-02-23T05:00:00"
        }
        """

    def generate_effectiveness_report(self, days: int = 90) -> dict:
        """Signal effectiveness overview across all signal types.
        Returns:
        {
            "period_days": 90,
            "total_signal_types": 14,
            "summary": {
                "well_calibrated": 6,    # effectiveness > 0.7
                "needs_review": 4,       # effectiveness 0.4-0.7
                "too_noisy": 3,          # effectiveness < 0.4
                "insufficient_data": 1
            },
            "noisiest_signals": [
                {
                    "signal_type": "client_overdue_tasks",
                    "effectiveness": 0.28,
                    "action_rate": 0.15,
                    "fires": 87,
                    "recommendation": "raise_threshold"
                }
            ],
            "most_effective_signals": [
                {
                    "signal_type": "payment_overdue_critical",
                    "effectiveness": 0.92,
                    "action_rate": 0.95,
                    "fires": 23,
                    "recommendation": "maintain"
                }
            ],
            "overall_signal_accuracy": 0.58,  # weighted avg effectiveness
            "trend_vs_last_period": "+0.04"   # improving
        }
        """

    def generate_calibration_history(self, months: int = 6) -> dict:
        """Historical view of all calibrations.
        Returns:
        {
            "period_months": 6,
            "total_calibrations": 24,
            "total_adjustments": 47,
            "by_signal_type": {
                "client_overdue_tasks": {
                    "adjustments": 3,
                    "net_direction": "raised",
                    "original_threshold": 5,
                    "current_threshold": 7,
                    "total_change_pct": 0.40,
                    "oscillations": 0
                }
            },
            "rollbacks": 1,
            "system_health": "calibrating"  # calibrating | stable | oscillating
        }
        """

    def format_for_briefing(self, report: dict) -> str:
        """Format a calibration report as human-readable text for the daily briefing.
        Example output:
        'This week: raised overdue task threshold from 5→7 (only 15% acted on).
         3 signals well-calibrated, 4 need review. Overall accuracy: 58% (+4% vs last period).'
        """
```

### Integration Points

1. **Daily Briefing (PI-4.1):** `format_for_briefing()` provides the calibration section
2. **Intelligence API (IA-1.1):** New endpoint `GET /api/v3/intelligence/calibration/report` returns weekly report
3. **Notifications (Brief 21):** Weekly calibration summary as a non-critical notification
4. **Explainer (IO-2.1):** Calibration context included in signal explanations ("threshold was recently raised from 5 to 7")

### API Endpoint

```
GET /api/v3/intelligence/calibration/report
Query params: type (weekly|effectiveness|history), week_of, days, months

GET /api/v3/intelligence/calibration/history/{signal_type}
Returns calibration history for a specific signal type
```

## Validation

- Weekly report includes all adjustments from calibration_log
- Skipped adjustments include reason
- Effectiveness report aggregations match individual scores
- History correctly computes net direction and total change
- format_for_briefing produces readable, concise output
- Reports handle empty data gracefully (no calibrations yet → "No calibrations performed. Building baseline data.")
- Seasonal exclusions are counted and reported

## Estimated Effort

~200 lines
