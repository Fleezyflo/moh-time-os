"""S3.5: TimeOSDaemon._save_state must write atomically (temp file + replace)
so a crash mid-write cannot corrupt daemon_state.json."""

import json
from unittest.mock import patch

from lib import daemon as daemon_mod


def _make_daemon():
    """Construct a daemon without running its scheduler/loaders."""
    d = daemon_mod.TimeOSDaemon.__new__(daemon_mod.TimeOSDaemon)
    d.job_states = {}
    import logging

    d.logger = logging.getLogger("test-daemon")
    return d


def test_save_state_writes_via_temp_then_replace(tmp_path):
    state_path = tmp_path / "daemon_state.json"
    d = _make_daemon()

    with patch.object(daemon_mod, "_state_file", return_value=state_path):
        d._save_state()

    # Final file exists and is valid JSON; no leftover temp file.
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "jobs" in data and "updated_at" in data
    assert not (tmp_path / "daemon_state.json.tmp").exists()


def test_save_state_crash_before_replace_keeps_original(tmp_path):
    state_path = tmp_path / "daemon_state.json"
    state_path.write_text('{"jobs": {"prior": {}}, "updated_at": "old"}')
    d = _make_daemon()

    # Simulate a crash during the JSON write to the temp file.
    with (
        patch.object(daemon_mod, "_state_file", return_value=state_path),
        patch.object(daemon_mod.json, "dump", side_effect=OSError("disk full")),
    ):
        d._save_state()  # _save_state swallows OSError and logs a warning

    # Original file is untouched (the corrupt temp never replaced it).
    assert json.loads(state_path.read_text()) == {
        "jobs": {"prior": {}},
        "updated_at": "old",
    }
