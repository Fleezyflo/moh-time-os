# TASK: Wire System Memory modules
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.3 | Status: PENDING

## Context

Four system memory modules exist with real code but zero imports:

1. `lib/intelligence/decision_journal.py` (294 lines) — `DecisionJournal` class. Records decisions and their rationale for learning.
2. `lib/intelligence/entity_memory.py` (397 lines) — `EntityMemory` class. Tracks interaction history and attention debt per entity.
3. `lib/intelligence/signal_lifecycle.py` (524 lines) — `SignalLifecycleTracker` class. Manages signal states (new → active → resolved → expired).
4. `lib/intelligence/behavioral_patterns.py` (522 lines) — `BehavioralPatternAnalyzer` class. Detects user behavior patterns.

These are "memory" modules — they accumulate knowledge over time. They should run at the END of the intelligence phase so they capture results from all earlier steps.

## Objective

Wire all four modules into the intelligence pipeline.

## Instructions

### 1. Wire into `_intelligence_phase()` at the END

After all scoring, signals, patterns, and cost steps:

- `decision_journal` — records what the reasoner decided this cycle and why
- `entity_memory` — updates interaction recency and attention debt per entity
- `signal_lifecycle` — manages signal state transitions (may overlap with existing `update_signal_state` — check for conflicts)
- `behavioral_patterns` — analyzes accumulated pattern data for user behavior trends

**IMPORTANT:** `signal_lifecycle.py` may conflict with the existing `update_signal_state()` call in step 2. Read both carefully. If `SignalLifecycleTracker` is a superset, replace the inline signal state logic. If complementary, run after.

### 2. Read method signatures

```
python -c "from lib.intelligence.decision_journal import DecisionJournal; help(DecisionJournal.__init__)"
python -c "from lib.intelligence.entity_memory import EntityMemory; help(EntityMemory.__init__)"
python -c "from lib.intelligence.signal_lifecycle import SignalLifecycleTracker; help(SignalLifecycleTracker.__init__)"
python -c "from lib.intelligence.behavioral_patterns import BehavioralPatternAnalyzer; help(BehavioralPatternAnalyzer.__init__)"
```

## Preconditions
- [ ] None

## Validation
1. All four modules imported and called in `_intelligence_phase()`
2. Decision journal table populated after loop cycle
3. Entity memory updates reflected in DB
4. No conflicts with existing signal state logic
5. `ruff check`, `bandit` clean
6. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] All four modules wired at end of intelligence phase
- [ ] Tables populated after 2+ loop cycles
- [ ] No regression in signal detection
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`

## Estimate
3 hours

## Branch
`feat/wire-system-memory`
