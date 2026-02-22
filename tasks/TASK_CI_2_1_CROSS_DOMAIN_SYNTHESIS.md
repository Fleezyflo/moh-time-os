# CI-2.1: Cross-Domain Synthesis

## Objective
Build the synthesis layer that combines data from multiple domains into coherent, interpreted answers. A query about a client should pull from health, revenue, projects, communications, predictions, and history — and return structured intelligence, not raw numbers. "Client X: revenue strong at 340K YTD, but engagement declining — meeting frequency down 40% over 6 weeks."

## Implementation

### Synthesizer (`lib/conversational/synthesizer.py`)
```python
class Synthesizer:
    """Combine multi-domain data into coherent intelligence responses."""

    def synthesize_entity(self, entity_type: str, entity_id: str,
                           raw_data: dict) -> SynthesizedResponse:
        """
        Take raw data from multiple sources and produce a coherent summary.
        Structure:
          - Lead with the headline (what's most important right now)
          - Supporting data points with context
          - Trend interpretation (improving/declining/stable)
          - Open items requiring attention
          - Source citations for each data point
        """

    def synthesize_metric(self, metric_name: str, raw_data: dict,
                           time_range: 'TimeRange' = None) -> SynthesizedResponse:
        """
        Metric query answer with context.
        Not just "Revenue is 340K" but "Revenue is 340K YTD, up 12% vs same period
        last year. Top contributor: Client X (45% of total). Concern: Client Y
        revenue trending down 20% over last quarter."
        """

    def synthesize_comparison(self, entity_a: dict, entity_b: dict,
                                metrics: List[str] = None) -> SynthesizedResponse:
        """
        Side-by-side with interpretation.
        "Client X vs Client Y: X has higher revenue (340K vs 220K) but Y has better
        health (82 vs 58). Y pays faster (avg 15 days vs 42 days). X has more
        active projects (4 vs 2) but two are flagged at risk."
        """

    def synthesize_ranked_summary(self, signals: List[dict], predictions: List[dict],
                                    stale_entities: List[dict]) -> SynthesizedResponse:
        """
        "What should I worry about?" → ranked intelligence.
        Combines current signals, predictions, and stale items.
        Ranks by: severity × recency × impact.
        Top 5 items with clear action suggestions.
        """

    def synthesize_history(self, decisions: List[dict],
                            entity_type: str, entity_id: str) -> SynthesizedResponse:
        """
        "What did I decide about Client X last time?" → decision narrative.
        "Last time Client X showed declining health (Nov 2025), you sent a follow-up
        email and scheduled a review meeting. Health recovered to 72 within 3 weeks.
        Before that (Aug 2025), you dismissed the signal — health continued to drop
        to 45 before recovering after a direct call."
        """
```

### Response Formatting
```python
class ResponseFormatter:
    """Format synthesized data into readable responses."""

    def format_entity_response(self, synthesis: SynthesizedResponse) -> FormattedResponse:
        """
        Structure:
          headline: "Client X — Needs Attention"
          summary: "Revenue strong but engagement declining..."
          data_points: [
            {label: "Revenue YTD", value: "340K", trend: "up", source: "xero_revenue"},
            {label: "Health Score", value: "58", trend: "down", source: "health_engine"},
            ...
          ]
          open_items: ["Invoice #1234 overdue 28 days", "No meeting in 6 weeks"]
          suggested_actions: ["Draft follow-up email", "Schedule review meeting"]
        """

    def format_metric_response(self, synthesis: SynthesizedResponse) -> FormattedResponse:
        """Single metric with context and trend."""

    def format_comparison_response(self, synthesis: SynthesizedResponse) -> FormattedResponse:
        """Side-by-side with winner/loser indicators per metric."""

    def format_ranked_response(self, synthesis: SynthesizedResponse) -> FormattedResponse:
        """Numbered priority list with severity indicators."""

    def format_history_response(self, synthesis: SynthesizedResponse) -> FormattedResponse:
        """Chronological narrative of past decisions and outcomes."""
```

### Data Schemas
```python
@dataclass
class SynthesizedResponse:
    headline: str                     # one-line summary
    summary: str                      # 2-3 sentence interpretation
    data_points: List[DataPoint]      # individual facts with sources
    trends: List[TrendIndicator]      # up/down/stable indicators
    open_items: List[str]             # things requiring attention
    suggested_actions: List[str]      # what you could do about it
    sources: List[str]                # which engines/tables contributed
    confidence: float                 # how complete the picture is (0-1)

@dataclass
class DataPoint:
    label: str                        # "Revenue YTD"
    value: str                        # "340K"
    raw_value: float | None           # 340000
    trend: str | None                 # 'up' | 'down' | 'stable'
    trend_detail: str | None          # "+12% vs last year"
    source: str                       # "xero_revenue_summary"
    timestamp: str | None             # when this data was current

@dataclass
class TrendIndicator:
    metric: str
    direction: str                    # 'improving' | 'declining' | 'stable'
    magnitude: str                    # 'significant' | 'moderate' | 'slight'
    timeframe: str                    # 'over last 6 weeks'

@dataclass
class FormattedResponse:
    text: str                         # plain text response
    structured: dict                  # structured data for UI rendering
    sources_cited: List[str]          # referenced data sources
    action_cards: List[dict] | None   # if suggested actions should be actionable
```

### Interpretation Rules
```python
INTERPRETATION_RULES = {
    'health_score': {
        'good': {'min': 70, 'label': 'healthy'},
        'concern': {'min': 50, 'max': 69, 'label': 'needs attention'},
        'critical': {'max': 49, 'label': 'at risk'},
    },
    'payment_days': {
        'good': {'max': 30, 'label': 'pays on time'},
        'slow': {'min': 31, 'max': 60, 'label': 'slow payer'},
        'concern': {'min': 61, 'label': 'chronic late payer'},
    },
    'communication_frequency': {
        'active': {'min_per_month': 4, 'label': 'regular engagement'},
        'declining': {'trend': 'down_20pct', 'label': 'engagement declining'},
        'silent': {'days_since_last': 30, 'label': 'gone silent'},
    },
}
```

### API Endpoints
```
POST /api/v2/synthesize/entity     (body: entity_type, entity_id)
POST /api/v2/synthesize/metric     (body: metric, time_range, filters)
POST /api/v2/synthesize/compare    (body: entity_a, entity_b, metrics)
POST /api/v2/synthesize/priorities (what should I worry about)
POST /api/v2/synthesize/history    (body: entity_type, entity_id)
```

## Validation
- [ ] Entity synthesis pulls from all relevant data sources (health, revenue, projects, comms, predictions, history)
- [ ] Metric synthesis includes trend and comparison context, not just raw numbers
- [ ] Comparison synthesis correctly identifies differences and highlights concerns
- [ ] Ranked summary combines signals + predictions + stale items with correct priority ordering
- [ ] History synthesis produces accurate chronological narrative from decision journal
- [ ] Source citations correctly reference origin table/engine for each data point
- [ ] Interpretation rules correctly categorize health scores, payment patterns, engagement
- [ ] Responses are concise (summary under 3 sentences, data points under 10)
- [ ] Missing data handled gracefully (partial response with noted gaps, not errors)
- [ ] Confidence score reflects data completeness

## Files Created
- `lib/conversational/synthesizer.py`
- `lib/conversational/response_formatter.py`
- `lib/conversational/interpretation_rules.py`
- `tests/test_synthesizer.py`

## Estimated Effort
Large — ~800 lines (synthesis logic + formatting + interpretation + tests)
