# IO-2.1: Explainability Engine

## Objective

Generate human-readable "because" explanations for every intelligence output. When a score drops, Molham should see "Score dropped from 72 to 58 because: +3 overdue tasks, -40% communication volume, invoice aging now 45 days."

## Dependencies

- IO-1.1 (audit trail provides the computation data)
- Brief 18 ID-3.1 (entity profiles provide the context)

## Deliverables

### New file: `lib/intelligence/explainer.py`

```python
class IntelligenceExplainer:
    """Generates human-readable explanations for intelligence outputs."""

    def __init__(self, db_path: Path): ...

    def explain_score_change(self, entity_type: str, entity_id: str) -> dict:
        """Explain why an entity's score changed since last computation.
        Returns:
        {
            "entity": "Client X",
            "previous_score": 72,
            "current_score": 58,
            "change": -14,
            "headline": "Score dropped 14 points — overdue tasks and declining communication",
            "factors": [
                { "dimension": "operational", "change": -8, "because": "Overdue tasks increased from 2 to 5" },
                { "dimension": "engagement", "change": -6, "because": "Communication volume dropped 40% vs 30-day average" },
                { "dimension": "financial", "change": 0, "because": "No change in financial metrics" }
            ],
            "data_quality": 0.73,
            "confidence": "moderate"
        }
        """

    def explain_signal(self, signal_key: str) -> dict:
        """Explain why a signal fired.
        Returns:
        {
            "signal": "client_overdue_tasks",
            "entity": "Client X",
            "headline": "7 tasks are overdue (threshold: 5)",
            "evidence": { "current_value": 7, "threshold": 5, "trend": "worsening" },
            "context": "This signal was first detected 3 days ago and has been escalating",
            "related_signals": ["communication_drop"],
            "suggested_action": "Review overdue tasks and prioritize resolution"
        }
        """

    def explain_pattern(self, pattern_id: str, cycle_id: str = None) -> dict:
        """Explain why a pattern was detected.
        Returns:
        {
            "pattern": "engagement_drop",
            "headline": "Client X shows declining engagement across 3 dimensions",
            "components": [
                "Communication volume down 40%",
                "Meeting cancellations up from 0 to 2 this month",
                "Task completion rate declined from 85% to 60%"
            ],
            "direction": "worsening",
            "confidence": 0.82,
            "first_detected": "2026-02-15",
            "suggested_action": "Schedule a check-in call to assess relationship health"
        }
        """

    def explain_proposal(self, proposal: dict) -> dict:
        """Explain why a proposal was generated and ranked at this priority.
        Returns:
        {
            "proposal_type": "client_risk",
            "headline": "Client X is at risk — declining engagement and overdue tasks",
            "triggered_by": ["signal: client_overdue_tasks", "pattern: engagement_drop"],
            "priority_factors": {
                "urgency": "high (7 overdue tasks)",
                "impact": "medium ($120K annual revenue)",
                "recency": "detected 3 days ago",
                "confidence": "moderate (data quality 0.73)"
            },
            "suggested_actions": [
                "Review and prioritize overdue tasks",
                "Schedule relationship check-in",
                "Review latest invoice status"
            ]
        }
        """

    def explain_entity_attention(self, entity_type: str, entity_id: str) -> dict:
        """Why does this entity need attention? Comprehensive explanation.
        Combines score change + active signals + patterns + proposals into one narrative.
        """
```

### Explanation Generation Strategy

Explanations are built from:
1. **Audit trail** (IO-1.1) — what went into the computation
2. **Score history** — delta between last two scores
3. **Signal state** — active signals with evidence
4. **Pattern snapshots** — detected patterns with entities

No LLM involved. Explanations are template-driven with data interpolation:
- "Score dropped {delta} points — {top_factor_1} and {top_factor_2}"
- "{metric} {direction} from {old} to {new} ({change_pct}%)"
- "This signal was first detected {age} ago and has been {state}"

### Integration

1. **Entity profiles** (ID-3.1): `narrative` field populated by explainer
2. **API responses** (Brief 26): explanation available via `/entity/{type}/{id}/explain`
3. **Notifications** (Brief 21): critical notifications include explanation
4. **Daily briefing** (PI-4.1): briefing sections use explainer for readability

## Validation

- Score change explanation identifies correct dimension drivers
- Signal explanation includes threshold vs actual
- Pattern explanation lists component signals
- Proposal explanation traces back to triggers
- Explanations read naturally (no jargon, no raw numbers without context)
- Empty/missing data produces graceful "insufficient data" explanation

## Estimated Effort

~400 lines
