# IE-2.1: Cross-Domain Pattern Recognition

## Objective
Build `lib/intelligence/pattern_engine.py` — detect meaningful patterns that span multiple data sources (Asana + Gmail + Calendar + Xero), not just within a single source.

## Context
Current signal detection works within individual data sources. But the valuable patterns are cross-domain: "Client X has 3 overdue tasks, 12 unanswered emails, and a declined meeting" = relationship at risk. "Team member Y has 40 hours of meetings, 200 emails, and 15 task reassignments this week" = burnout risk.

## Implementation

### Pattern Types

1. **Client Risk Pattern**: overdue tasks + unanswered comms + meeting declines → client relationship at risk
2. **Capacity Crisis Pattern**: meeting overload + email spike + task delays → team member at capacity
3. **Revenue Leak Pattern**: completed work + no invoice → unbilled revenue
4. **Scope Creep Pattern**: task count growing + no new invoice + communication volume increasing
5. **Engagement Drop Pattern**: communication frequency declining + meeting cancellations + task completion slowing
6. **Payment Risk Pattern**: overdue invoices + declining communication → collection risk

### Engine Structure
```python
class PatternEngine:
    def __init__(self, db):
        self.detectors = [
            ClientRiskDetector(),
            CapacityCrisisDetector(),
            RevenueLeakDetector(),
            ScopeCreepDetector(),
            EngagementDropDetector(),
            PaymentRiskDetector(),
        ]

    def scan(self, period: DateRange) -> list[Pattern]:
        """Run all detectors, return identified patterns."""
        patterns = []
        for detector in self.detectors:
            patterns.extend(detector.detect(self.db, period))
        return self.deduplicate_and_rank(patterns)

@dataclass
class Pattern:
    pattern_type: str
    severity: str  # critical, warning, info
    entity_type: str  # client, team_member, project
    entity_id: str
    entity_name: str
    signals: list[dict]  # contributing data points
    description: str
    recommended_action: str
    confidence: float  # 0.0-1.0
```

### Detection Logic Example
```python
class ClientRiskDetector:
    def detect(self, db, period) -> list[Pattern]:
        for client in get_active_clients(db):
            overdue = count_overdue_tasks(db, client.id, period)
            unanswered = count_unanswered_emails(db, client.id, period, days=3)
            declined = count_declined_meetings(db, client.id, period)

            risk_score = (overdue * 0.4) + (unanswered * 0.35) + (declined * 0.25)
            if risk_score > threshold:
                yield Pattern(
                    pattern_type="client_risk",
                    severity="critical" if risk_score > high_threshold else "warning",
                    entity_id=client.id,
                    signals=[...],
                    confidence=min(risk_score / max_score, 1.0),
                )
```

### Integration
- PatternEngine runs as part of truth cycle (after truth modules, before snapshot)
- Detected patterns stored in `patterns` table
- High-severity patterns trigger Google Chat notifications
- Patterns surfaced in agency snapshot

## Validation
- [ ] Each detector returns patterns with real data
- [ ] Cross-domain correlation works (signals from 2+ data sources)
- [ ] Severity ranking is consistent
- [ ] Confidence scores are calibrated (not all 1.0 or all 0.0)
- [ ] Patterns deduplicated (same root cause → one pattern)
- [ ] Integration with truth cycle and snapshot verified

## Files Created
- `lib/intelligence/pattern_engine.py`
- `tests/test_pattern_engine.py`

## Estimated Effort
Large — ~400 lines, 6 detectors with cross-table correlation logic
