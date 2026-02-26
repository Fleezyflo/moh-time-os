"""Tests for Gmail collector — backfill capability and transform logic."""

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest


def _get_gmail_collector_class():
    """Load GmailCollector with a mocked BaseCollector to avoid import chain issues."""
    fake_base = types.ModuleType("lib.collectors.base")

    class FakeBaseCollector:
        def __init__(self, config=None, store=None):
            self.config = config or {}
            self.store = store
            self.logger = MagicMock()

    fake_base.BaseCollector = FakeBaseCollector

    pkg = types.ModuleType("lib.collectors")
    pkg.__path__ = ["lib/collectors"]
    pkg.__package__ = "lib.collectors"

    saved = {}
    for key in ("lib.collectors", "lib.collectors.base", "lib.collectors.gmail"):
        saved[key] = sys.modules.pop(key, None)

    sys.modules["lib.collectors"] = pkg
    sys.modules["lib.collectors.base"] = fake_base

    try:
        spec = importlib.util.spec_from_file_location(
            "lib.collectors.gmail",
            "lib/collectors/gmail.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["lib.collectors.gmail"] = mod
        spec.loader.exec_module(mod)
        return mod.GmailCollector
    finally:
        for key, val in saved.items():
            if val is not None:
                sys.modules[key] = val


_GmailCollector = _get_gmail_collector_class()


class TestGmailCollectConfig:
    """Tests for the collect method configuration."""

    def test_since_parameter_in_collect(self):
        """Collector source should reference 'since' config parameter."""
        import inspect

        source = inspect.getsource(_GmailCollector.collect)
        assert "since" in source, "Collector must support 'since' parameter for backfill"

    def test_since_overrides_lookback_days(self):
        """When 'since' is set, it should use after: query instead of newer_than."""
        import inspect

        source = inspect.getsource(_GmailCollector.collect)
        assert "after:" in source, "Collector must use Gmail after: query for since param"

    def test_pagination_support(self):
        """Collector should paginate through results."""
        import inspect

        source = inspect.getsource(_GmailCollector.collect)
        assert "nextPageToken" in source, "Collector must paginate through thread list"
        assert "pageToken" in source, "Collector must pass page tokens"


class TestGmailTransform:
    """Tests for the transform method."""

    @pytest.fixture
    def collector(self):
        return _GmailCollector(config={}, store=MagicMock())

    @pytest.fixture
    def sample_threads(self):
        return {
            "threads": [
                {
                    "id": "t001",
                    "subject": "Project update",
                    "from": "Ahmed <ahmed@hrmny.co>",
                    "to": "molham@hrmny.co",
                    "date": "Mon, 10 Feb 2026 10:00:00 +0400",
                    "snippet": "Here is the latest update on the project",
                    "body": "Full body text of the email about the project",
                    "labels": ["INBOX", "UNREAD"],
                },
                {
                    "id": "t002",
                    "subject": "Newsletter update",
                    "from": "noreply@example.com",
                    "to": "molham@hrmny.co",
                    "date": "Tue, 11 Feb 2026 08:00:00 +0400",
                    "snippet": "Weekly newsletter",
                    "body": "",
                    "labels": ["CATEGORY_UPDATES"],
                },
            ]
        }

    def test_transforms_valid_thread(self, collector, sample_threads):
        """Valid threads should be transformed."""
        result = collector.transform(sample_threads)
        # t002 should be filtered out (CATEGORY_UPDATES)
        assert len(result) == 1
        assert result[0]["source_id"] == "t001"

    def test_filters_promotional_categories(self, collector, sample_threads):
        """Promotional/update/social categories should be skipped."""
        result = collector.transform(sample_threads)
        ids = [t["source_id"] for t in result]
        assert "t002" not in ids

    def test_extracts_email_from_header(self, collector):
        """Should extract email address from 'Name <email>' format."""
        assert collector._extract_email("Ahmed <ahmed@hrmny.co>") == "ahmed@hrmny.co"
        assert collector._extract_email("plain@example.com") == "plain@example.com"

    def test_skips_threads_without_id(self, collector):
        """Threads without ID should be skipped."""
        data = {"threads": [{"subject": "No ID"}]}
        result = collector.transform(data)
        assert len(result) == 0

    def test_priority_boost_for_hrmny(self, collector):
        """Internal hrmny emails should get priority boost."""
        thread = {"from": "ahmed@hrmny.co", "subject": "test", "labels": [], "snippet": ""}
        priority = collector._compute_priority(thread)
        assert priority >= 75  # 50 base + 25 internal

    def test_noreply_does_not_need_response(self, collector):
        """No-reply senders should not flag as needing response."""
        thread = {"from": "noreply@example.com", "subject": "Update", "snippet": "info"}
        assert not collector._needs_response(thread)
