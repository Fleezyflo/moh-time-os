"""
Time OS UI Spec v2.1 Implementation

This package implements the Client UI Specification v2.1 FINAL exactly as defined.
"""

from .detectors import DetectorRunner
from .evidence import render_link, validate_evidence
from .health import client_health, engagement_health
from .inbox_lifecycle import InboxLifecycleManager
from .issue_lifecycle import IssueLifecycleManager
from .suppression import (
    check_suppression,
    compute_suppression_key,
    insert_suppression_rule,
)
from .time_utils import days_late, local_midnight_utc, payment_date_local, window_start

__version__ = "2.1.0"

__all__ = [
    "DetectorRunner",
    "render_link",
    "validate_evidence",
    "client_health",
    "engagement_health",
    "InboxLifecycleManager",
    "IssueLifecycleManager",
    "check_suppression",
    "compute_suppression_key",
    "insert_suppression_rule",
    "days_late",
    "local_midnight_utc",
    "payment_date_local",
    "window_start",
]
