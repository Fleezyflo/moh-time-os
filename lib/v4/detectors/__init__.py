"""
Time OS V4 - Detectors

Detection algorithms that analyze artifacts and produce signals.
Each detector is versioned and logs its runs for auditability.
"""

from .base import BaseDetector
from .deadline_detector import DeadlineDetector
from .health_detector import HealthDetector
from .commitment_detector import CommitmentDetector
from .anomaly_detector import AnomalyDetector

__all__ = [
    'BaseDetector',
    'DeadlineDetector',
    'HealthDetector', 
    'CommitmentDetector',
    'AnomalyDetector'
]
