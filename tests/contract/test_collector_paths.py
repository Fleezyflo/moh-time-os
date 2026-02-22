"""
Contract Tests — CollectorOrchestrator path resolution.

Ensures:
- CollectorOrchestrator can be imported/constructed without missing imports
- sources.yaml path resolves via lib.paths.config_dir(), not hardcoded paths
"""

from unittest import mock


class TestCollectorOrchestratorImport:
    """Test CollectorOrchestrator can be imported without errors."""

    def test_import_succeeds(self):
        """Import must not raise NameError or ImportError."""
        from lib.collectors.orchestrator import CollectorOrchestrator

        assert CollectorOrchestrator is not None


class TestCollectorOrchestratorPathResolution:
    """Test that CollectorOrchestrator uses lib.paths for config resolution."""

    def test_uses_paths_config_dir_for_sources_yaml(self, tmp_path, monkeypatch):
        """
        sources.yaml must resolve via paths.config_dir().

        Strategy: set MOH_TIME_OS_HOME to temp dir, create sources.yaml there,
        verify CollectorOrchestrator reads from that location.
        """
        # Set up temp home
        monkeypatch.setenv("MOH_TIME_OS_HOME", str(tmp_path))

        # Create config dir and sources.yaml with marker content
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        sources_file = config_dir / "sources.yaml"
        sources_file.write_text("sources:\n  _test_marker: {enabled: false}\n")

        # Force reimport of paths module to pick up new env var
        import lib.paths

        monkeypatch.setattr(lib.paths, "app_home", lambda: tmp_path)
        monkeypatch.setattr(lib.paths, "config_dir", lambda: config_dir)

        # Import and construct - should read from our temp sources.yaml
        from lib.collectors.orchestrator import CollectorOrchestrator

        # Mock the store to avoid DB dependencies
        with mock.patch("lib.collectors.orchestrator.get_store"):
            with mock.patch("lib.collectors.orchestrator.AsanaCollector"):
                with mock.patch("lib.collectors.orchestrator.CalendarCollector"):
                    with mock.patch("lib.collectors.orchestrator.GmailCollector"):
                        with mock.patch("lib.collectors.orchestrator.TasksCollector"):
                            with mock.patch("lib.collectors.orchestrator.XeroCollector"):
                                orch = CollectorOrchestrator()

        # Verify it read from our marker file
        assert "_test_marker" in orch.config.get(
            "sources", {}
        ), "CollectorOrchestrator did not read sources.yaml from paths.config_dir()"

    def test_config_path_defaults_to_paths_config_dir(self, tmp_path, monkeypatch):
        """self.config_path must default to str(paths.config_dir())."""
        monkeypatch.setenv("MOH_TIME_OS_HOME", str(tmp_path))

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        import lib.paths

        monkeypatch.setattr(lib.paths, "config_dir", lambda: config_dir)

        from lib.collectors.orchestrator import CollectorOrchestrator

        with mock.patch("lib.collectors.orchestrator.get_store"):
            with mock.patch("lib.collectors.orchestrator.AsanaCollector"):
                with mock.patch("lib.collectors.orchestrator.CalendarCollector"):
                    with mock.patch("lib.collectors.orchestrator.GmailCollector"):
                        with mock.patch("lib.collectors.orchestrator.TasksCollector"):
                            with mock.patch("lib.collectors.orchestrator.XeroCollector"):
                                orch = CollectorOrchestrator()

        assert orch.config_path == str(
            config_dir
        ), f"config_path should default to paths.config_dir(), got {orch.config_path}"

    def test_no_hardcoded_path_in_source(self):
        """Source code must not contain Path(self.config_path) for sources.yaml."""
        import inspect

        from lib.collectors.orchestrator import CollectorOrchestrator

        source = inspect.getsource(CollectorOrchestrator._load_config)

        assert (
            "Path(self.config_path)" not in source
        ), "_load_config must use paths.config_dir(), not Path(self.config_path)"
        assert (
            "paths.config_dir()" in source
        ), "_load_config must use paths.config_dir() for sources.yaml resolution"
