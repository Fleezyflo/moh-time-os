# IO-4.1: Debug Mode & Single-Entity Trace

## Objective

Provide a way to run the full intelligence pipeline for a single entity with verbose output, showing every computation step and its result. Essential for the implementing agent to debug issues and for Molham to understand specific entity behavior.

## Dependencies

- IO-1.1 (audit trail for structured logging)
- All intelligence modules (scoring, signals, patterns, cost, quality)

## Deliverables

### New file: `lib/intelligence/debug.py`

```python
class IntelligenceDebugger:
    """Run intelligence pipeline for a single entity with full trace."""

    def __init__(self, db_path: Path): ...

    def trace_entity(self, entity_type: str, entity_id: str) -> dict:
        """Run full intelligence pipeline for one entity, returning detailed trace.

        Returns:
        {
            "entity": { "type": "client", "id": "abc", "name": "Client X" },
            "timestamp": "2026-02-21T10:30:00Z",
            "duration_ms": 142,
            "steps": [
                {
                    "step": "data_quality",
                    "duration_ms": 12,
                    "result": {
                        "quality_score": 0.73,
                        "domains": { "tasks": 0.9, "communications": 0.8, ... },
                        "gaps": ["No calendar events"]
                    }
                },
                {
                    "step": "scoring",
                    "duration_ms": 35,
                    "result": {
                        "composite_score": 58,
                        "classification": "at_risk",
                        "dimensions": [
                            { "name": "health", "score": 45, "weight": 0.30, "metrics_used": {...} },
                            { "name": "engagement", "score": 52, "weight": 0.30, "metrics_used": {...} },
                            ...
                        ],
                        "previous_score": 72,
                        "change": -14
                    }
                },
                {
                    "step": "signals",
                    "duration_ms": 28,
                    "result": {
                        "evaluated": 10,      # total signal types checked
                        "detected": 3,        # signals that fired
                        "signals": [
                            {
                                "signal_id": "client_overdue_tasks",
                                "fired": True,
                                "severity": "warning",
                                "evidence": { "value": 7, "threshold": 5 },
                                "state": "ongoing",
                                "age_days": 3
                            },
                            {
                                "signal_id": "client_comm_drop",
                                "fired": True,
                                "severity": "watch",
                                "evidence": { "current_volume": 12, "baseline": 20 }
                            },
                            {
                                "signal_id": "client_invoice_aging",
                                "fired": False,
                                "reason": "value 25 below threshold 45"
                            }
                        ]
                    }
                },
                {
                    "step": "patterns",
                    "duration_ms": 22,
                    "result": {
                        "checked": 5,
                        "detected": 1,
                        "patterns": [
                            {
                                "pattern_id": "engagement_drop",
                                "fired": True,
                                "confidence": 0.82,
                                "direction": "worsening",
                                "components": [...]
                            }
                        ]
                    }
                },
                {
                    "step": "cost_to_serve",
                    "duration_ms": 18,
                    "result": { "effort_score": 45, "efficiency_ratio": 0.83, "profitability": "healthy" }
                },
                {
                    "step": "trajectory",
                    "duration_ms": 15,
                    "result": { "direction": "declining", "velocity": -2.3, "projected_30d": 52 }
                },
                {
                    "step": "proposals",
                    "duration_ms": 12,
                    "result": {
                        "generated": 1,
                        "proposals": [
                            { "type": "client_risk", "urgency": "this_week", "priority_score": 0.72 }
                        ]
                    }
                }
            ],
            "explanation": "Client X scored 58 (at_risk). Score dropped 14 points due to...",
            "data_quality_warning": "No calendar data available — engagement scoring may be incomplete"
        }
        """

    def trace_signal(self, signal_type: str, entity_type: str, entity_id: str) -> dict:
        """Run a single signal evaluation with full metric trace."""

    def trace_pattern(self, pattern_id: str) -> dict:
        """Run a single pattern detection with full evidence trace."""
```

### CLI integration

Add to existing CLI or create a simple script:
```bash
python -m lib.intelligence.debug --entity client abc123
python -m lib.intelligence.debug --signal client_overdue_tasks --entity client abc123
python -m lib.intelligence.debug --pattern engagement_drop
```

### API endpoint (via Brief 26)

#### GET `/api/v3/intelligence/debug/{entity_type}/{entity_id}`

Returns the full trace. Useful for the implementing agent during development. Consider gating behind a debug flag in production.

## Validation

- trace_entity runs all steps and returns structured output
- Each step includes actual metrics used (not just results)
- Failed steps don't block subsequent steps
- trace_signal shows threshold vs actual comparison
- trace_pattern shows which component signals contributed
- CLI produces readable output
- Duration tracking is accurate

## Estimated Effort

~200 lines
