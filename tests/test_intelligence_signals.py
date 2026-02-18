"""
Tests for Intelligence Signals Module.

Covers:
- Signal catalog validation
- Condition evaluators (threshold, trend, anomaly, compound)
- Entity-level signal detection
- Full database signal scan
"""

from pathlib import Path

import pytest

from lib.intelligence.signals import (
    SIGNAL_CATALOG,
    SignalCategory,
    SignalDefinition,
    SignalSeverity,
    _evaluate_anomaly,
    _evaluate_compound,
    _evaluate_threshold,
    _evaluate_trend,
    acknowledge_signal,
    clear_all_signal_state,
    detect_all_client_signals,
    detect_all_signals,
    detect_signals_for_entity,
    evaluate_signal,
    get_active_signals,
    get_signal,
    get_signal_history,
    get_signal_summary,
    get_signals_by_category,
    get_signals_by_entity_type,
    get_signals_by_severity,
    # State management
    update_signal_state,
    validate_signal_catalog,
)

# =============================================================================
# CATALOG VALIDATION TESTS
# =============================================================================


class TestSignalCatalog:
    """Tests for signal catalog structure and validation."""

    def test_catalog_not_empty(self):
        """Catalog should have signals defined."""
        assert len(SIGNAL_CATALOG) >= 20, "Expected at least 20 signals"

    def test_catalog_validation_passes(self):
        """All signals should pass validation."""
        errors = validate_signal_catalog()
        assert errors == [], f"Validation errors: {errors}"

    def test_all_categories_represented(self):
        """All signal categories should have at least one signal."""
        for category in SignalCategory:
            signals = get_signals_by_category(category)
            assert len(signals) > 0, f"No signals for category {category.value}"

    def test_all_entity_types_covered(self):
        """All entity types should have signals."""
        for entity_type in ["client", "project", "person", "portfolio"]:
            signals = get_signals_by_entity_type(entity_type)
            assert len(signals) > 0, f"No signals for entity type {entity_type}"

    def test_get_signal_by_id(self):
        """get_signal should return correct signal."""
        signal = get_signal("sig_client_comm_drop")
        assert signal is not None
        assert signal.id == "sig_client_comm_drop"
        assert signal.entity_type == "client"

    def test_get_nonexistent_signal(self):
        """get_signal should return None for unknown ID."""
        signal = get_signal("sig_does_not_exist")
        assert signal is None

    def test_signal_has_required_fields(self):
        """Every signal should have required fields."""
        for sig_id, signal in SIGNAL_CATALOG.items():
            assert signal.id, f"{sig_id}: missing id"
            assert signal.name, f"{sig_id}: missing name"
            assert signal.conditions, f"{sig_id}: missing conditions"
            assert signal.implied_action, f"{sig_id}: missing implied_action"
            assert signal.evidence_template, f"{sig_id}: missing evidence_template"


# =============================================================================
# THRESHOLD EVALUATOR TESTS
# =============================================================================


class TestThresholdEvaluator:
    """Tests for threshold condition evaluation."""

    @pytest.fixture
    def db_path(self):
        """Get path to live database."""
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_threshold_returns_none_for_nonexistent_entity(self, db_path):
        """Should return None for entity that doesn't exist."""
        condition = {
            "type": "threshold",
            "metric": "active_tasks",
            "operator": "gt",
            "value": 10,
        }
        result = _evaluate_threshold(condition, "client", "nonexistent-id", db_path)
        assert result is None

    def test_threshold_evaluates_client_metric(self, db_path):
        """Should evaluate threshold for real client."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        # Find a client with some tasks
        client = next((c for c in clients if c.get("total_tasks", 0) > 0), None)
        if not client:
            pytest.skip("No clients with tasks")

        # Test threshold that should NOT trigger (very high threshold)
        condition = {
            "type": "threshold",
            "metric": "total_tasks",
            "operator": "gt",
            "value": 999999,
        }
        result = _evaluate_threshold(condition, "client", client["client_id"], db_path)
        assert result is None, "Should not trigger for impossible threshold"


# =============================================================================
# TREND EVALUATOR TESTS
# =============================================================================


class TestTrendEvaluator:
    """Tests for trend condition evaluation."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_trend_returns_none_for_nonexistent_entity(self, db_path):
        """Should return None for entity that doesn't exist."""
        condition = {
            "type": "trend",
            "metric": "communications_count",
            "direction": "declining",
            "consecutive_periods": 3,
        }
        result = _evaluate_trend(condition, "client", "nonexistent-id", db_path)
        assert result is None


# =============================================================================
# ANOMALY EVALUATOR TESTS
# =============================================================================


class TestAnomalyEvaluator:
    """Tests for anomaly condition evaluation."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_anomaly_returns_none_for_nonexistent_entity(self, db_path):
        """Should return None for entity that doesn't exist."""
        condition = {
            "type": "anomaly",
            "metric": "communications_count",
            "deviation_threshold": 2.0,
        }
        result = _evaluate_anomaly(condition, "client", "nonexistent-id", db_path)
        assert result is None


# =============================================================================
# COMPOUND EVALUATOR TESTS
# =============================================================================


class TestCompoundEvaluator:
    """Tests for compound condition evaluation."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_compound_with_no_conditions(self, db_path):
        """Empty conditions should return None."""
        condition = {
            "type": "compound",
            "operator": "all",
            "conditions": [],
        }
        result = _evaluate_compound(condition, "client", "any-id", db_path)
        assert result is None


# =============================================================================
# SIGNAL DETECTION TESTS
# =============================================================================


class TestSignalDetection:
    """Tests for signal detection functions."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_evaluate_signal_wrong_entity_type(self, db_path):
        """Signal should not fire for wrong entity type."""
        signal = get_signal("sig_client_comm_drop")
        # Try to evaluate client signal for a project
        result = evaluate_signal(signal, "project", "some-id", db_path)
        assert result is None

    def test_detect_signals_for_nonexistent_entity(self, db_path):
        """Should return empty list for nonexistent entity."""
        result = detect_signals_for_entity("client", "nonexistent-id-12345", db_path)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_detect_signals_for_real_client(self, db_path):
        """Should run without error for real client."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        client_id = clients[0]["client_id"]
        result = detect_signals_for_entity("client", client_id, db_path)

        assert isinstance(result, list)
        # Each detected signal should have required fields
        for signal in result:
            assert "signal_id" in signal
            assert "severity" in signal
            assert "entity_id" in signal
            assert "evidence" in signal

    def test_detect_signals_sorted_by_severity(self, db_path):
        """Detected signals should be sorted CRITICAL > WARNING > WATCH."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        # Try a few clients to find one with signals
        for client in clients[:10]:
            result = detect_signals_for_entity("client", client["client_id"], db_path)
            if len(result) >= 2:
                # Verify sorting
                severity_order = {"critical": 0, "warning": 1, "watch": 2}
                severities = [severity_order.get(s["severity"], 3) for s in result]
                assert severities == sorted(severities), "Signals should be sorted by severity"
                break


# =============================================================================
# FULL DETECTION TESTS
# =============================================================================


class TestFullDetection:
    """Tests for full database signal detection."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_detect_all_signals_structure(self, db_path):
        """detect_all_signals should return valid structure (quick mode)."""
        # Use quick mode for speed - only evaluates threshold signals
        result = detect_all_signals(db_path, quick=True)

        assert "detected_at" in result
        assert "total_signals" in result
        assert "by_severity" in result
        assert "by_entity_type" in result
        assert "signals" in result

        assert isinstance(result["signals"], list)
        assert isinstance(result["by_severity"], dict)
        assert isinstance(result["by_entity_type"], dict)

    def test_detect_all_signals_runs_without_crash(self, db_path):
        """Full detection should complete without errors (quick mode)."""
        result = detect_all_signals(db_path, quick=True)

        # Should have run against all entity types
        assert "client" in result["by_entity_type"]
        assert "project" in result["by_entity_type"]
        assert "person" in result["by_entity_type"]

        # Total should match sum
        total_from_severity = sum(result["by_severity"].values())
        assert result["total_signals"] == total_from_severity

    def test_detect_all_client_signals(self, db_path):
        """detect_all_client_signals should return list (quick mode)."""
        from lib.intelligence.signals import SignalCategory

        result = detect_all_client_signals(db_path, categories=[SignalCategory.THRESHOLD])

        assert isinstance(result, list)

        # All should be client signals
        for signal in result:
            assert signal["entity_type"] == "client"

    def test_quick_mode_only_threshold_signals(self, db_path):
        """Quick mode should only return threshold signals."""
        result = detect_all_signals(db_path, quick=True)

        # All detected signals should be threshold type
        for signal in result["signals"]:
            assert signal["category"] == "threshold", (
                f"Quick mode returned non-threshold signal: {signal['signal_id']}"
            )


# =============================================================================
# EVIDENCE FORMATTING TESTS
# =============================================================================


class TestEvidenceFormatting:
    """Tests for evidence text formatting."""

    @pytest.fixture
    def db_path(self):
        path = Path(__file__).parent.parent / "data" / "moh_time_os.db"
        if not path.exists():
            pytest.skip("Live database not available")
        return path

    def test_detected_signal_has_evidence_text(self, db_path):
        """Detected signals should have formatted evidence text."""
        from lib.query_engine import QueryEngine

        engine = QueryEngine(db_path)
        clients = engine.client_portfolio_overview()

        if not clients:
            pytest.skip("No clients in database")

        # Run detection and check any signals that fire
        for client in clients[:20]:
            signals = detect_signals_for_entity("client", client["client_id"], db_path)
            for signal in signals:
                assert "evidence_text" in signal
                assert isinstance(signal["evidence_text"], str)
                assert len(signal["evidence_text"]) > 0


# =============================================================================
# SIGNAL STATE TRACKING TESTS
# =============================================================================

from tests.fixtures.fixture_db import create_fixture_db


class TestSignalStateTracking:
    """Tests for signal state persistence and lifecycle management."""

    @pytest.fixture
    def fixture_db(self, tmp_path):
        """Create a fixture database for state tracking tests."""
        db_path = tmp_path / "test_signals.db"
        conn = create_fixture_db(str(db_path))
        conn.close()
        return db_path

    def test_update_state_inserts_new_signal(self, fixture_db):
        """New detected signal should be inserted as active."""
        detected = [
            {
                "signal_id": "sig_test_new",
                "entity_type": "client",
                "entity_id": "test-client-123",
                "severity": "warning",
                "evidence": {"test": True},
            }
        ]

        result = update_signal_state(detected, fixture_db)

        assert len(result["new_signals"]) == 1
        assert result["new_signals"][0]["signal_id"] == "sig_test_new"

        # Verify it's in the database
        active = get_active_signals(entity_id="test-client-123", db_path=fixture_db)
        assert len(active) == 1
        assert active[0]["signal_id"] == "sig_test_new"
        assert active[0]["status"] == "active"

    def test_update_state_increments_evaluation_count(self, fixture_db):
        """Detecting same signal again should increment count."""
        detected = [
            {
                "signal_id": "sig_test_ongoing",
                "entity_type": "client",
                "entity_id": "test-client-456",
                "severity": "warning",
                "evidence": {"test": True},
            }
        ]

        # First detection
        result1 = update_signal_state(detected, fixture_db)
        assert len(result1["new_signals"]) == 1

        # Second detection
        result2 = update_signal_state(detected, fixture_db)
        assert len(result2["new_signals"]) == 0
        assert len(result2["ongoing_signals"]) == 1
        assert result2["ongoing_signals"][0]["evaluation_count"] == 2

    def test_get_active_signals_filters(self, fixture_db):
        """get_active_signals should filter by entity_type and severity."""
        signals = [
            {
                "signal_id": "sig_a",
                "entity_type": "client",
                "entity_id": "c1",
                "severity": "warning",
                "evidence": {},
            },
            {
                "signal_id": "sig_b",
                "entity_type": "client",
                "entity_id": "c2",
                "severity": "critical",
                "evidence": {},
            },
            {
                "signal_id": "sig_c",
                "entity_type": "project",
                "entity_id": "p1",
                "severity": "warning",
                "evidence": {},
            },
        ]
        update_signal_state(signals, fixture_db)

        # Filter by entity_type
        clients = get_active_signals(entity_type="client", db_path=fixture_db)
        assert len(clients) == 2

        # Filter by severity
        critical = get_active_signals(severity="critical", db_path=fixture_db)
        assert len(critical) == 1
        assert critical[0]["signal_id"] == "sig_b"

        # Filter by both
        client_warning = get_active_signals(
            entity_type="client", severity="warning", db_path=fixture_db
        )
        assert len(client_warning) == 1

    def test_get_signal_history(self, fixture_db):
        """get_signal_history should return all signals for entity."""
        signals = [
            {
                "signal_id": "sig_hist1",
                "entity_type": "client",
                "entity_id": "hist-client",
                "severity": "warning",
                "evidence": {},
            },
            {
                "signal_id": "sig_hist2",
                "entity_type": "client",
                "entity_id": "hist-client",
                "severity": "watch",
                "evidence": {},
            },
        ]
        update_signal_state(signals, fixture_db)

        history = get_signal_history("client", "hist-client", db_path=fixture_db)
        assert len(history) == 2
        signal_ids = {h["signal_id"] for h in history}
        assert "sig_hist1" in signal_ids
        assert "sig_hist2" in signal_ids

    def test_acknowledge_signal(self, fixture_db):
        """acknowledge_signal should change status."""
        signals = [
            {
                "signal_id": "sig_ack",
                "entity_type": "client",
                "entity_id": "ack-client",
                "severity": "warning",
                "evidence": {},
            },
        ]
        update_signal_state(signals, fixture_db)

        active = get_active_signals(entity_id="ack-client", db_path=fixture_db)
        assert len(active) == 1
        state_id = active[0]["id"]

        # Acknowledge
        success = acknowledge_signal(state_id, fixture_db)
        assert success is True

        # Should no longer appear in active (status changed to acknowledged)
        active_after = get_active_signals(entity_id="ack-client", db_path=fixture_db)
        assert len(active_after) == 0

        # But should appear in history
        history = get_signal_history("client", "ack-client", db_path=fixture_db)
        assert len(history) == 1
        assert history[0]["status"] == "acknowledged"

    def test_get_signal_summary(self, fixture_db):
        """get_signal_summary should return dashboard counts."""
        signals = [
            {
                "signal_id": "sig_sum1",
                "entity_type": "client",
                "entity_id": "s1",
                "severity": "critical",
                "evidence": {},
            },
            {
                "signal_id": "sig_sum2",
                "entity_type": "client",
                "entity_id": "s2",
                "severity": "warning",
                "evidence": {},
            },
            {
                "signal_id": "sig_sum3",
                "entity_type": "project",
                "entity_id": "s3",
                "severity": "warning",
                "evidence": {},
            },
        ]
        update_signal_state(signals, fixture_db)

        summary = get_signal_summary(fixture_db)

        assert summary["total_active"] == 3
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["warning"] == 2
        assert summary["by_entity_type"]["client"] == 2
        assert summary["by_entity_type"]["project"] == 1
        assert summary["new_since_last_check"] == 3  # All just created

    def test_no_duplicate_active_signals(self, fixture_db):
        """Same signal detected multiple times should not create duplicates."""
        signal = {
            "signal_id": "sig_dedup",
            "entity_type": "client",
            "entity_id": "dedup-client",
            "severity": "warning",
            "evidence": {},
        }

        # Detect 5 times
        for _ in range(5):
            update_signal_state([signal], fixture_db)

        # Should only have 1 active record
        active = get_active_signals(entity_id="dedup-client", db_path=fixture_db)
        assert len(active) == 1
        assert active[0]["evaluation_count"] == 5


class TestSignalClearing:
    """Tests for signal clearing on cooldown expiry."""

    @pytest.fixture
    def fixture_db(self, tmp_path):
        """Create a fixture database for clearing tests."""
        db_path = tmp_path / "test_clearing.db"
        conn = create_fixture_db(str(db_path))
        conn.close()
        return db_path

    def test_signal_not_cleared_within_cooldown(self, fixture_db):
        """Signal should remain active if not detected but within cooldown."""
        # Insert a signal
        signals = [
            {
                "signal_id": "sig_cooldown",
                "entity_type": "client",
                "entity_id": "cool-client",
                "severity": "warning",
                "evidence": {},
            },
        ]
        update_signal_state(signals, fixture_db)

        # Now update with empty list (signal not detected)
        result = update_signal_state([], fixture_db)

        # Should NOT be cleared yet (cooldown not expired)
        active = get_active_signals(entity_id="cool-client", db_path=fixture_db)
        assert len(active) == 1
