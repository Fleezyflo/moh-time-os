"""
Watchdog Timer -- Enforces hard time limits on collector runs.

Uses signal.SIGALRM (Unix-only) to interrupt long-running collectors.
"""

import logging
import signal
from collections.abc import Callable
from types import FrameType
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Type alias for signal handlers
_SignalHandler = Callable[[int, FrameType | None], None] | int | None


class WatchdogTimeout(Exception):
    """Raised when a collector exceeds its time limit."""


class WatchdogTimer:
    """
    Enforces a hard time limit on a callable using SIGALRM.

    Usage:
        watchdog = WatchdogTimer(timeout_seconds=300)
        result = watchdog.run(some_collector_function)

    Note: Only works on Unix systems. SIGALRM is not available on Windows.
    """

    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds
        self._previous_handler: _SignalHandler = None

    def _alarm_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle SIGALRM by raising WatchdogTimeout."""
        raise WatchdogTimeout(f"Operation timed out after {self.timeout_seconds}s")

    def run(self, func: Callable[[], T]) -> T:
        """
        Execute func with a hard time limit.

        Args:
            func: Callable to execute

        Returns:
            Result of func()

        Raises:
            WatchdogTimeout: If func exceeds timeout_seconds
        """
        self._previous_handler = signal.signal(signal.SIGALRM, self._alarm_handler)
        signal.alarm(self.timeout_seconds)
        try:
            result = func()
            signal.alarm(0)  # Cancel alarm
            return result
        except WatchdogTimeout:
            logger.error(
                "Watchdog timeout: operation exceeded %ds limit",
                self.timeout_seconds,
            )
            raise
        finally:
            signal.alarm(0)  # Ensure alarm is cancelled
            if self._previous_handler is not None:
                signal.signal(signal.SIGALRM, self._previous_handler)
