"""
Time OS V4 - Detectors

Detection algorithms that analyze artifacts and produce signals.
Each detector is versioned and logs its runs for auditability.
"""

from .anomaly_detector import AnomalyDetector
from .base import BaseDetector
from .commitment_detector import CommitmentDetector
from .deadline_detector import DeadlineDetector
from .health_detector import HealthDetector

__all__ = [
    "BaseDetector",
    "DeadlineDetector",
    "HealthDetector",
    "CommitmentDetector",
    "AnomalyDetector",
]
