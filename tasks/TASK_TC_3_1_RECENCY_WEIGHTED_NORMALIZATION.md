# TC-3.1: Recency-Weighted Score Normalization

## Objective

Score normalization currently treats all historical data equally. A 90-day-old data point carries the same weight as yesterday's. This distorts trend analysis and makes the system slow to react to recent changes while over-weighting stale data.

Implement recency weighting with configurable half-life so recent data has more influence on normalized scores and trends.

## Dependencies

- TC-1.1 (BusinessCalendar — for business-day-aware decay)
- Brief 17 IW-1.1 (score_history table — the data being normalized)
- `lib/intelligence/scoring.py` (existing normalization functions)

## Deliverables

### Add to `lib/intelligence/temporal.py` (RecencyWeighter class)

```python
import math

class RecencyWeighter:
    """Applies exponential decay weighting to temporal data series."""

    def __init__(self, calendar: BusinessCalendar, half_life_days: int = 14):
        """
        half_life_days: number of business days after which a data point
        has half the weight of today's data. Default: 14 business days (~3 calendar weeks).
        """

    def compute_weight(self, data_date: date, reference_date: date = None) -> float:
        """Compute decay weight for a single data point.
        Formula: weight = 2^(-business_days_ago / half_life_days)

        Examples (half_life=14):
          Today: 1.0
          7 business days ago: 0.707
          14 business days ago: 0.5
          28 business days ago: 0.25
          56 business days ago: 0.0625
        """

    def weighted_average(self, data_points: list[tuple[date, float]]) -> float:
        """Compute recency-weighted average of (date, value) pairs.
        Formula: Σ(value × weight) / Σ(weight)
        Returns simple average if all weights are equal (all same date).
        """

    def weighted_trend(self, data_points: list[tuple[date, float]]) -> dict:
        """Compute recency-weighted trend analysis.
        Returns:
        {
            "direction": "declining",      # "improving" | "stable" | "declining"
            "slope": -0.4,                 # weighted linear regression slope
            "weighted_mean": 65.3,         # recency-weighted average
            "unweighted_mean": 68.1,       # simple average for comparison
            "recency_delta": -2.8,         # weighted - unweighted (negative = recent worse)
            "confidence": 0.85,            # R² of weighted regression
            "data_points": 30
        }

        Direction thresholds:
          slope > +0.3 per business day: "improving"
          slope < -0.3 per business day: "declining"
          else: "stable"
        """

    def weighted_percentile(self, value: float, population: list[tuple[date, float]]) -> float:
        """Where does this value rank among its recency-weighted peers?
        Recent peers count more. A score of 70 among mostly-old-70s
        and recent-60s is actually above the recency-weighted median.
        Returns 0.0-1.0 percentile.
        """
```

### Integration with Existing Normalization

`lib/intelligence/scoring.py` currently has:
- `normalize_percentile(value, population)` — rank against peers
- `normalize_relative(value, history)` — rank against own history
- `normalize_threshold(value, target)` — against absolute targets

Add recency-weighted variants:
- `normalize_percentile_weighted(value, population, weighter)` — peers weighted by recency
- `normalize_relative_weighted(value, history, weighter)` — own history weighted by recency

These are **new functions**, not replacements. Consumers switch by calling the weighted version when temporal context matters.

### Integration with Health Unifier

`lib/intelligence/health_unifier.py` reads `score_history` for trends:
- `get_health_trend(entity_type, entity_id, days)` currently returns unweighted series
- Add: `get_weighted_health_trend(entity_type, entity_id, days, weighter)` that applies recency decay

### Configuration

Add to `config/intelligence.yaml`:

```yaml
recency_weighting:
  enabled: true
  half_life_business_days: 14     # data halves in weight every 14 business days
  min_weight: 0.05                # floor — data older than ~60 business days still counts slightly
  trend_direction_threshold: 0.3  # slope magnitude to classify as improving/declining
```

### Design Decision: Business Days, Not Calendar Days

Decay uses **business days**, not calendar days. Reason: a data point from Thursday should not lose weight over the weekend when no business activity happens. A 14-business-day half-life means ~3 calendar weeks, which is the right timescale for an agency's operational rhythm.

## Validation

- Weight for today = 1.0
- Weight for 14 business days ago ≈ 0.5
- Weight for 28 business days ago ≈ 0.25
- Weight floors at min_weight (0.05), never reaches 0
- weighted_average of identical values = that value (regardless of dates)
- weighted_trend with strictly increasing recent scores → "improving"
- weighted_trend with flat recent scores but old variance → "stable"
- recency_delta is negative when recent data is worse than historical
- weighted_percentile matches unweighted when all data is same date
- Integration: health_unifier returns weighted trend when weighter provided

## Estimated Effort

~200 lines
