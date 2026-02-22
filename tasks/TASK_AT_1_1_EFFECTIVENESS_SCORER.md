# AT-1.1: Signal Effectiveness Scorer

## Objective

Score how effective each signal type is by analyzing decision journal entries. A signal is effective if it gets acted on. A signal is noise if it gets dismissed.

## Dependencies

- Brief 22 SM-1.1 (decision journal must exist)
- Brief 18 ID-4.1 (outcome tracking — signal outcomes table)

## Deliverables

### New file: `lib/intelligence/effectiveness.py`

```python
class SignalEffectivenessScorer:
    """Scores signal effectiveness based on user response patterns."""

    def __init__(self, db_path: Path): ...

    def score_signal_type(self, signal_type: str, days: int = 90) -> dict:
        """Score effectiveness for a signal type.
        Returns:
        {
            "signal_type": "client_overdue_tasks",
            "period_days": 90,
            "total_fires": 45,
            "acted_on": 12,
            "dismissed": 28,
            "expired_unseen": 5,
            "action_rate": 0.27,       # acted_on / (acted_on + dismissed)
            "effectiveness": 0.35,     # weighted score considering outcomes
            "avg_response_time_hours": 4.2,
            "health_improvement_rate": 0.6,  # % of acted signals that improved health
            "recommendation": "raise_threshold",  # raise_threshold | maintain | lower_threshold
            "suggested_new_threshold": 7     # current is 5
        }
        """

    def score_all_signal_types(self, days: int = 90) -> list[dict]:
        """Score all signal types, sorted by effectiveness (worst first)."""

    def get_effectiveness_summary(self) -> dict:
        """Portfolio-level: overall signal accuracy, noisiest signals, most effective signals."""
```

### Effectiveness formula

```
effectiveness = (0.5 × action_rate) + (0.3 × health_improvement_rate) + (0.2 × timeliness_factor)

where:
  action_rate = acted_on / (acted_on + dismissed)  # ignoring expired
  health_improvement_rate = signals where health improved / signals acted on
  timeliness_factor = 1.0 - (avg_response_hours / 72)  # decays over 3 days
```

### Recommendation logic

```
effectiveness > 0.7  → "maintain" (well-calibrated)
effectiveness 0.4-0.7 → "review" (may need adjustment)
effectiveness < 0.4  → "raise_threshold" (too noisy)
action_rate > 0.9    → "lower_threshold" (catching real issues, maybe missing some)
```

### Threshold suggestion

For "raise_threshold": suggest new threshold = current × (1 + (1 - action_rate) × 0.3)
For "lower_threshold": suggest new threshold = current × 0.85
Cap: never adjust more than ±30% from current value.

## Data Sources

- `decision_log` (from SM-1.1) — user actions on signals
- `signal_outcomes` (from ID-4.1) — signal lifecycle and health impact
- `signal_state` — current and historical signal states
- `score_history` — health before/after signal lifecycle

## Validation

- High-dismiss signal gets low effectiveness score
- High-action signal gets high effectiveness score
- Health improvement rate computed correctly
- Threshold suggestion stays within ±30% cap
- Signal with no journal entries returns "insufficient data"
- score_all returns sorted list

## Estimated Effort

~250 lines
