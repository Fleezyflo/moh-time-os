"""
Time OS V5 — Detectors Package

Signal detectors for various data sources.
"""

from .asana_task_detector import AsanaTaskDetector
from .base import SignalDetector
from .calendar_meet_detector import CalendarMeetDetector
from .gchat_detector import GoogleChatDetector
from .registry import DetectorRegistry, get_registry, set_registry
from .xero_financial_detector import XeroFinancialDetector

__all__ = [
    "SignalDetector",
    "DetectorRegistry",
    "get_registry",
    "set_registry",
    "AsanaTaskDetector",
    "XeroFinancialDetector",
    "GoogleChatDetector",
    "CalendarMeetDetector",
]
