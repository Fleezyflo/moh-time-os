# IW-3.1: Wire Intelligence into Daemon Cycle

## Objective
Integrate the intelligence system into the core daemon cycle. The daemon currently runs collect → truth_cycle → snapshot → notify. Add an intelligence stage that executes after truth_cycle and persists signal state, patterns, scores, and proposals, then emits events for critical findings.

## Implementation

### Current Daemon Flow
```
collect (30 min)
  → truth_cycle (15 min)
  → snapshot (15 min)
  → notify (60 min)
```

### New Daemon Flow
```
collect (30 min)
  → truth_cycle (15 min)
  → intelligence (new)
  → snapshot (15 min)
  → notify (60 min)
```

### Intelligence Stage in Daemon (`lib/daemon.py`)
```python
import logging
from lib.intelligence.signals import SignalGenerator
from lib.intelligence.engine import IntelligenceEngine
from lib.intelligence.persistence import (
    SignalStatePersistence, PatternPersistence, CostPersistence
)
from lib.intelligence.events import IntelligenceEventEmitter
from lib.scorecard import ScorecardEngine
from lib.query_engine import QueryEngine

logger = logging.getLogger(__name__)

class Daemon:
    def __init__(self, query_engine: QueryEngine, ...):
        self.query_engine = query_engine
        self.signal_generator = SignalGenerator(...)
        self.intelligence_engine = IntelligenceEngine(...)
        self.signal_persistence = SignalStatePersistence(query_engine)
        self.pattern_persistence = PatternPersistence(query_engine)
        self.cost_persistence = CostPersistence(query_engine)
        self.event_emitter = IntelligenceEventEmitter(query_engine)
        self.scorecard = ScorecardEngine(...)

    def run_cycle(self) -> None:
        """Execute full daemon cycle."""
        try:
            logger.info("Starting daemon cycle")
            cycle_id = self.generate_cycle_id()
            
            self.collect_phase(cycle_id)
            self.truth_cycle_phase(cycle_id)
            self.intelligence_phase(cycle_id)  # NEW STAGE
            self.snapshot_phase(cycle_id)
            self.notify_phase(cycle_id)
            
            logger.info(f"Daemon cycle {cycle_id} completed successfully")
        except Exception as e:
            logger.error(f"Daemon cycle failed: {e}", exc_info=True)
            raise

    def intelligence_phase(self, cycle_id: str) -> None:
        """
        Execute intelligence stage.
        
        Responsibilities:
        1. Generate and persist signal state changes
        2. Detect and persist patterns
        3. Score entities and persist to score_history
        4. Store latest proposal set
        5. Emit events for critical/warning findings
        """
        logger.info(f"Starting intelligence phase for cycle {cycle_id}")
        
        try:
            # 1. Generate signals and persist state
            logger.debug("Generating signals...")
            signals = self.signal_generator.detect_all_signals()
            for signal in signals:
                self.signal_persistence.upsert(signal)
                logger.debug(f"Persisted signal: {signal.signal_key}")
            
            # 2. Detect patterns and persist snapshots
            logger.debug("Detecting patterns...")
            patterns = self.intelligence_engine.detect_patterns(cycle_id)
            for pattern in patterns:
                self.pattern_persistence.record_pattern(pattern)
                logger.debug(f"Persisted pattern: {pattern.pattern_id}")
            
            # 3. Score all entities and persist to score_history
            logger.debug("Scoring entities...")
            entities = self.get_all_entities_to_score()
            for entity in entities:
                try:
                    score = self.scorecard.score_client(entity.id)
                    logger.debug(f"Scored {entity.type} {entity.id}: {score.composite_health}")
                except Exception as e:
                    logger.error(f"Failed to score {entity.type} {entity.id}: {e}")
                    # Continue scoring other entities
            
            # 4. Persist cost-to-serve snapshots
            logger.debug("Computing cost snapshots...")
            cost_daily = self.intelligence_engine.compute_cost_snapshot()
            if cost_daily:
                self.cost_persistence.record_snapshot(cost_daily)
            
            # 5. Store latest proposal set
            logger.debug("Generating proposals...")
            proposals = self.intelligence_engine.generate_proposals(cycle_id)
            self.store_proposals(proposals, cycle_id)
            
            # 6. Emit events for critical/warning findings
            logger.debug("Emitting intelligence events...")
            critical_signals = [s for s in signals if s.severity in ['CRITICAL', 'WARNING']]
            for signal in critical_signals:
                self.event_emitter.emit_signal_event(
                    event_type='signal_new',
                    signal=signal,
                    severity=signal.severity
                )
            
            # Emit pattern events
            critical_patterns = [p for p in patterns if p.severity in ['CRITICAL', 'WARNING']]
            for pattern in critical_patterns:
                self.event_emitter.emit_pattern_event(
                    event_type='pattern_detected',
                    pattern=pattern,
                    severity=pattern.severity
                )
            
            # Emit proposal events
            self.event_emitter.emit_proposal_events(proposals)
            
            logger.info(f"Intelligence phase completed: {len(signals)} signals, "
                       f"{len(patterns)} patterns, {len(proposals)} proposals")
        
        except Exception as e:
            logger.error(f"Intelligence phase failed: {e}", exc_info=True)
            raise

    def collect_phase(self, cycle_id: str) -> None:
        """Existing collect phase - no changes."""
        # ... existing code

    def truth_cycle_phase(self, cycle_id: str) -> None:
        """Existing truth_cycle phase - no changes."""
        # ... existing code

    def snapshot_phase(self, cycle_id: str) -> None:
        """Existing snapshot phase - no changes."""
        # ... existing code

    def notify_phase(self, cycle_id: str) -> None:
        """Existing notify phase - can consume intelligence events."""
        # ... existing code
        # Optional: notify on CRITICAL intelligence events

    def get_all_entities_to_score(self) -> list:
        """Retrieve all clients and projects that should be scored."""
        # Query database for all active entities
        pass

    def store_proposals(self, proposals: list, cycle_id: str) -> None:
        """
        Store the latest proposal set (possibly overwriting previous cycle).
        Proposals bridge intelligence findings to Brief 24 preparation engine.
        """
        # Update proposals table with cycle_id
        pass

    def generate_cycle_id(self) -> str:
        """Generate a unique cycle ID (e.g., timestamp-based)."""
        from datetime import datetime
        return f"cycle_{datetime.utcnow().isoformat()}"
```

### Error Handling
- Signal detection failures do not block pattern detection
- Pattern detection failures do not block scoring
- Scoring failures do not block proposal generation
- Any failure is logged but does not stop the intelligence phase (fail gracefully)
- If intelligence phase fails entirely, daemon continues to snapshot/notify phases

### Integration with signal_generator, engine.py, scorecard.py
These modules already have the logic; daemon simply orchestrates their execution and persists the results.

## Validation
- [ ] Daemon cycle includes intelligence stage in correct position (after truth, before snapshot)
- [ ] intelligence_phase() method is called and completes successfully in tests
- [ ] Signal state persisted to database after signal generation
- [ ] Patterns persisted to database with correct cycle_id
- [ ] Score history populated with one entry per entity per cycle
- [ ] Cost snapshots persisted for daily summary
- [ ] Proposals stored and retrievable
- [ ] Events emitted for CRITICAL/WARNING signals
- [ ] Events emitted for CRITICAL/WARNING patterns
- [ ] Events emitted for generated proposals
- [ ] Errors logged but don't block cycle completion
- [ ] Cycle completes even if individual entity scoring fails

## Files Modified
- `lib/daemon.py` — add intelligence_phase() method and wire into run_cycle()

## Tests Created
- `tests/test_daemon_intelligence.py` — verify cycle flow, persistence, event emission

## Estimated Effort
Medium — ~150 lines
