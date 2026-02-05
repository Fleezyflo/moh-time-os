#!/usr/bin/env python3
"""
MOH Time OS — Status Engine

Implements status model from MOH_TIME_OS_STATUS.md:
- Canonical statuses
- Transition rules
- Manual-only gates
- Auto-transition detection
- Evidence requirements
- Staleness detection
"""

import json
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set
from enum import Enum

from .governance import get_domain_mode, can_write, DomainMode
from .change_bundles import create_status_change_bundle
from .config_store import get


class Status(str, Enum):
    """Canonical task statuses."""
    NEW = "new"
    PLANNED = "planned"
    IN_PROGRESS = "inProgress"
    DELEGATED = "delegated"
    WAITING_FOR = "waitingFor"
    REVIEW = "review"
    BLOCKED = "blocked"
    DONE = "done"
    DROPPED = "dropped"
    ARCHIVED = "archived"


# Allowed transitions per status
TRANSITIONS: Dict[Status, Set[Status]] = {
    Status.NEW: {Status.PLANNED, Status.DELEGATED, Status.DROPPED},
    Status.PLANNED: {Status.IN_PROGRESS, Status.DELEGATED, Status.WAITING_FOR, Status.BLOCKED, Status.DROPPED, Status.ARCHIVED},
    Status.IN_PROGRESS: {Status.REVIEW, Status.WAITING_FOR, Status.BLOCKED, Status.DONE, Status.DROPPED},
    Status.DELEGATED: {Status.WAITING_FOR, Status.REVIEW, Status.DONE, Status.BLOCKED, Status.PLANNED},
    Status.WAITING_FOR: {Status.PLANNED, Status.IN_PROGRESS, Status.REVIEW, Status.DONE, Status.BLOCKED, Status.ARCHIVED},
    Status.REVIEW: {Status.PLANNED, Status.IN_PROGRESS, Status.DONE, Status.BLOCKED},
    Status.BLOCKED: {Status.PLANNED, Status.IN_PROGRESS, Status.WAITING_FOR, Status.DELEGATED, Status.ARCHIVED},
    Status.DONE: set(),  # No auto transitions; manual reopen only
    Status.DROPPED: {Status.PLANNED, Status.ARCHIVED},
    Status.ARCHIVED: {Status.PLANNED},
}

# Statuses that require manual confirmation (hard gate)
MANUAL_ONLY = {Status.DONE, Status.DROPPED, Status.ARCHIVED}

# Status title prefixes for Google Tasks
STATUS_PREFIXES = {
    Status.WAITING_FOR: "[WF]",
    Status.REVIEW: "[REV]",
    Status.BLOCKED: "[BLOCKED]",
}


def can_transition(from_status: str, to_status: str) -> Tuple[bool, str]:
    """
    Check if a transition is allowed.
    
    Returns: (allowed, reason)
    """
    try:
        from_s = Status(from_status)
        to_s = Status(to_status)
    except ValueError as e:
        return False, f"Invalid status: {e}"
    
    if to_s not in TRANSITIONS.get(from_s, set()):
        allowed = list(TRANSITIONS.get(from_s, set()))
        return False, f"Transition {from_status} → {to_status} not allowed. Allowed: {[s.value for s in allowed]}"
    
    return True, "Allowed"


def requires_confirmation(to_status: str) -> bool:
    """Check if transitioning to this status requires manual confirmation."""
    try:
        to_s = Status(to_status)
        return to_s in MANUAL_ONLY
    except ValueError:
        return True  # Unknown status, require confirmation


def get_status_prefix(status: str) -> str:
    """Get the title prefix for a status (for Google Tasks)."""
    try:
        s = Status(status)
        return STATUS_PREFIXES.get(s, "")
    except ValueError:
        return ""


class TransitionProposal:
    """A proposed status transition."""
    
    def __init__(
        self,
        item_id: str,
        from_status: str,
        to_status: str,
        reason: str,
        evidence: Dict = None,
        confidence: str = "medium",
    ):
        self.item_id = item_id
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        self.evidence = evidence or {}
        self.confidence = confidence
        self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


def propose_transition(
    item_id: str,
    from_status: str,
    to_status: str,
    reason: str,
    evidence: Dict = None,
) -> Tuple[bool, TransitionProposal | str]:
    """
    Propose a status transition.
    
    In OBSERVE mode: creates proposal only.
    In PROPOSE mode: creates proposal and queues it.
    In EXECUTE mode: executes if allowed.
    
    Returns: (success, proposal_or_error)
    """
    # Validate transition
    allowed, msg = can_transition(from_status, to_status)
    if not allowed:
        return False, msg
    
    # Create proposal
    proposal = TransitionProposal(
        item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        evidence=evidence,
    )
    
    # Check domain mode
    mode = get_domain_mode("tasks")
    
    if mode == DomainMode.OBSERVE:
        return True, proposal
    
    if mode == DomainMode.PROPOSE:
        # Queue proposal for approval
        _queue_proposal(proposal)
        return True, proposal
    
    if mode == DomainMode.EXECUTE:
        # Check if manual confirmation required
        if requires_confirmation(to_status):
            # Still need confirmation, queue as proposal
            _queue_proposal(proposal)
            return True, proposal
        
        # Execute transition
        success = _execute_transition(proposal)
        return success, proposal
    
    return False, "Unknown domain mode"


def _queue_proposal(proposal: TransitionProposal) -> None:
    """Queue a transition proposal for later approval."""
    proposals_file = Path(__file__).parent.parent / "data" / "transition_proposals.json"
    proposals_file.parent.mkdir(parents=True, exist_ok=True)
    
    proposals = []
    if proposals_file.exists():
        try:
            proposals = json.loads(proposals_file.read_text())
        except:
            proposals = []
    
    proposals.append(proposal.to_dict())
    proposals_file.write_text(json.dumps(proposals, indent=2))


def _execute_transition(proposal: TransitionProposal) -> bool:
    """Execute a status transition."""
    import sqlite3
    from pathlib import Path
    
    # Create change bundle for rollback
    bundle = create_status_change_bundle(
        proposal.item_id,
        proposal.from_status,
        proposal.to_status,
        proposal.reason,
    )
    
    # Update the item in the database
    db_path = Path(__file__).parent.parent / "data" / "state.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Determine table based on item_id prefix or proposal context
        if proposal.item_id.startswith('task_') or proposal.item_type == 'task':
            cursor.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (proposal.to_status, proposal.item_id)
            )
        elif proposal.item_id.startswith('project_') or proposal.item_type == 'project':
            cursor.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (proposal.to_status, proposal.item_id)
            )
        elif proposal.item_id.startswith('inv_') or proposal.item_type == 'invoice':
            cursor.execute(
                "UPDATE invoices SET status = ? WHERE id = ?",
                (proposal.to_status, proposal.item_id)
            )
        else:
            # Try tasks first as default
            cursor.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (proposal.to_status, proposal.item_id)
            )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error executing transition: {e}")
        return False


def get_pending_proposals() -> List[Dict]:
    """Get all pending transition proposals."""
    proposals_file = Path(__file__).parent.parent / "data" / "transition_proposals.json"
    
    if not proposals_file.exists():
        return []
    
    try:
        return json.loads(proposals_file.read_text())
    except:
        return []


def approve_proposal(proposal_index: int) -> Tuple[bool, str]:
    """Approve and execute a pending proposal."""
    proposals = get_pending_proposals()
    
    if proposal_index < 0 or proposal_index >= len(proposals):
        return False, "Invalid proposal index"
    
    proposal = proposals[proposal_index]
    
    # Execute
    bundle = create_status_change_bundle(
        proposal["item_id"],
        proposal["from_status"],
        proposal["to_status"],
        f"Approved: {proposal['reason']}",
    )
    
    # Remove from queue
    proposals.pop(proposal_index)
    proposals_file = Path(__file__).parent.parent / "data" / "transition_proposals.json"
    proposals_file.write_text(json.dumps(proposals, indent=2))
    
    return True, f"Approved transition for {proposal['item_id']}"


def reject_proposal(proposal_index: int, reason: str = None) -> Tuple[bool, str]:
    """Reject a pending proposal."""
    proposals = get_pending_proposals()
    
    if proposal_index < 0 or proposal_index >= len(proposals):
        return False, "Invalid proposal index"
    
    # Remove from queue
    proposals.pop(proposal_index)
    proposals_file = Path(__file__).parent.parent / "data" / "transition_proposals.json"
    proposals_file.write_text(json.dumps(proposals, indent=2))
    
    return True, f"Rejected proposal: {reason or 'No reason provided'}"


# ===== Evidence Requirements =====

class EvidenceType(str, Enum):
    CONFIRMATION_EMAIL = "confirmation_email"
    ARTIFACT_LINK = "artifact_link"
    MEETING_OUTCOME = "meeting_outcome"
    MANUAL_CONFIRMATION = "manual_confirmation"


def has_sufficient_evidence(to_status: str, evidence: Dict) -> Tuple[bool, str]:
    """
    Check if there's sufficient evidence for a transition.
    
    "done" requires evidence per spec.
    """
    if to_status != Status.DONE.value:
        return True, "No evidence required"
    
    # For "done", need at least one evidence type
    if not evidence:
        return False, "No evidence provided for done status"
    
    valid_types = [e.value for e in EvidenceType]
    
    for etype in valid_types:
        if etype in evidence and evidence[etype]:
            return True, f"Evidence found: {etype}"
    
    return False, "No valid evidence type found"


# ===== Staleness Detection =====

def get_staleness_threshold(status: str) -> int:
    """Get staleness threshold in days for a status."""
    thresholds = {
        Status.WAITING_FOR.value: get("staleness.waiting_for_days", 5),
        Status.REVIEW.value: get("staleness.review_days", 3),
        Status.BLOCKED.value: get("staleness.blocked_days", 3),
        Status.IN_PROGRESS.value: get("staleness.in_progress_days", 2),
    }
    return thresholds.get(status, 7)  # Default 7 days


def is_stale(status: str, last_updated: str) -> bool:
    """Check if an item is stale based on its status and last update."""
    threshold = get_staleness_threshold(status)
    
    try:
        updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold)
        return updated < cutoff
    except:
        return False


def detect_stale_items(items: List[Dict]) -> List[Dict]:
    """
    Detect stale items that need attention.
    
    Returns list of items with staleness info.
    """
    stale = []
    
    for item in items:
        status = item.get("status")
        last_updated = item.get("updated_at") or item.get("created_at")
        
        if not status or not last_updated:
            continue
        
        if is_stale(status, last_updated):
            threshold = get_staleness_threshold(status)
            stale.append({
                "item": item,
                "status": status,
                "threshold_days": threshold,
                "last_updated": last_updated,
            })
    
    return stale


# ===== Auto-Transition Detection (OBSERVE-safe) =====

def detect_transitions(item: Dict, signals: Dict) -> List[TransitionProposal]:
    """
    Detect potential transitions based on signals.
    
    Signals can include:
    - email_signals: emails related to this item
    - calendar_signals: calendar events
    - task_signals: task completion signals
    - artifact_signals: delivered artifacts
    """
    proposals = []
    current_status = item.get("status", Status.NEW.value)
    item_id = item.get("id")
    
    if not item_id:
        return proposals
    
    # Signal: Task normalized with next action → planned
    if current_status == Status.NEW.value:
        if item.get("lane") and item.get("recommended_action"):
            proposals.append(TransitionProposal(
                item_id=item_id,
                from_status=current_status,
                to_status=Status.PLANNED.value,
                reason="Task normalized with lane and next action",
                confidence="high",
            ))
    
    # Signal: Calendar block exists → inProgress
    if current_status == Status.PLANNED.value:
        calendar_blocks = signals.get("calendar_signals", [])
        for block in calendar_blocks:
            if block.get("item_id") == item_id and block.get("is_now"):
                proposals.append(TransitionProposal(
                    item_id=item_id,
                    from_status=current_status,
                    to_status=Status.IN_PROGRESS.value,
                    reason=f"Calendar block active: {block.get('summary', 'Unknown')}",
                    evidence={"calendar_event": block},
                    confidence="high",
                ))
    
    # Signal: Delegation sent → delegated
    if current_status in [Status.PLANNED.value, Status.NEW.value]:
        delegation = signals.get("delegation_signal")
        if delegation and delegation.get("sent"):
            proposals.append(TransitionProposal(
                item_id=item_id,
                from_status=current_status,
                to_status=Status.DELEGATED.value,
                reason=f"Delegated to {delegation.get('to', 'Unknown')}",
                evidence={"delegation": delegation},
                confidence="high",
            ))
    
    # Signal: Awaiting reply → waitingFor
    if current_status == Status.PLANNED.value:
        email_signals = signals.get("email_signals", [])
        for email in email_signals:
            if email.get("type") == "sent" and email.get("awaiting_reply"):
                proposals.append(TransitionProposal(
                    item_id=item_id,
                    from_status=current_status,
                    to_status=Status.WAITING_FOR.value,
                    reason=f"Sent email, awaiting reply: {email.get('subject', 'Unknown')}",
                    evidence={"email": email},
                    confidence="medium",
                ))
    
    # Signal: Artifact delivered → review
    if current_status in [Status.IN_PROGRESS.value, Status.DELEGATED.value]:
        artifacts = signals.get("artifact_signals", [])
        for artifact in artifacts:
            if artifact.get("item_id") == item_id:
                proposals.append(TransitionProposal(
                    item_id=item_id,
                    from_status=current_status,
                    to_status=Status.REVIEW.value,
                    reason=f"Artifact delivered: {artifact.get('name', 'Unknown')}",
                    evidence={"artifact": artifact},
                    confidence="high",
                ))
    
    return proposals


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: status_engine.py <command> [args]")
        print("Commands: check <from> <to>, proposals, approve <index>, reject <index>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "check" and len(sys.argv) >= 4:
        allowed, msg = can_transition(sys.argv[2], sys.argv[3])
        print(f"{'✓' if allowed else '✗'} {msg}")
    
    elif cmd == "proposals":
        proposals = get_pending_proposals()
        for i, p in enumerate(proposals):
            print(f"{i}: {p['from_status']} → {p['to_status']} | {p['item_id']} | {p['reason']}")
    
    elif cmd == "approve" and len(sys.argv) >= 3:
        success, msg = approve_proposal(int(sys.argv[2]))
        print(msg)
    
    elif cmd == "reject" and len(sys.argv) >= 3:
        reason = sys.argv[3] if len(sys.argv) > 3 else None
        success, msg = reject_proposal(int(sys.argv[2]), reason)
        print(msg)
    
    else:
        print(f"Unknown command: {cmd}")
