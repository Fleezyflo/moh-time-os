"""
Tests for the daemon's intelligence-mode env switch (MOH_INTELLIGENCE_FULL_MODE).

Verifies:
- Default (unset) -> detect_all_signals called with quick=True (fast path preserved).
- MOH_INTELLIGENCE_FULL_MODE=1 -> detect_all_signals called with quick=False
  (full catalog: TREND/ANOMALY/COMPOUND signals evaluated).

The detection internals are mocked; only the quick= argument the daemon passes
is asserted, so no real DB or trajectory work runs.
"""

from unittest.mock import MagicMock

import pytest


def _make_daemon():
    """Build a TimeOSDaemon without running its scheduler/init side effects."""
    from lib.daemon import TimeOSDaemon

    daemon = TimeOSDaemon.__new__(TimeOSDaemon)
    daemon.logger = MagicMock()
    return daemon


@pytest.fixture
def patched_detection(monkeypatch):
    """Patch signals + proposal service so _handle_intelligence does no real work."""
    detect = MagicMock(return_value={"signals": []})
    update = MagicMock(return_value={})
    monkeypatch.setattr("lib.intelligence.signals.detect_all_signals", detect)
    monkeypatch.setattr("lib.intelligence.signals.update_signal_state", update)
    # ProposalService is imported inside the method; patch where it is defined.
    monkeypatch.setattr(
        "lib.v4.proposal_service.ProposalService",
        MagicMock(
            return_value=MagicMock(generate_proposals_from_signals=MagicMock(return_value={}))
        ),
    )
    return detect


def test_default_mode_is_quick(monkeypatch, patched_detection):
    """With MOH_INTELLIGENCE_FULL_MODE unset, the daemon runs quick=True (default OFF)."""
    monkeypatch.delenv("MOH_INTELLIGENCE_FULL_MODE", raising=False)
    daemon = _make_daemon()

    daemon._handle_intelligence()

    assert patched_detection.call_count == 1
    _args, kwargs = patched_detection.call_args
    assert kwargs.get("quick") is True


def test_full_mode_env_runs_quick_false(monkeypatch, patched_detection):
    """MOH_INTELLIGENCE_FULL_MODE=1 makes the daemon run the full catalog (quick=False)."""
    monkeypatch.setenv("MOH_INTELLIGENCE_FULL_MODE", "1")
    daemon = _make_daemon()

    daemon._handle_intelligence()

    assert patched_detection.call_count == 1
    _args, kwargs = patched_detection.call_args
    assert kwargs.get("quick") is False


def test_explicit_zero_is_quick(monkeypatch, patched_detection):
    """MOH_INTELLIGENCE_FULL_MODE=0 explicitly keeps the quick fast path (default OFF)."""
    monkeypatch.setenv("MOH_INTELLIGENCE_FULL_MODE", "0")
    daemon = _make_daemon()

    daemon._handle_intelligence()

    _args, kwargs = patched_detection.call_args
    assert kwargs.get("quick") is True
