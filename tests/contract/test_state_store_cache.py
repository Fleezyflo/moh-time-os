"""
Contract Test — StateStore cache operations.

Ensures:
- set_cache does not raise NameError (Path must be imported)
- Cache files are written to the expected location
"""


class TestStateStoreCacheContract:
    """Contract tests for StateStore cache operations."""

    def test_set_cache_no_name_error(self, tmp_path, monkeypatch):
        """
        set_cache must not raise NameError for Path.

        This is a regression test for the bug where Path was used
        but not imported in lib/state_store.py.
        """
        # Set up temp home to isolate test
        monkeypatch.setenv("MOH_TIME_OS_HOME", str(tmp_path))

        # Force reimport of paths module
        import lib.paths

        monkeypatch.setattr(lib.paths, "app_home", lambda: tmp_path)
        monkeypatch.setattr(lib.paths, "data_dir", lambda: tmp_path / "data")
        monkeypatch.setattr(lib.paths, "db_path", lambda: tmp_path / "data" / "test.db")

        # Create data directory
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)

        # Import StateStore fresh (it's a singleton, so we need to reset it)
        import lib.state_store as ss

        # Reset singleton for clean test
        ss.StateStore._instance = None

        # This should NOT raise NameError: name 'Path' is not defined
        store = ss.StateStore(db_path=str(tmp_path / "data" / "test.db"))

        # Call set_cache - this is where the NameError occurred
        store.set_cache("test_key", {"foo": "bar"})

        # Verify cache file was written
        cache_dir = tmp_path / "data" / "cache"
        cache_file = cache_dir / "test_key.json"
        assert cache_file.exists(), f"Cache file should exist at {cache_file}"

    def test_set_cache_writes_valid_json(self, tmp_path, monkeypatch):
        """Cache files must contain valid JSON with value and timestamp."""
        import json

        monkeypatch.setenv("MOH_TIME_OS_HOME", str(tmp_path))

        import lib.paths

        monkeypatch.setattr(lib.paths, "app_home", lambda: tmp_path)
        monkeypatch.setattr(lib.paths, "data_dir", lambda: tmp_path / "data")
        monkeypatch.setattr(lib.paths, "db_path", lambda: tmp_path / "data" / "test.db")

        (tmp_path / "data").mkdir(parents=True, exist_ok=True)

        import lib.state_store as ss

        ss.StateStore._instance = None

        store = ss.StateStore(db_path=str(tmp_path / "data" / "test.db"))

        test_value = {"items": [1, 2, 3], "count": 3}
        store.set_cache("json_test", test_value)

        cache_file = tmp_path / "data" / "cache" / "json_test.json"
        assert cache_file.exists()

        with open(cache_file) as f:
            data = json.load(f)

        assert "value" in data, "Cache file must contain 'value' key"
        assert "timestamp" in data, "Cache file must contain 'timestamp' key"
        assert data["value"] == test_value

    def test_path_import_exists_in_state_store(self):
        """Source code must import Path from pathlib."""
        import inspect

        import lib.state_store as ss

        source = inspect.getsource(ss)

        assert (
            "from pathlib import Path" in source
        ), "lib/state_store.py must import Path from pathlib"
