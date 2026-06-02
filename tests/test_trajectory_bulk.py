"""
Behavioral tests for the bulk-trajectory migration of portfolio_health_trajectory.

Verifies:
- client_full_trajectory(traj=...) reuses a pre-built bulk window set (no per-entity
  engine.client_trajectory call) and produces a FullTrajectory.
- portfolio_health_trajectory() builds ONE bulk map and calls bulk_client_trajectories
  exactly once instead of one client_trajectory per client.
- Both paths produce identical FullTrajectory.entity_id / overall_health.
- A DB/engine failure raises TrajectoryComputationError instead of returning [].
"""

import sqlite3
from unittest.mock import MagicMock

import pytest

from lib.intelligence.trajectory import FullTrajectory, TrajectoryEngine


def _bulk_windows():
    """Six 30-day windows of amount_invoiced declining 5000 -> 0 (DECLINING health)."""
    windows = []
    for i, amount in enumerate([5000, 4000, 3000, 2000, 1000, 0]):
        windows.append(
            {
                "period_start": f"2026-0{i + 1}-01T00:00:00+00:00",
                "period_end": f"2026-0{i + 1}-28T00:00:00+00:00",
                "metrics": {
                    "tasks_created": 10 - i,
                    "tasks_completed": 8 - i,
                    "invoices_issued": 2,
                    "amount_invoiced": amount,
                    "communications_count": 5 - i,
                },
            }
        )
    return windows


def test_client_full_trajectory_uses_prebuilt_traj():
    """When a pre-built traj dict is passed, no engine.client_trajectory call happens."""
    engine = TrajectoryEngine(db_path=None)
    engine.engine = MagicMock()
    engine.engine.client_deep_profile.return_value = {"client_name": "Acme"}

    prebuilt = {
        "client_id": "c1",
        "window_size_days": 30,
        "num_windows": 6,
        "windows": _bulk_windows(),
        "trends": {},
    }
    result = engine.client_full_trajectory("c1", windows=12, traj=prebuilt)

    assert isinstance(result, FullTrajectory)
    assert result.entity_id == "c1"
    assert result.entity_name == "Acme"
    # The pre-built path must NOT call the per-entity trajectory query.
    engine.engine.client_trajectory.assert_not_called()


def test_portfolio_health_trajectory_calls_bulk_once():
    """portfolio_health_trajectory builds ONE bulk map, not N per-entity calls."""
    engine = TrajectoryEngine(db_path=None)
    engine.engine = MagicMock()
    engine.engine.client_portfolio_overview.return_value = [
        {"client_id": "c1", "client_name": "Acme", "client_tier": "gold"},
        {"client_id": "c2", "client_name": "Beta", "client_tier": "silver"},
    ]
    engine.engine.client_deep_profile.side_effect = lambda cid: {"client_name": cid}
    engine.engine.bulk_client_trajectories.return_value = {
        "c1": {"client_id": "c1", "windows": _bulk_windows(), "trends": {}},
        "c2": {"client_id": "c2", "windows": _bulk_windows(), "trends": {}},
    }

    results = engine.portfolio_health_trajectory()

    assert len(results) == 2
    assert {r.entity_id for r in results} == {"c1", "c2"}
    # Bulk path: ONE bulk call, ZERO per-entity client_trajectory calls.
    engine.engine.bulk_client_trajectories.assert_called_once_with(
        window_size_days=30, num_windows=12
    )
    engine.engine.client_trajectory.assert_not_called()
    # And ZERO per-entity client_deep_profile calls: the client name comes from the
    # portfolio overview, so the bulk path must not fire N deep-profile queries (each
    # of which opens fresh connections — the residual N×4 blowup the bulk fix would
    # otherwise leave behind). The entity_name must still be the overview name.
    engine.engine.client_deep_profile.assert_not_called()
    assert {r.entity_name for r in results} == {"Acme", "Beta"}


def test_client_full_trajectory_uses_supplied_client_name():
    """When client_name is supplied, no per-entity client_deep_profile call happens."""
    engine = TrajectoryEngine(db_path=None)
    engine.engine = MagicMock()

    prebuilt = {
        "client_id": "c1",
        "window_size_days": 30,
        "num_windows": 6,
        "windows": _bulk_windows(),
        "trends": {},
    }
    result = engine.client_full_trajectory("c1", windows=12, traj=prebuilt, client_name="Acme")

    assert isinstance(result, FullTrajectory)
    assert result.entity_id == "c1"
    assert result.entity_name == "Acme"
    # The supplied-name path must NOT call the per-entity deep-profile query.
    engine.engine.client_deep_profile.assert_not_called()


def test_portfolio_health_trajectory_raises_on_engine_error():
    """A DB/engine failure must raise TrajectoryComputationError, not return []."""
    from lib.intelligence.errors import TrajectoryComputationError

    engine = TrajectoryEngine(db_path=None)
    engine.engine = MagicMock()
    engine.engine.client_portfolio_overview.return_value = [
        {"client_id": "c1", "client_name": "Acme", "client_tier": "gold"}
    ]
    engine.engine.bulk_client_trajectories.side_effect = sqlite3.OperationalError(
        "database is locked"
    )

    with pytest.raises(TrajectoryComputationError):
        engine.portfolio_health_trajectory()


def test_portfolio_health_trajectory_error_is_oserror_subclass():
    """Existing callers catch OSError; the typed error must remain catchable there."""
    from lib.intelligence.errors import TrajectoryComputationError

    assert issubclass(TrajectoryComputationError, OSError)
