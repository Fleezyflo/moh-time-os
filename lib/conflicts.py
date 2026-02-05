#!/usr/bin/env python3
"""
MOH Time OS — Conflict Tracking

Per spec 4.5:
- conflicting claims + sources
- confidence per claim
- proposed resolution path
- execution gating flag (if high risk)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from enum import Enum

CONFLICTS_FILE = Path(__file__).parent.parent / "data" / "conflicts.json"
CONFLICTS_FILE.parent.mkdir(parents=True, exist_ok=True)


class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ConflictType(str, Enum):
    DUPLICATE = "duplicate"  # Same item from multiple sources
    SCHEDULE = "schedule"  # Overlapping time commitments
    ASSIGNMENT = "assignment"  # Multiple owners/assignees
    DEADLINE = "deadline"  # Conflicting deadlines
    STATUS = "status"  # Conflicting status signals
    DATA = "data"  # Conflicting data values


@dataclass
class Claim:
    """A claim about an item from a specific source."""
    source_type: str  # email, calendar, tasks, chat, manual
    source_ref: str  # Reference to the source (message ID, event ID, etc.)
    claim_type: str  # What is being claimed (deadline, status, owner, etc.)
    claim_value: str  # The claimed value
    confidence: str  # low, medium, high
    timestamp: str = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Claim':
        return cls(**data)


@dataclass
class Conflict:
    """A conflict between multiple claims."""
    id: str
    conflict_type: str
    item_id: str = None  # Related item, if any
    
    claims: List[Claim] = field(default_factory=list)
    
    status: str = ConflictStatus.OPEN.value
    
    # Resolution
    proposed_resolution: str = None
    resolution_confidence: str = None
    resolved_claim_index: int = None  # Which claim was chosen
    resolution_notes: str = None
    resolved_at: str = None
    resolved_by: str = None
    
    # Gating
    execution_gated: bool = False  # If True, block execution until resolved
    risk_level: str = "low"  # low, medium, high
    
    # Metadata
    created_at: str = None
    updated_at: str = None
    
    def add_claim(self, claim: Claim) -> None:
        """Add a claim to this conflict."""
        self.claims.append(claim)
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["claims"] = [c.to_dict() if isinstance(c, Claim) else c for c in self.claims]
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conflict':
        claims = [Claim.from_dict(c) if isinstance(c, dict) else c for c in data.pop("claims", [])]
        return cls(claims=claims, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_conflicts() -> Dict[str, Conflict]:
    """Load all conflicts from disk."""
    if not CONFLICTS_FILE.exists():
        return {}
    
    try:
        data = json.loads(CONFLICTS_FILE.read_text())
        return {cid: Conflict.from_dict(c) for cid, c in data.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_conflicts(conflicts: Dict[str, Conflict]) -> None:
    """Save all conflicts to disk."""
    data = {cid: c.to_dict() for cid, c in conflicts.items()}
    CONFLICTS_FILE.write_text(json.dumps(data, indent=2))


def get_conflict(conflict_id: str) -> Optional[Conflict]:
    """Get a conflict by ID."""
    conflicts = load_conflicts()
    return conflicts.get(conflict_id)


def create_conflict(
    conflict_type: str,
    claims: List[Claim],
    item_id: str = None,
    execution_gated: bool = False,
    risk_level: str = "low",
) -> Conflict:
    """Create a new conflict."""
    import uuid
    
    conflicts = load_conflicts()
    
    conflict_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    conflict = Conflict(
        id=conflict_id,
        conflict_type=conflict_type,
        item_id=item_id,
        claims=claims,
        execution_gated=execution_gated,
        risk_level=risk_level,
        created_at=now,
        updated_at=now,
    )
    
    conflicts[conflict_id] = conflict
    save_conflicts(conflicts)
    
    return conflict


def resolve_conflict(
    conflict_id: str,
    chosen_claim_index: int = None,
    resolution_notes: str = None,
    resolved_by: str = "system",
) -> Optional[Conflict]:
    """Resolve a conflict by choosing a claim or providing notes."""
    conflicts = load_conflicts()
    
    if conflict_id not in conflicts:
        return None
    
    conflict = conflicts[conflict_id]
    conflict.status = ConflictStatus.RESOLVED.value
    conflict.resolved_claim_index = chosen_claim_index
    conflict.resolution_notes = resolution_notes
    conflict.resolved_at = datetime.now(timezone.utc).isoformat()
    conflict.resolved_by = resolved_by
    conflict.updated_at = datetime.now(timezone.utc).isoformat()
    
    save_conflicts(conflicts)
    return conflict


def ignore_conflict(conflict_id: str, reason: str = None) -> Optional[Conflict]:
    """Mark a conflict as ignored."""
    conflicts = load_conflicts()
    
    if conflict_id not in conflicts:
        return None
    
    conflict = conflicts[conflict_id]
    conflict.status = ConflictStatus.IGNORED.value
    conflict.resolution_notes = reason
    conflict.updated_at = datetime.now(timezone.utc).isoformat()
    
    save_conflicts(conflicts)
    return conflict


def list_conflicts(
    status: str = None,
    conflict_type: str = None,
    item_id: str = None,
    gated_only: bool = False,
) -> List[Conflict]:
    """List conflicts with optional filters."""
    conflicts = load_conflicts()
    result = list(conflicts.values())
    
    if status:
        result = [c for c in result if c.status == status]
    if conflict_type:
        result = [c for c in result if c.conflict_type == conflict_type]
    if item_id:
        result = [c for c in result if c.item_id == item_id]
    if gated_only:
        result = [c for c in result if c.execution_gated]
    
    return result


def list_open_conflicts() -> List[Conflict]:
    """List all open (unresolved) conflicts."""
    return list_conflicts(status=ConflictStatus.OPEN.value)


def list_gated_conflicts() -> List[Conflict]:
    """List all conflicts that gate execution."""
    return list_conflicts(gated_only=True, status=ConflictStatus.OPEN.value)


def has_blocking_conflicts(item_id: str = None) -> bool:
    """Check if there are any blocking (gated) conflicts."""
    gated = list_gated_conflicts()
    if item_id:
        gated = [c for c in gated if c.item_id == item_id]
    return len(gated) > 0


def detect_duplicate_conflict(
    item_id: str,
    source_type: str,
    source_ref: str,
    existing_sources: List[Dict],
) -> Optional[Conflict]:
    """
    Detect if adding a new source creates a duplicate conflict.
    
    Returns a new Conflict if one is detected, None otherwise.
    """
    # Check if any existing source has the same type but different ref
    for existing in existing_sources:
        if existing.get("source_type") == source_type:
            if existing.get("source_ref") != source_ref:
                # Potential duplicate
                claims = [
                    Claim(
                        source_type=existing.get("source_type"),
                        source_ref=existing.get("source_ref"),
                        claim_type="identity",
                        claim_value=item_id,
                        confidence="high",
                        timestamp=existing.get("timestamp"),
                    ),
                    Claim(
                        source_type=source_type,
                        source_ref=source_ref,
                        claim_type="identity",
                        claim_value=item_id,
                        confidence="medium",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                ]
                return create_conflict(
                    conflict_type=ConflictType.DUPLICATE.value,
                    claims=claims,
                    item_id=item_id,
                )
    
    return None


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: conflicts.py <command> [args]")
        print("Commands: list, open, gated, get <id>, resolve <id> [claim_index]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        for c in list_conflicts():
            print(f"{c.id}: {c.conflict_type} ({c.status}) - {len(c.claims)} claims")
    
    elif cmd == "open":
        for c in list_open_conflicts():
            print(f"{c.id}: {c.conflict_type} - {len(c.claims)} claims")
    
    elif cmd == "gated":
        for c in list_gated_conflicts():
            print(f"{c.id}: {c.conflict_type} - BLOCKS EXECUTION")
    
    elif cmd == "get" and len(sys.argv) >= 3:
        c = get_conflict(sys.argv[2])
        if c:
            print(json.dumps(c.to_dict(), indent=2))
        else:
            print("Not found")
    
    elif cmd == "resolve" and len(sys.argv) >= 3:
        claim_index = int(sys.argv[3]) if len(sys.argv) > 3 else None
        c = resolve_conflict(sys.argv[2], chosen_claim_index=claim_index)
        if c:
            print(f"Resolved: {c.id}")
        else:
            print("Not found")
    
    else:
        print(f"Unknown command: {cmd}")
