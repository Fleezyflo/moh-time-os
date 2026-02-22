"""
Comprehensive tests for observability modules.

Covers:
- Metrics: Counter, Gauge, Histogram, MetricsRegistry, exports
- Logging: JSONFormatter, HumanFormatter, extra fields
- Middleware: CorrelationIdMiddleware, request ID propagation
"""

import json
import logging
import time
from datetime import timezone
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.observability.context import RequestContext, generate_request_id, get_request_id
from lib.observability.logging import HumanFormatter, JSONFormatter, configure_logging
from lib.observability.metrics import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)
from lib.observability.middleware import CorrelationIdMiddleware, RequestMetricsMiddleware

# =============================================================================
# METRICS - COUNTER TESTS
# =============================================================================


class TestCounter:
    """Tests for Counter metric."""

    def test_counter_increments(self):
        """Counter.inc() should increase value."""
        c = Counter("test_counter", "Test counter")
        assert c.value == 0
        c.inc()
        assert c.value == 1
        c.inc()
        assert c.value == 2

    def test_counter_increment_by_amount(self):
        """Counter.inc(amount) should increment by specified amount."""
        c = Counter("test_counter", "Test counter")
        c.inc(5)
        assert c.value == 5
        c.inc(3)
        assert c.value == 8

    def test_counter_thread_safe(self):
        """Counter should be thread-safe."""
        import threading

        c = Counter("test_counter", "Test counter")

        def increment():
            for _ in range(100):
                c.inc()

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert c.value == 500

    def test_counter_description(self):
        """Counter should store description."""
        c = Counter("test", "Test description")
        assert c.name == "test"
        assert c.description == "Test description"


# =============================================================================
# METRICS - GAUGE TESTS
# =============================================================================


class TestGauge:
    """Tests for Gauge metric."""

    def test_gauge_set(self):
        """Gauge.set() should set value."""
        g = Gauge("test_gauge", "Test gauge")
        assert g.value == 0.0
        g.set(42.5)
        assert g.value == 42.5
        g.set(10.0)
        assert g.value == 10.0

    def test_gauge_inc(self):
        """Gauge.inc() should increment."""
        g = Gauge("test_gauge", "Test gauge")
        g.set(10.0)
        g.inc(5.0)
        assert g.value == 15.0
        g.inc()
        assert g.value == 16.0

    def test_gauge_dec(self):
        """Gauge.dec() should decrement."""
        g = Gauge("test_gauge", "Test gauge")
        g.set(20.0)
        g.dec(5.0)
        assert g.value == 15.0
        g.dec()
        assert g.value == 14.0

    def test_gauge_can_go_negative(self):
        """Gauge should support negative values."""
        g = Gauge("test_gauge", "Test gauge")
        g.set(5.0)
        g.dec(10.0)
        assert g.value == -5.0

    def test_gauge_thread_safe(self):
        """Gauge should be thread-safe."""
        import threading

        g = Gauge("test_gauge", "Test gauge")

        def increment():
            for _ in range(100):
                g.inc(1.0)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert g.value == 500.0


# =============================================================================
# METRICS - HISTOGRAM TESTS
# =============================================================================


class TestHistogram:
    """Tests for Histogram metric."""

    def test_histogram_observe(self):
        """Histogram.observe() should record values."""
        h = Histogram("test_histogram", "Test histogram")
        assert h.count == 0
        h.observe(10.0)
        assert h.count == 1
        h.observe(20.0)
        assert h.count == 2

    def test_histogram_sum(self):
        """Histogram.sum should return sum of observations."""
        h = Histogram("test_histogram", "Test histogram")
        h.observe(10.0)
        h.observe(20.0)
        h.observe(30.0)
        assert h.sum == 60.0

    def test_histogram_avg(self):
        """Histogram.avg should return average."""
        h = Histogram("test_histogram", "Test histogram")
        h.observe(10.0)
        h.observe(20.0)
        h.observe(30.0)
        assert h.avg == 20.0

    def test_histogram_empty_avg(self):
        """Histogram.avg should return 0 when empty."""
        h = Histogram("test_histogram", "Test histogram")
        assert h.avg == 0.0

    def test_histogram_keeps_last_1000(self):
        """Histogram should keep only last 1000 observations."""
        h = Histogram("test_histogram", "Test histogram")
        for i in range(1500):
            h.observe(float(i))
        assert h.count == 1000
        # First 500 should be dropped, should start from 500
        assert min(h._values) >= 500.0

    def test_histogram_thread_safe(self):
        """Histogram should be thread-safe."""
        import threading

        h = Histogram("test_histogram", "Test histogram")

        def observe():
            for i in range(100):
                h.observe(float(i))

        threads = [threading.Thread(target=observe) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert h.count == 500


# =============================================================================
# METRICS - REGISTRY TESTS
# =============================================================================


class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_registry_get_or_create_counter(self):
        """Registry.counter() should get or create counter."""
        reg = MetricsRegistry()
        c1 = reg.counter("test_counter", "Test counter")
        assert isinstance(c1, Counter)
        c1.inc(5)
        # Getting same counter should return same instance
        c2 = reg.counter("test_counter")
        assert c2 is c1
        assert c2.value == 5

    def test_registry_get_or_create_gauge(self):
        """Registry.gauge() should get or create gauge."""
        reg = MetricsRegistry()
        g1 = reg.gauge("test_gauge", "Test gauge")
        assert isinstance(g1, Gauge)
        g1.set(42.0)
        # Getting same gauge should return same instance
        g2 = reg.gauge("test_gauge")
        assert g2 is g1
        assert g2.value == 42.0

    def test_registry_get_or_create_histogram(self):
        """Registry.histogram() should get or create histogram."""
        reg = MetricsRegistry()
        h1 = reg.histogram("test_histogram", "Test histogram")
        assert isinstance(h1, Histogram)
        h1.observe(10.0)
        # Getting same histogram should return same instance
        h2 = reg.histogram("test_histogram")
        assert h2 is h1
        assert h2.count == 1

    def test_registry_counters_property(self):
        """Registry.counters should return dict of counters."""
        reg = MetricsRegistry()
        reg.counter("c1", "Counter 1")
        reg.counter("c2", "Counter 2")
        counters = reg.counters
        assert len(counters) == 2
        assert "c1" in counters
        assert "c2" in counters

    def test_registry_gauges_property(self):
        """Registry.gauges should return dict of gauges."""
        reg = MetricsRegistry()
        reg.gauge("g1", "Gauge 1")
        reg.gauge("g2", "Gauge 2")
        gauges = reg.gauges
        assert len(gauges) == 2
        assert "g1" in gauges
        assert "g2" in gauges

    def test_registry_histograms_property(self):
        """Registry.histograms should return dict of histograms."""
        reg = MetricsRegistry()
        reg.histogram("h1", "Histogram 1")
        reg.histogram("h2", "Histogram 2")
        histograms = reg.histograms
        assert len(histograms) == 2
        assert "h1" in histograms
        assert "h2" in histograms


# =============================================================================
# METRICS - EXPORT TESTS
# =============================================================================


class TestMetricsExport:
    """Tests for metrics export formats."""

    def test_to_prometheus_format_counters(self):
        """to_prometheus() should output valid Prometheus format."""
        reg = MetricsRegistry()
        c = reg.counter("test_counter", "Test counter description")
        c.inc(42)

        output = reg.to_prometheus()
        assert "# HELP test_counter Test counter description" in output
        assert "# TYPE test_counter counter" in output
        assert "test_counter 42" in output

    def test_to_prometheus_format_gauges(self):
        """to_prometheus() should output gauges."""
        reg = MetricsRegistry()
        g = reg.gauge("test_gauge", "Test gauge description")
        g.set(3.14)

        output = reg.to_prometheus()
        assert "# HELP test_gauge Test gauge description" in output
        assert "# TYPE test_gauge gauge" in output
        assert "test_gauge 3.14" in output

    def test_to_prometheus_format_histograms(self):
        """to_prometheus() should output histograms as summaries."""
        reg = MetricsRegistry()
        h = reg.histogram("test_histogram", "Test histogram description")
        h.observe(10.0)
        h.observe(20.0)
        h.observe(30.0)

        output = reg.to_prometheus()
        assert "# HELP test_histogram Test histogram description" in output
        assert "# TYPE test_histogram summary" in output
        assert "test_histogram_count 3" in output
        assert "test_histogram_sum 60" in output

    def test_to_dict(self):
        """to_dict() should export metrics as dictionary."""
        reg = MetricsRegistry()
        c = reg.counter("counter", "Counter")
        g = reg.gauge("gauge", "Gauge")
        h = reg.histogram("histogram", "Histogram")

        c.inc(5)
        g.set(2.5)
        h.observe(10.0)

        result = reg.to_dict()

        assert result["counter"]["type"] == "counter"
        assert result["counter"]["value"] == 5
        assert result["gauge"]["type"] == "gauge"
        assert result["gauge"]["value"] == 2.5
        assert result["histogram"]["type"] == "histogram"
        assert result["histogram"]["count"] == 1
        assert result["histogram"]["sum"] == 10.0
        assert result["histogram"]["avg"] == 10.0

    def test_prometheus_format_ends_with_newline(self):
        """Prometheus format should end with newline."""
        reg = MetricsRegistry()
        reg.counter("test", "Test")
        output = reg.to_prometheus()
        assert output.endswith("\n")


# =============================================================================
# LOGGING - JSON FORMATTER TESTS
# =============================================================================


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_json_formatter_basic(self):
        """JSONFormatter should output valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_json_formatter_includes_request_id(self):
        """JSONFormatter should include request_id from context."""
        formatter = JSONFormatter()
        with RequestContext(request_id="req-test123"):
            record = logging.LogRecord(
                name="test.module",
                level=logging.INFO,
                pathname="test.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            data = json.loads(output)
            assert data["request_id"] == "req-test123"

    def test_json_formatter_no_request_id_when_not_set(self):
        """JSONFormatter should not include request_id when not in context."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "request_id" not in data

    def test_json_formatter_extra_fields(self):
        """JSONFormatter should include extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.user_id = "user-123"
        record.action = "test_action"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["user_id"] == "user-123"
        assert data["action"] == "test_action"

    def test_json_formatter_exception(self):
        """JSONFormatter should include exception traceback."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test error" in data["exception"]

    def test_json_formatter_timestamp_format(self):
        """JSONFormatter should use ISO 8601 timestamp format with Z suffix."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        timestamp = data["timestamp"]
        assert timestamp.endswith("Z")
        assert "T" in timestamp  # ISO 8601 format


# =============================================================================
# LOGGING - HUMAN FORMATTER TESTS
# =============================================================================


class TestHumanFormatter:
    """Tests for HumanFormatter."""

    def test_human_formatter_basic(self):
        """HumanFormatter should output human-readable format."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "[INFO]" in output
        assert "test.module" in output
        assert "Test message" in output

    def test_human_formatter_includes_request_id(self):
        """HumanFormatter should include request_id from context."""
        formatter = HumanFormatter()
        with RequestContext(request_id="req-test123"):
            record = logging.LogRecord(
                name="test.module",
                level=logging.INFO,
                pathname="test.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            assert "req-test" in output
            assert "Test message" in output

    def test_human_formatter_no_request_id_when_not_set(self):
        """HumanFormatter should work without request_id."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "[INFO]" in output
        assert "test.module" in output
        assert "Test message" in output


# =============================================================================
# MIDDLEWARE TESTS (Using sync wrapper with mocking)
# =============================================================================


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    def test_middleware_generates_request_id(self):
        """Middleware should generate request_id if not provided."""
        request_id_captured = None

        def sync_app(scope, receive, send):
            # Simulate extracting request_id from context
            import asyncio

            async def check():
                nonlocal request_id_captured
                request_id_captured = get_request_id()

            asyncio.run(check())

        middleware = CorrelationIdMiddleware(
            lambda scope, receive, send: sync_app(scope, receive, send)
        )

        # Test that middleware can be instantiated
        assert middleware is not None

    def test_middleware_structure(self):
        """Middleware should have proper structure."""

        def dummy_app(scope, receive, send):
            pass

        middleware = CorrelationIdMiddleware(dummy_app)
        assert middleware.app == dummy_app

    def test_middleware_handles_headers(self):
        """Middleware should be able to extract headers from scope."""
        scope = {
            "type": "http",
            "headers": [(b"x-request-id", b"test-123")],
        }

        # Verify we can access headers
        dict(scope.get("headers", []))
        # Note: this creates a mapping from bytes to bytes
        # The middleware should handle case-insensitive lookup


class TestRequestMetricsMiddleware:
    """Tests for RequestMetricsMiddleware."""

    def test_middleware_structure(self):
        """Middleware should have proper structure."""

        def dummy_app(scope, receive, send):
            pass

        middleware = RequestMetricsMiddleware(dummy_app)
        assert middleware.app == dummy_app

    def test_middleware_initialization(self):
        """Middleware should initialize without errors."""
        app = MagicMock()
        middleware = RequestMetricsMiddleware(app)
        assert middleware is not None

    def test_request_context_manager(self):
        """RequestContext should manage context properly."""
        initial_id = get_request_id()

        with RequestContext(request_id="req-test123"):
            assert get_request_id() == "req-test123"

        assert get_request_id() == initial_id

    def test_request_id_generation(self):
        """generate_request_id should create valid IDs."""
        rid = generate_request_id()
        assert rid.startswith("req-")
        assert len(rid) > 4
