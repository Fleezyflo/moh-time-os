"""Tests for sync schedule config parsing and health checks."""

import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta, timezone

import pytest
import yaml

from lib.sync_health import (
    check_collector_health,
    format_health_report,
    get_enabled_collectors,
    load_schedule,
)


@pytest.fixture
def schedule_file(tmp_path):
    """Create a temporary sync_schedule.yaml."""
    config = {
        "schedules": {
            "asana": {"interval_minutes": 30, "enabled": True, "health_multiplier": 2},
            "gmail": {"interval_minutes": 15, "enabled": True, "health_multiplier": 2},
            "calendar": {"interval_minutes": 60, "enabled": True, "health_multiplier": 2},
            "chat": {"interval_minutes": 60, "enabled": True, "health_multiplier": 2},
            "xero": {"interval_minutes": 360, "enabled": True, "health_multiplier": 2},
            "drive": {"interval_minutes": 720, "enabled": False, "health_multiplier": 2},
        }
    }
    path = tmp_path / "sync_schedule.yaml"
    path.write_text(yaml.dump(config))
    return str(path)


@pytest.fixture
def health_db():
    """Create a test DB with cycle_logs table."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name)
    conn.execute("""
        CREATE TABLE cycle_logs (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    return tmp.name


class TestLoadSchedule:
    """Tests for schedule config loading."""

    def test_loads_valid_config(self, schedule_file):
        schedule = load_schedule(schedule_file)
        assert "schedules" in schedule
        assert "asana" in schedule["schedules"]
        assert schedule["schedules"]["asana"]["interval_minutes"] == 30

    def test_all_enabled_collectors_present(self, schedule_file):
        schedule = load_schedule(schedule_file)
        enabled = [n for n, c in schedule["schedules"].items() if c["enabled"]]
        assert set(enabled) == {"asana", "gmail", "calendar", "chat", "xero"}

    def test_disabled_collectors_parsed(self, schedule_file):
        schedule = load_schedule(schedule_file)
        assert schedule["schedules"]["drive"]["enabled"] is False

    def test_health_multiplier_default(self, tmp_path):
        config = {"schedules": {"test": {"interval_minutes": 10}}}
        path = tmp_path / "sched.yaml"
        path.write_text(yaml.dump(config))
        schedule = load_schedule(str(path))
        assert schedule["schedules"]["test"]["health_multiplier"] == 2

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_schedule("/nonexistent/path/sync_schedule.yaml")

    def test_missing_schedules_key_raises(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("foo: bar")
        with pytest.raises(ValueError, match="schedules"):
            load_schedule(str(path))

    def test_invalid_interval_skipped(self, tmp_path):
        config = {"schedules": {"bad": {"interval_minutes": -1}}}
        path = tmp_path / "sched.yaml"
        path.write_text(yaml.dump(config))
        schedule = load_schedule(str(path))
        assert "bad" not in schedule["schedules"]


class TestGetEnabledCollectors:
    """Tests for get_enabled_collectors."""

    def test_returns_only_enabled(self, schedule_file):
        enabled = get_enabled_collectors(schedule_file)
        assert "drive" not in enabled
        assert "asana" in enabled
        assert len(enabled) == 5


class TestCheckCollectorHealth:
    """Tests for collector health checking."""

    def test_healthy_collector(self, schedule_file, health_db):
        # Insert a recent run for asana (within 2x30 = 60 minutes)
        now = datetime.now(UTC)
        recent = (now - timedelta(minutes=20)).isoformat()

        conn = sqlite3.connect(health_db)
        conn.execute(
            "INSERT INTO cycle_logs (source, status, completed_at) VALUES (?, ?, ?)",
            ("asana", "success", recent),
        )
        conn.commit()
        conn.close()

        report = check_collector_health(health_db, schedule_file, now=now)
        assert "asana" in report["healthy"]

    def test_stale_collector(self, schedule_file, health_db):
        # Insert an old run for gmail (> 2x15 = 30 minutes ago)
        now = datetime.now(UTC)
        old = (now - timedelta(minutes=120)).isoformat()

        conn = sqlite3.connect(health_db)
        conn.execute(
            "INSERT INTO cycle_logs (source, status, completed_at) VALUES (?, ?, ?)",
            ("gmail", "success", old),
        )
        conn.commit()
        conn.close()

        report = check_collector_health(health_db, schedule_file, now=now)
        stale_names = [s["name"] for s in report["stale"]]
        assert "gmail" in stale_names

    def test_never_run_collector(self, schedule_file, health_db):
        now = datetime.now(UTC)
        report = check_collector_health(health_db, schedule_file, now=now)
        # All enabled collectors should be in never_run since DB is empty
        assert set(report["never_run"]) == {"asana", "gmail", "calendar", "chat", "xero"}

    def test_disabled_collector(self, schedule_file, health_db):
        now = datetime.now(UTC)
        report = check_collector_health(health_db, schedule_file, now=now)
        assert "drive" in report["disabled"]

    def test_failed_runs_ignored(self, schedule_file, health_db):
        # Only failed runs — collector should be in never_run
        now = datetime.now(UTC)
        recent = (now - timedelta(minutes=5)).isoformat()

        conn = sqlite3.connect(health_db)
        conn.execute(
            "INSERT INTO cycle_logs (source, status, completed_at) VALUES (?, ?, ?)",
            ("asana", "failed", recent),
        )
        conn.commit()
        conn.close()

        report = check_collector_health(health_db, schedule_file, now=now)
        assert "asana" in report["never_run"]

    def test_stale_includes_timing_details(self, schedule_file, health_db):
        now = datetime.now(UTC)
        # Xero: interval=360, multiplier=2, threshold=720m. Use 800m to be clearly stale.
        old = (now - timedelta(minutes=800)).isoformat()

        conn = sqlite3.connect(health_db)
        conn.execute(
            "INSERT INTO cycle_logs (source, status, completed_at) VALUES (?, ?, ?)",
            ("xero", "success", old),
        )
        conn.commit()
        conn.close()

        report = check_collector_health(health_db, schedule_file, now=now)
        stale_xero = next(s for s in report["stale"] if s["name"] == "xero")
        assert stale_xero["expected_interval_minutes"] == 360
        assert stale_xero["stale_minutes"] >= 799

    def test_report_has_all_fields(self, schedule_file, health_db):
        report = check_collector_health(health_db, schedule_file)
        assert "healthy" in report
        assert "stale" in report
        assert "never_run" in report
        assert "disabled" in report
        assert "checked_at" in report


class TestFormatHealthReport:
    """Tests for report formatting."""

    def test_format_includes_stale_details(self):
        report = {
            "healthy": ["asana"],
            "stale": [
                {
                    "name": "gmail",
                    "last_run": "2026-01-01T00:00:00",
                    "expected_interval_minutes": 15,
                    "stale_minutes": 120,
                }
            ],
            "never_run": ["chat"],
            "disabled": ["drive"],
            "checked_at": "2026-02-20T12:00:00+00:00",
        }
        text = format_health_report(report)
        assert "gmail" in text
        assert "120m ago" in text
        assert "asana" in text
        assert "chat" in text
        assert "drive" in text


class TestLaunchdPlist:
    """Verify launchd plist is correctly configured."""

    def test_plist_exists(self):
        from pathlib import Path

        plist = Path(__file__).parent.parent / "com.mohtimeos.api.plist"
        assert plist.exists(), "LaunchAgent plist missing"

    def test_plist_has_required_keys(self):
        import xml.etree.ElementTree as ET
        from pathlib import Path

        plist = Path(__file__).parent.parent / "com.mohtimeos.api.plist"
        tree = ET.parse(plist)  # nosec B314  # noqa: S314
        root = tree.getroot()
        # Find dict element
        dict_elem = root.find("dict")
        keys = [k.text for k in dict_elem.findall("key")]
        assert "Label" in keys
        assert "ProgramArguments" in keys
        assert "RunAtLoad" in keys
        assert "KeepAlive" in keys

    def test_plist_label_correct(self):
        import xml.etree.ElementTree as ET
        from pathlib import Path

        plist = Path(__file__).parent.parent / "com.mohtimeos.api.plist"
        tree = ET.parse(plist)  # nosec B314  # noqa: S314
        root = tree.getroot()
        dict_elem = root.find("dict")
        children = list(dict_elem)
        # First key should be Label, next sibling is the value
        for i, child in enumerate(children):
            if child.tag == "key" and child.text == "Label":
                label_value = children[i + 1].text
                assert label_value == "com.mohtimeos.api"
                break
