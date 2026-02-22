# SM-4.1: Behavioral Pattern Learning & Validation

## Objective
Analyze the decision journal to learn your operational patterns — which signals you act on, which you dismiss, how you respond to different situations — and use this to rank and frame future intelligence. Validate the entire memory system end-to-end.

## Implementation

### BehavioralAnalyzer (`lib/memory/behavioral_analyzer.py`)
```python
class BehavioralAnalyzer:
    """Learn operational patterns from the decision journal."""

    def get_action_distribution(self, signal_type: str = None) -> Dict[str, float]:
        """
        For a given signal type (or overall):
        What % of the time do you: act, dismiss, escalate, ignore?
        """

    def get_response_time(self, severity: str = None) -> ResponseTimeStats:
        """
        How quickly do you act on signals?
        By severity: critical avg 2h, high avg 8h, medium avg 3d
        """

    def get_preferred_action(self, entity_type: str, pattern: str) -> str | None:
        """
        When a client shows declining health, what do you usually do?
        Returns the most common action_taken for that entity+pattern combo.
        e.g., 'For declining client health, you typically send a follow-up email (65% of the time)'
        """

    def get_dismiss_patterns(self) -> List[DismissPattern]:
        """
        Signal types you frequently dismiss.
        Used by signal lifecycle for auto-deprioritization.
        """

    def generate_context_hint(self, entity_type: str, entity_id: str,
                               situation: str) -> str | None:
        """
        Generate a contextual hint based on past behavior:
        'Last time Client X showed this pattern (Aug 2025), you scheduled
         a call and offered a discount — their health recovered to 78 within 3 weeks.'
        Returns None if no relevant history.
        """

    def get_effectiveness_report(self) -> EffectivenessReport:
        """
        Which of your actions led to positive outcomes?
        (Requires outcome data from decision_journal.record_outcome)
        e.g., 'Follow-up emails after health decline: 70% led to health recovery'
        """
```

### Pattern Output Schema
```python
@dataclass
class DismissPattern:
    signal_type: str
    dismiss_rate: float       # 0-1
    total_occurrences: int
    suggested_action: str     # 'deprioritize' | 'adjust_threshold' | 'keep'

@dataclass
class ResponseTimeStats:
    severity: str
    avg_hours: float
    median_hours: float
    p90_hours: float
    sample_size: int

@dataclass
class EffectivenessReport:
    total_decisions_with_outcomes: int
    positive_outcome_rate: float
    by_action_type: Dict[str, float]   # action → positive_outcome_rate
    top_effective_patterns: List[str]   # human-readable
```

### Context Enrichment
```python
# Wire into signal presentation and prepared actions
def enrich_with_context(signal, entity_type, entity_id):
    """Add behavioral context to any signal or prepared action."""
    hint = behavioral_analyzer.generate_context_hint(
        entity_type, entity_id, signal.signal_type
    )
    if hint:
        signal.context_hint = hint

    preferred = behavioral_analyzer.get_preferred_action(
        entity_type, signal.signal_type
    )
    if preferred:
        signal.suggested_action = preferred
```

### API Endpoints
```
GET  /api/v2/memory/patterns/actions?signal_type=...
GET  /api/v2/memory/patterns/response-times
GET  /api/v2/memory/patterns/dismissals
GET  /api/v2/memory/patterns/effectiveness
GET  /api/v2/memory/context/:entity_type/:entity_id?situation=...
```

### End-to-End Memory Validation
```python
class MemoryValidation:
    """Validate the entire Brief 22 memory system."""

    def test_journal_captures_all_interaction_types(self):
        """Every decision type correctly logged."""

    def test_entity_memory_updates_on_view(self):
        """Viewing entity page → last_reviewed_at updated."""

    def test_signal_suppression_after_dismiss(self):
        """Dismissed signal → not shown within suppression window."""

    def test_signal_reactivation_on_worsening(self):
        """Condition worsens past threshold → signal re-raised."""

    def test_behavioral_hint_generation(self):
        """With decision history, context hints are generated accurately."""

    def test_stale_entity_detection(self):
        """Entity not reviewed in 14 days with active signals → flagged stale."""

    def test_memory_enrichment_pipeline(self):
        """Signal presented → enriched with entity history + behavioral hint."""

    def test_no_memory_leaks(self):
        """Journal doesn't grow unbounded — old entries archivable."""
```

## Validation
- [ ] Action distribution computed correctly from journal entries
- [ ] Response time stats accurate against logged timestamps
- [ ] Context hints generated when relevant history exists
- [ ] Context hints return None when no relevant history
- [ ] Effectiveness report requires outcome data (graceful without it)
- [ ] Behavioral patterns feed into signal lifecycle deprioritization
- [ ] End-to-end: signal raised → presented with context → acted on → logged → used for future enrichment
- [ ] Memory tables don't grow unbounded (retention policy applied)

## Files Created
- `lib/memory/behavioral_analyzer.py`
- `tests/test_behavioral_analyzer.py`
- `tests/test_memory_validation.py`

## Estimated Effort
Large — ~700 lines (behavioral analysis + context enrichment + validation suite)
