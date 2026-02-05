"""
Commitment Truth Module (Tier 1)

Extracts and tracks promises/commitments from communications.

Dependencies:
- Tier 0 (Time Truth) must be stable

Objects:
- Commitment (promise made in email/chat/meeting)
- CommitmentLink (task association)

Invariants:
- Every commitment maps to zero or one task
- Commitments are never duplicated for same source
- Untracked commitments surface in briefs
"""

from .detector import detect_promises, detect_requests, extract_deadline
from .commitment_manager import CommitmentManager

__all__ = ['detect_promises', 'detect_requests', 'extract_deadline', 'CommitmentManager']
