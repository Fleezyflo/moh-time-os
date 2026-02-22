#!/usr/bin/env python3
"""
MOH Time OS — Delegation Graph

Per spec 4.4:
- people/roles
- what they can own
- constraints + escalation paths
- turnaround norms
- disclosure restrictions
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from lib import paths
from lib.compat import UTC

logger = logging.getLogger(__name__)


GRAPH_FILE = paths.data_dir() / "delegation_graph.json"


@dataclass
class Delegatee:
    """A person who can receive delegated work."""

    id: str
    name: str
    email: str = None
    role: str = None  # e.g., "designer", "developer", "coordinator"

    # What they can own
    lanes: list[str] = field(default_factory=list)  # Lanes they handle
    projects: list[str] = field(default_factory=list)  # Specific projects
    clients: list[str] = field(default_factory=list)  # Specific clients
    task_types: list[str] = field(default_factory=list)  # e.g., ["design", "review"]

    # Constraints
    max_concurrent_items: int = 10
    max_weekly_hours: float = 20.0
    unavailable_days: list[str] = field(default_factory=list)  # ["saturday", "sunday"]

    # Escalation
    escalation_contact: str = None  # Who to escalate to if unavailable
    escalation_threshold_hours: int = 24

    # Turnaround norms
    default_turnaround_days: int = 3
    urgent_turnaround_days: int = 1

    # Disclosure restrictions
    sensitivity_allowed: list[str] = field(
        default_factory=list
    )  # Which sensitivity flags they can see
    sensitivity_denied: list[str] = field(
        default_factory=lambda: ["financial", "legal"]
    )  # Flags they can't see

    # Metadata
    active: bool = True
    created_at: str = None
    updated_at: str = None

    def can_handle_lane(self, lane: str) -> bool:
        """Check if delegatee can handle a lane."""
        return not self.lanes or lane in self.lanes

    def can_handle_project(self, project_id: str) -> bool:
        """Check if delegatee can handle a project."""
        return not self.projects or project_id in self.projects

    def can_handle_client(self, client_id: str) -> bool:
        """Check if delegatee can handle a client."""
        return not self.clients or client_id in self.clients

    def can_see_sensitivity(self, flags: list[str]) -> bool:
        """Check if delegatee can see items with these sensitivity flags."""
        for flag in flags:
            if flag in self.sensitivity_denied:
                return False
            if self.sensitivity_allowed and flag not in self.sensitivity_allowed:
                return False
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Delegatee":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_graph() -> dict[str, Delegatee]:
    """Load delegation graph from disk."""
    if not GRAPH_FILE.exists():
        return {}

    try:
        data = json.loads(GRAPH_FILE.read_text())
        return {did: Delegatee.from_dict(d) for did, d in data.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_graph(graph: dict[str, Delegatee]) -> None:
    """Save delegation graph to disk."""
    data = {did: d.to_dict() for did, d in graph.items()}
    GRAPH_FILE.write_text(json.dumps(data, indent=2))


def get_delegatee(delegatee_id: str) -> Delegatee | None:
    """Get a delegatee by ID."""
    graph = load_graph()
    return graph.get(delegatee_id)


def find_delegatee(
    name: str = None,
    email: str = None,
    role: str = None,
) -> Delegatee | None:
    """Find a delegatee by name, email, or role."""
    graph = load_graph()

    for d in graph.values():
        if name and d.name.lower() == name.lower():
            return d
        if email and d.email and d.email.lower() == email.lower():
            return d
        if role and d.role and d.role.lower() == role.lower():
            return d

    return None


def add_delegatee(
    name: str, email: str = None, role: str = None, lanes: list[str] = None, **kwargs
) -> Delegatee:
    """Add a new delegatee to the graph."""
    import uuid

    graph = load_graph()

    delegatee_id = str(uuid.uuid4())[:8]
    now = datetime.now(UTC).isoformat()

    delegatee = Delegatee(
        id=delegatee_id,
        name=name,
        email=email,
        role=role,
        lanes=lanes or [],
        created_at=now,
        updated_at=now,
        **kwargs,
    )

    graph[delegatee_id] = delegatee
    save_graph(graph)

    return delegatee


def update_delegatee(delegatee_id: str, **updates) -> Delegatee | None:
    """Update a delegatee."""
    graph = load_graph()

    if delegatee_id not in graph:
        return None

    delegatee = graph[delegatee_id]

    for key, value in updates.items():
        if hasattr(delegatee, key):
            setattr(delegatee, key, value)

    delegatee.updated_at = datetime.now(UTC).isoformat()

    save_graph(graph)
    return delegatee


def deactivate_delegatee(delegatee_id: str) -> Delegatee | None:
    """Deactivate a delegatee."""
    return update_delegatee(delegatee_id, active=False)


def list_delegatees(
    active_only: bool = True,
    role: str = None,
    lane: str = None,
) -> list[Delegatee]:
    """List delegatees with optional filters."""
    graph = load_graph()
    result = list(graph.values())

    if active_only:
        result = [d for d in result if d.active]
    if role:
        result = [d for d in result if d.role and d.role.lower() == role.lower()]
    if lane:
        result = [d for d in result if d.can_handle_lane(lane)]

    return result


def find_best_delegatee(
    lane: str = None,
    project_id: str = None,
    client_id: str = None,
    sensitivity_flags: list[str] = None,
    task_type: str = None,
) -> Delegatee | None:
    """
    Find the best delegatee for a task based on constraints.

    Returns the first matching active delegatee, or None.
    """
    candidates = list_delegatees(active_only=True)

    for d in candidates:
        # Check lane
        if lane and not d.can_handle_lane(lane):
            continue

        # Check project
        if project_id and not d.can_handle_project(project_id):
            continue

        # Check client
        if client_id and not d.can_handle_client(client_id):
            continue

        # Check sensitivity
        if sensitivity_flags and not d.can_see_sensitivity(sensitivity_flags):
            continue

        # Check task type
        if task_type and d.task_types and task_type not in d.task_types:
            continue

        return d

    return None


def get_escalation_path(delegatee_id: str) -> list[Delegatee]:
    """Get the escalation path for a delegatee."""
    path = []
    current_id = delegatee_id
    visited = set()

    while current_id and current_id not in visited:
        visited.add(current_id)
        delegatee = get_delegatee(current_id)

        if not delegatee:
            break

        path.append(delegatee)
        current_id = delegatee.escalation_contact

    return path


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: delegation_graph.py <command> [args]")
        logger.info(
            "Commands: list, add <name> [email] [role], find <name>, best [--lane X] [--project Y]"
        )
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        for d in list_delegatees():
            lanes = ", ".join(d.lanes) if d.lanes else "all"
            logger.info(f"{d.id}: {d.name} ({d.role or 'no role'}) - lanes: {lanes}")
    elif cmd == "add" and len(sys.argv) >= 3:
        name = sys.argv[2]
        email = sys.argv[3] if len(sys.argv) > 3 else None
        role = sys.argv[4] if len(sys.argv) > 4 else None
        d = add_delegatee(name, email, role)
        logger.info(f"Added: {d.id} - {d.name}")
    elif cmd == "find" and len(sys.argv) >= 3:
        d = find_delegatee(name=sys.argv[2])
        if d:
            logger.info(json.dumps(d.to_dict(), indent=2))
        else:
            logger.info("Not found")
    elif cmd == "best":
        # Parse optional args
        lane = None
        project = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--lane" and i + 1 < len(sys.argv):
                lane = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--project" and i + 1 < len(sys.argv):
                project = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        d = find_best_delegatee(lane=lane, project_id=project)
        if d:
            logger.info(f"Best match: {d.name} ({d.role})")
        else:
            logger.info("No matching delegatee found")
    else:
        logger.info(f"Unknown command: {cmd}")
