"""
Minimal metrics collection for observability.

Provides counters and timing metrics without external dependencies.
Metrics are exposed via /api/metrics endpoint and can be scraped by Prometheus.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Counter:
    """Thread-safe counter metric."""

    name: str
    description: str
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc(self, amount: int = 1) -> None:
        """Increment the counter."""
        with self._lock:
            self._value += amount

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


@dataclass
class Gauge:
    """Thread-safe gauge metric."""

    name: str
    description: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, value: float) -> None:
        """Set the gauge value."""
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class Histogram:
    """Simple histogram for timing metrics."""

    name: str
    description: str
    _values: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            self._values.append(value)
            # Keep only last 1000 observations
            if len(self._values) > 1000:
                self._values = self._values[-1000:]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._values)

    @property
    def sum(self) -> float:
        with self._lock:
            return sum(self._values) if self._values else 0.0

    @property
    def avg(self) -> float:
        with self._lock:
            return sum(self._values) / len(self._values) if self._values else 0.0


class MetricsRegistry:
    """Central registry for all metrics."""

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    @property
    def counters(self) -> dict[str, Counter]:
        """Get all counters."""
        with self._lock:
            return dict(self._counters)

    @property
    def gauges(self) -> dict[str, Gauge]:
        """Get all gauges."""
        with self._lock:
            return dict(self._gauges)

    @property
    def histograms(self) -> dict[str, Histogram]:
        """Get all histograms."""
        with self._lock:
            return dict(self._histograms)

    def counter(self, name: str, description: str = "") -> Counter:
        """Get or create a counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description)
            return self._counters[name]

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Get or create a gauge."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description)
            return self._gauges[name]

    def histogram(self, name: str, description: str = "") -> Histogram:
        """Get or create a histogram."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description)
            return self._histograms[name]

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []
        with self._lock:
            # Counters
            for name in sorted(self._counters.keys()):
                c = self._counters[name]
                if c.description:
                    lines.append(f"# HELP {name} {c.description}")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {c.value}")

            # Gauges
            for name in sorted(self._gauges.keys()):
                g = self._gauges[name]
                if g.description:
                    lines.append(f"# HELP {name} {g.description}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {g.value}")

            # Histograms
            for name in sorted(self._histograms.keys()):
                h = self._histograms[name]
                if h.description:
                    lines.append(f"# HELP {name} {h.description}")
                lines.append(f"# TYPE {name} summary")
                lines.append(f"{name}_count {h.count}")
                lines.append(f"{name}_sum {h.sum}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, dict[str, float | int | str]]:
        """Export metrics as dictionary."""
        result: dict[str, dict[str, float | int | str]] = {}
        with self._lock:
            for name in self._counters:
                result[name] = {"type": "counter", "value": self._counters[name].value}
            for name in self._gauges:
                result[name] = {"type": "gauge", "value": self._gauges[name].value}
            for name in self._histograms:
                h = self._histograms[name]
                result[name] = {
                    "type": "histogram",
                    "count": h.count,
                    "sum": h.sum,
                    "avg": h.avg,
                }
        return result


# Global registry instance
REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return REGISTRY


# Pre-defined metrics
collector_runs = REGISTRY.counter("collector_runs_total", "Total collector run count")
collector_errors = REGISTRY.counter("collector_errors_total", "Total collector errors")
collector_duration = REGISTRY.histogram("collector_duration_seconds", "Collector run duration")
api_requests = REGISTRY.counter("api_requests_total", "Total API requests")
api_errors = REGISTRY.counter("api_errors_total", "Total API errors")
api_latency = REGISTRY.histogram("api_latency_seconds", "API request latency")
db_queries = REGISTRY.counter("db_queries_total", "Total database queries")
db_latency = REGISTRY.histogram("db_latency_seconds", "Database query latency")


def timed(histogram: Histogram) -> Callable:
    """Decorator to time function execution."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                histogram.observe(time.perf_counter() - start)
        return wrapper
    return decorator
