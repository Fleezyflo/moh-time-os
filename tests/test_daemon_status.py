"""Tests for TimeOSDaemon.status() orphan-job filtering (WS1 S1.3).

The daemon was rearchitected from a subprocess scheduler (jobs: autonomous,
backup) to an in-process 8-stage pipeline. The persisted daemon_state.json can
still contain those orphan keys. _load_state filters them, but status() returned
the raw dict, leaking consecutive_failures=168 for a job the current daemon never
runs. These tests pin the filter into status().
"""

import importlib
import json

import pytest


@pytest.fixture
def daemon_home(tmp_path, monkeypatch):
    """Point lib.paths at a temp home so data_dir() resolves into tmp_path."""
    monkeypatch.setenv("MOH_TIME_OS_HOME", str(tmp_path))
    import lib.paths as paths

    importlib.reload(paths)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    yield data_dir
    # Restore lib.paths to the unpatched env for other tests.
    monkeypatch.delenv("MOH_TIME_OS_HOME", raising=False)
    importlib.reload(paths)


def _write_state(data_dir, jobs: dict):
    state_file = data_dir / "daemon_state.json"
    state_file.write_text(
        json.dumps(
            {"jobs": jobs, "updated_at": "2026-05-21T22:04:00+00:00"},
            indent=2,
        )
    )
    return state_file


def test_status_drops_orphan_jobs(daemon_home):
    """status() must not return jobs the current daemon does not register."""
    from lib.daemon import TimeOSDaemon

    _write_state(
        daemon_home,
        {
            "autonomous": {"consecutive_failures": 168, "total_runs": 2661},
            "backup": {"consecutive_failures": 0, "total_runs": 10},
            "collect": {"consecutive_failures": 0, "total_runs": 5},
        },
    )

    status = TimeOSDaemon.status()

    assert "autonomous" not in status["jobs"]
    assert "backup" not in status["jobs"]
    assert "collect" in status["jobs"]


def test_status_keeps_all_eight_registered_stages(daemon_home):
    """All 8 in-process stages survive the filter when present in state."""
    from lib.daemon import TimeOSDaemon

    eight = [
        "collect",
        "lane_assignment",
        "truth_cycle",
        "detection",
        "intelligence",
        "snapshot",
        "morning_brief",
        "notify",
    ]
    _write_state(daemon_home, {name: {"consecutive_failures": 0} for name in eight})

    status = TimeOSDaemon.status()

    assert set(status["jobs"].keys()) == set(eight)


def test_status_preserves_top_level_fields(daemon_home):
    """Filtering jobs must not drop running/pid/state_updated metadata."""
    from lib.daemon import TimeOSDaemon

    _write_state(daemon_home, {"collect": {"consecutive_failures": 0}})

    status = TimeOSDaemon.status()

    assert status["running"] is False
    assert status["pid"] is None
    assert status["state_updated"] == "2026-05-21T22:04:00+00:00"


def test_status_with_no_state_file_returns_empty_jobs(daemon_home):
    """No state file => empty jobs dict, no crash."""
    from lib.daemon import TimeOSDaemon

    status = TimeOSDaemon.status()

    assert status["jobs"] == {}
    assert status["running"] is False
