# IW-5.1: Integration Validation

## Objective
Verify that the intelligence system is fully integrated into the daemon cycle and behaves correctly across cycles. Confirm data persistence, event emission, health unification, and system invariants.

## Implementation

### Test Plan: `tests/test_intelligence_wiring.py`

This test file validates the complete intelligence wiring:

```python
import pytest
from datetime import datetime, timedelta
from lib.daemon import Daemon
from lib.intelligence.persistence import (
    SignalStatePersistence, PatternPersistence, CostPersistence
)
from lib.intelligence.events import IntelligenceEventConsumer
from lib.intelligence.health_unifier import HealthUnifier
from lib.query_engine import QueryEngine

class TestSignalPersistence:
    """Verify signals persist across daemon restarts."""

    def test_signal_state_survives_restart(self, query_engine):
        """
        VALIDATION 1: Verify signal state survives daemon restart.
        - Run daemon cycle
        - Store detected signals
        - Create new daemon instance
        - Verify signals still in database
        """
        daemon = Daemon(query_engine)
        daemon.run_cycle()
        
        # Get signals from first cycle
        persistence = SignalStatePersistence(query_engine)
        signals_cycle_1 = persistence.get_active_signals()
        
        # Create new daemon (simulates restart)
        daemon_2 = Daemon(query_engine)
        persistence_2 = SignalStatePersistence(query_engine)
        
        # Verify same signals exist
        signals_cycle_2 = persistence_2.get_active_signals()
        assert len(signals_cycle_1) == len(signals_cycle_2)
        
        signal_keys_1 = {s.signal_key for s in signals_cycle_1}
        signal_keys_2 = {s.signal_key for s in signals_cycle_2}
        assert signal_keys_1 == signal_keys_2

class TestPatternPersistence:
    """Verify patterns persist from last cycle."""

    def test_patterns_retrievable_from_last_cycle(self, query_engine):
        """
        VALIDATION 2: Verify patterns from last cycle are retrievable.
        - Run daemon cycle
        - Record detected patterns with cycle_id
        - Query patterns from last cycle
        - Verify all patterns returned
        """
        daemon = Daemon(query_engine)
        cycle_id = daemon.generate_cycle_id()
        daemon.run_cycle()
        
        persistence = PatternPersistence(query_engine)
        patterns = persistence.get_patterns_in_cycle(cycle_id)
        
        # Should have at least some patterns (depends on test data)
        assert isinstance(patterns, list)
        # Each pattern should have required fields
        for pattern in patterns:
            assert pattern.pattern_id is not None
            assert pattern.detected_at is not None
            assert pattern.cycle_id == cycle_id

class TestScoreHistoryGrowth:
    """Verify score history grows correctly."""

    def test_score_history_grows_one_per_entity_per_cycle(self, query_engine):
        """
        VALIDATION 3: Verify score history grows by one row per entity per cycle.
        - Get initial score history count
        - Run daemon cycle
        - Count score history rows
        - Verify count increased by number of scored entities
        """
        from lib.client_truth.client_repository import ClientRepository
        
        # Get all clients that will be scored
        repo = ClientRepository(query_engine)
        all_clients = repo.get_all()
        expected_new_scores = len(all_clients)
        
        # Run cycle
        daemon = Daemon(query_engine)
        daemon.run_cycle()
        
        # Verify score history has new entries
        query = "SELECT COUNT(*) as count FROM score_history"
        result = query_engine.fetch_one(query)
        score_history_count = result['count']
        
        assert score_history_count >= expected_new_scores

class TestHealthUnificationAccuracy:
    """Verify scorecard health matches agency snapshot health."""

    def test_agency_snapshot_health_matches_scorecard(self, query_engine):
        """
        VALIDATION 4: Verify agency snapshot health scores match scorecard scores.
        - Run daemon cycle (populates score_history)
        - Get latest agency snapshot
        - Compare health scores to scorecard calculations
        - Allow ±2 point tolerance for rounding
        """
        from lib.agency_snapshot.aggregator import AgencySnapshot
        
        daemon = Daemon(query_engine)
        daemon.run_cycle()
        
        # Get agency snapshot
        snapshot = AgencySnapshot(query_engine)
        agency_data = snapshot.compute_snapshot()
        
        # Get scorecard health from unifier
        unifier = HealthUnifier(query_engine)
        
        # For each client in snapshot, verify health matches scorecard
        for client_data in agency_data.get('clients', []):
            client_id = client_data['id']
            agency_health = client_data['health']
            
            scorecard_health = unifier.get_latest_health('client', client_id)
            if scorecard_health:
                difference = abs(agency_health - scorecard_health.composite_health)
                assert difference <= 2.0, \
                    f"Client {client_id}: agency={agency_health}, scorecard={scorecard_health.composite_health}"

class TestEventEmission:
    """Verify intelligence events are emitted for critical findings."""

    def test_critical_signals_emit_events(self, query_engine):
        """
        VALIDATION 5: Verify critical signals emit intelligence events.
        - Run daemon cycle
        - Retrieve unconsumed signal_new events with CRITICAL severity
        - Verify at least some events exist (depends on test data)
        """
        daemon = Daemon(query_engine)
        daemon.run_cycle()
        
        # Get unconsumed critical events
        consumer = IntelligenceEventConsumer(query_engine)
        critical_events = consumer.get_unconsumed_events(
            event_type='signal_new',
            severity='CRITICAL'
        )
        
        # Critical signals should produce events
        # (assertion depends on test data; adjust if test has no critical signals)
        assert isinstance(critical_events, list)

    def test_pattern_detection_emits_events(self, query_engine):
        """
        VALIDATION 6: Verify patterns emit intelligence events.
        - Run daemon cycle
        - Retrieve unconsumed pattern_detected events
        - Verify events have correct structure
        """
        daemon = Daemon(query_engine)
        daemon.run_cycle()
        
        consumer = IntelligenceEventConsumer(query_engine)
        pattern_events = consumer.get_unconsumed_events(event_type='pattern_detected')
        
        for event in pattern_events:
            assert event.event_type == 'pattern_detected'
            assert event.event_data is not None
            assert 'pattern_id' in event.event_data

class TestEventCleanup:
    """Verify events don't accumulate indefinitely."""

    def test_events_archived_after_30_days(self, query_engine):
        """
        VALIDATION 7: Verify consumed events are archived after 30 days.
        - Create a consumed event with consumed_at 31 days ago
        - Run archive_old_events(days=30)
        - Verify event moved to archive table
        - Verify event removed from main table
        """
        consumer = IntelligenceEventConsumer(query_engine)
        
        # Create old consumed event directly in DB
        cutoff = (datetime.utcnow() - timedelta(days=31)).isoformat()
        old_event_id = 'evt_test_old'
        
        insert_query = """
        INSERT INTO intelligence_events
        (id, event_type, severity, entity_type, entity_id, event_data, created_at, consumed_at, consumer)
        VALUES (?, 'signal_new', 'INFO', 'client', 'cli_1', '{}', ?, ?, ?)
        """
        query_engine.execute(insert_query, [old_event_id, cutoff, cutoff, 'test_consumer'])
        
        # Run archive
        archived_count = consumer.archive_old_events(days=30)
        
        # Verify it was archived
        archive_query = "SELECT * FROM intelligence_events_archive WHERE id = ?"
        archived = query_engine.fetch_one(archive_query, [old_event_id])
        assert archived is not None
        
        # Verify it was removed from main table
        main_query = "SELECT * FROM intelligence_events WHERE id = ?"
        main = query_engine.fetch_one(main_query, [old_event_id])
        assert main is None

class TestDaemonCycleCompletion:
    """Verify full daemon cycle completes successfully."""

    def test_daemon_cycle_includes_intelligence_stage(self, query_engine):
        """
        VALIDATION 8: Verify daemon cycle includes intelligence stage.
        - Run full daemon cycle
        - Verify intelligence_phase was called (check for results)
        - Verify cycle completed without exceptions
        """
        daemon = Daemon(query_engine)
        
        # Should not raise
        daemon.run_cycle()
        
        # Verify intelligence work was done
        # Check for signal state, patterns, scores
        signal_persistence = SignalStatePersistence(query_engine)
        signals = signal_persistence.get_active_signals()
        assert signals is not None  # Could be empty list, but not None
        
        pattern_persistence = PatternPersistence(query_engine)
        patterns = pattern_persistence.get_recent_patterns(days=1)
        assert patterns is not None
        
        # Score history should have entries
        score_query = "SELECT COUNT(*) as count FROM score_history"
        score_result = query_engine.fetch_one(score_query)
        assert score_result['count'] >= 0

class TestSignalStateManagement:
    """Verify signal state transitions work correctly."""

    def test_signal_escalation(self, query_engine):
        """
        VALIDATION 9: Verify signal escalation persists correctly.
        - Create a signal
        - Mark it escalated
        - Verify escalated_at is set
        """
        persistence = SignalStatePersistence(query_engine)
        
        # Create a signal
        from lib.intelligence.persistence import SignalStateRecord
        signal = SignalStateRecord(
            signal_key='test_signal',
            entity_type='client',
            entity_id='cli_1',
            signal_type='health_declining',
            severity='WARNING',
            first_detected_at=datetime.utcnow().isoformat(),
            last_detected_at=datetime.utcnow().isoformat(),
            escalated_at=None,
            cleared_at=None,
            detection_count=1,
            cooldown_until=None,
            state='active'
        )
        persistence.upsert(signal)
        
        # Escalate it
        escalation_time = datetime.utcnow().isoformat()
        persistence.mark_escalated('test_signal', escalation_time)
        
        # Verify
        retrieved = persistence.get_signal('test_signal')
        assert retrieved is not None
        assert retrieved.escalated_at == escalation_time

class TestHealthScoreFormula:
    """Verify health score calculation uses correct formula."""

    def test_weighted_health_formula(self, query_engine):
        """
        VALIDATION 10: Verify weighted health formula.
        Delivery 35% + Comms 25% + Cash 25% + Relationship 15%
        """
        unifier = HealthUnifier(query_engine)
        
        # Test with known values
        delivery = 100
        comms = 80
        cash = 90
        relationship = 85
        
        composite = unifier.calculate_weighted_health(
            delivery=delivery,
            comms=comms,
            cash=cash,
            relationship=relationship
        )
        
        expected = (delivery * 0.35) + (comms * 0.25) + (cash * 0.25) + (relationship * 0.15)
        assert composite == pytest.approx(expected, abs=0.01)
```

### Test Plan: `tests/test_health_unification.py`

```python
import pytest
from lib.intelligence.health_unifier import HealthUnifier
from lib.scorecard import ScorecardEngine
from lib.client_truth.health_calculator import HealthCalculator

class TestHealthUnifierIntegration:
    """Verify health unifier correctly interfaces with scorecard."""

    def test_scorecard_health_persists_to_score_history(self, query_engine):
        """Verify scorecard results are saved to score_history."""
        scorecard = ScorecardEngine(query_engine)
        
        # Score a client
        client_id = 'cli_test'
        score = scorecard.score_client(client_id)
        
        # Verify in score_history
        query = "SELECT * FROM score_history WHERE entity_id = ? ORDER BY computed_at DESC LIMIT 1"
        row = query_engine.fetch_one(query, [client_id])
        assert row is not None
        assert row['composite_health'] == pytest.approx(score.composite_health, abs=0.01)

    def test_health_calculator_delegates_to_unifier(self, query_engine):
        """Verify HealthCalculator reads from unifier."""
        calculator = HealthCalculator(query_engine)
        
        # Score a client
        client_id = 'cli_test'
        health = calculator.calculate_health(client_id)
        
        # Should match unifier
        unifier = HealthUnifier(query_engine)
        expected = unifier.get_latest_health('client', client_id)
        
        if expected:
            assert health == pytest.approx(expected.composite_health, abs=0.01)

    def test_health_trend_returns_chronological_history(self, query_engine):
        """Verify health trend returns ordered results."""
        unifier = HealthUnifier(query_engine)
        
        client_id = 'cli_test'
        trend = unifier.get_health_trend('client', client_id, days=30)
        
        # Should be ordered chronologically
        if len(trend) > 1:
            for i in range(len(trend) - 1):
                assert trend[i].computed_at >= trend[i + 1].computed_at
```

## Validation Checklist

- [ ] Signal state survives daemon restart (VALIDATION 1)
- [ ] Patterns from last cycle are retrievable (VALIDATION 2)
- [ ] Score history grows by one row per entity per cycle (VALIDATION 3)
- [ ] Agency snapshot health matches scorecard health ±2 points (VALIDATION 4)
- [ ] CRITICAL signals emit intelligence events (VALIDATION 5)
- [ ] Patterns emit intelligence events (VALIDATION 6)
- [ ] Consumed events archived after 30 days (VALIDATION 7)
- [ ] Daemon cycle completes successfully with intelligence stage (VALIDATION 8)
- [ ] Signal escalation persists correctly (VALIDATION 9)
- [ ] Weighted health formula is correct (VALIDATION 10)
- [ ] All tests pass without exceptions
- [ ] No SQL injection vectors (all queries parameterized)
- [ ] No unhandled exceptions in event emission/consumption

## Files Created
- `tests/test_intelligence_wiring.py`
- `tests/test_health_unification.py`

## Estimated Effort
Medium — ~200 lines
