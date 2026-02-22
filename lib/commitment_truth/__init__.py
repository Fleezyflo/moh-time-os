"""
Commitment Truth Module

Extracts and tracks promises/commitments from communications.

Dependencies:
Objects:
- Commitment (promise made in email/chat/meeting)
- CommitmentLink (task association)

Invariants:
- Every commitment maps to zero or one task
- Commitments are never duplicated for same source
- Untracked commitments surface in briefs
"""

from .commitment_manager import CommitmentManager
from .detector import detect_promises, detect_requests, extract_deadline

__all__ = [
    "detect_promises",
    "detect_requests",
    "extract_deadline",
    "CommitmentManager",
]
