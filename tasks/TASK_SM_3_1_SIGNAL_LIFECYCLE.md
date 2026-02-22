# SM-3.1: Signal Lifecycle & Stale Suppression

## Objective
Upgrade the signal system to track lifecycle states so signals you've already seen and acted on don't re-surface. Signals you consistently dismiss for a category get auto-deprioritized. The system stops being noisy and starts being precise.

## Implementation

### New Table
```sql
CREATE TABLE signal_states (
    signal_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'raised',
    -- 'raised' | 'seen' | 'acted_on' | 'resolved' | 'dismissed' | 'expired'
    raised_at TEXT NOT NULL,
    seen_at TEXT,
    acted_on_at TEXT,
    resolved_at TEXT,
    dismissed_at TEXT,
    suppressed_until TEXT,           -- don't re-show until this date
    reactivation_threshold TEXT,     -- JSON: what change would re-raise it
    -- e.g., {"metric": "health_score", "current": 58, "trigger_delta": -15}
    dismiss_count INTEGER DEFAULT 0, -- how many times dismissed (across re-raises)
    last_presented_at TEXT           -- last time this was shown to you
);

CREATE INDEX idx_signal_states_state ON signal_states(state);
CREATE INDEX idx_signal_states_suppressed ON signal_states(suppressed_until);
```

### SignalLifecycleManager (`lib/memory/signal_lifecycle.py`)
```python
class SignalLifecycleManager:
    """Track signal lifecycle to prevent noise and repetition."""

    def on_signal_raised(self, signal_id: str, signal_data: dict) -> None:
        """New signal raised. Check if it's a re-raise of a previously dismissed signal."""

    def on_signal_seen(self, signal_id: str) -> None:
        """You viewed a page where this signal was displayed."""

    def on_signal_acted_on(self, signal_id: str, action: str) -> None:
        """You took an action on this signal (dismiss, escalate, acknowledge)."""

    def on_signal_resolved(self, signal_id: str) -> None:
        """The underlying condition that caused the signal has improved."""

    def should_present(self, signal_id: str) -> bool:
        """
        Should this signal be shown to you?
        Returns False if:
          - State is 'dismissed' and suppressed_until hasn't passed
          - State is 'acted_on' and condition hasn't materially worsened
          - State is 'resolved' or 'expired'
          - Signal type has high dismiss rate (auto-deprioritized)
        """

    def check_reactivation(self, signal_id: str, current_data: dict) -> bool:
        """
        Has the underlying condition changed enough to re-raise?
        e.g., health dropped another 15 points since dismissal.
        """

    def get_active_signals(self) -> List[SignalWithState]:
        """Signals in states: 'raised' or 'seen' (not acted on, dismissed, or resolved)."""

    def get_signal_noise_report(self) -> Dict:
        """
        Which signal types have high dismiss rates?
        Suggest threshold adjustments.
        """
```

### Suppression Rules
```python
SUPPRESSION_RULES = {
    'dismissed': {
        'default_suppress_days': 7,       # don't re-show for 7 days
        'repeat_dismiss_suppress_days': 30, # if dismissed 3+ times, 30 days
    },
    'acted_on': {
        'recheck_days': 3,                 # recheck condition after 3 days
        'reactivation_delta_pct': 20,      # re-raise if metric worsens 20% more
    },
    'auto_deprioritize_threshold': 0.7,    # if 70%+ of a signal type is dismissed, auto-lower severity
}
```

### Integration with Existing Signal System
```python
# Modify signal presentation in UI to filter through lifecycle
def get_signals_for_display(entity_type=None, entity_id=None):
    raw_signals = signal_engine.get_signals(entity_type, entity_id)
    return [s for s in raw_signals if lifecycle_manager.should_present(s.id)]

# Modify signal actions to record lifecycle transitions
def dismiss_signal(signal_id):
    lifecycle_manager.on_signal_acted_on(signal_id, 'dismiss')
    decision_journal.record(decision_type='signal_dismissed', ...)
```

### API Endpoints
```
GET   /api/v2/signals/active              (filtered through lifecycle)
PATCH /api/v2/signals/:id/state           (transition state)
GET   /api/v2/signals/noise-report        (dismiss rates by type)
```

## Validation
- [ ] Dismissed signals don't re-appear within suppression window
- [ ] Re-activation triggers when condition materially worsens
- [ ] Repeat-dismissed signals get longer suppression windows
- [ ] Auto-deprioritization fires at 70%+ dismiss rate for a type
- [ ] Signal noise report correctly calculates dismiss rates
- [ ] Existing signal display respects lifecycle filtering
- [ ] Resolved signals correctly removed from active set
- [ ] All lifecycle transitions logged to decision journal

## Files Created
- `lib/memory/signal_lifecycle.py`
- `tests/test_signal_lifecycle.py`

## Estimated Effort
Large — ~700 lines (lifecycle engine + suppression logic + integration with existing signals)
