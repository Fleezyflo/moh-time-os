"""
Correlator -- post-detection entity overlap pass.

Takes findings from all three detectors, finds shared entities
(e.g., drift client's tasks assigned to bottlenecked member),
and outputs FindingGroups with primary + subordinate findings.

Rendering rule: the entity that appears in the most findings
becomes the primary. Impacts fold under it.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from .bottleneck import BottleneckFinding
from .collision import CollisionFinding
from .drift import DriftFinding

logger = logging.getLogger(__name__)


@dataclass
class FindingGroup:
    """A correlated group of findings with a primary and subordinates."""

    primary_type: str  # "collision", "drift", "bottleneck"
    primary_finding: dict[str, Any] = field(default_factory=dict)
    subordinates: list[dict[str, Any]] = field(default_factory=list)
    shared_entity: str | None = None  # The linking entity (person name or client_id)
    shared_entity_type: str | None = None  # "person" or "client"


def correlate(
    collisions: list[CollisionFinding],
    drifts: list[DriftFinding],
    bottlenecks: list[BottleneckFinding],
) -> list[FindingGroup]:
    """
    Correlate findings across detectors.

    Rules:
    1. If a person is bottlenecked and has tasks from a drifting client,
       the bottleneck is primary and drift folds under it.
    2. If a collision day has tasks from a drifting client, add cross-reference.
    3. Uncorrelated findings become their own group.
    """
    groups: list[FindingGroup] = []
    used_drift_clients: set[str] = set()
    used_collision_indices: set[int] = set()

    # Index drift findings by client_id
    drift_by_client: dict[str, DriftFinding] = {}
    for d in drifts:
        drift_by_client[d.client_id] = d

    # Index drift findings by assigned team member
    drift_clients_by_person: dict[str, list[str]] = {}
    for d in drifts:
        for team_member in d.assigned_team:
            person = team_member.get("name", "")
            if person:
                if person not in drift_clients_by_person:
                    drift_clients_by_person[person] = []
                drift_clients_by_person[person].append(d.client_id)

    # Process bottlenecks first -- they can absorb drifts
    for bn in bottlenecks:
        person = bn.member_name
        related_drift_ids = drift_clients_by_person.get(person, [])

        subordinate_drifts: list[dict[str, Any]] = []
        for cid in related_drift_ids:
            drift = drift_by_client.get(cid)
            if drift:
                subordinate_drifts.append(
                    {
                        "type": "drift",
                        "finding": asdict(drift),
                        "relationship": f"Tasks assigned to {person} are overdue for this client",
                    }
                )
                used_drift_clients.add(cid)

        groups.append(
            FindingGroup(
                primary_type="bottleneck",
                primary_finding=asdict(bn),
                subordinates=subordinate_drifts,
                shared_entity=person,
                shared_entity_type="person",
            )
        )

    # Process remaining drifts (not absorbed by bottlenecks)
    for d in drifts:
        if d.client_id in used_drift_clients:
            continue

        # Check if any collision has tasks from this drifting client
        collision_refs: list[dict[str, Any]] = []
        for i, col in enumerate(collisions):
            client_tasks_in_collision = [t for t in col.tasks if t.get("client_id") == d.client_id]
            if client_tasks_in_collision:
                collision_refs.append(
                    {
                        "type": "collision",
                        "date": col.date,
                        "person": col.person,
                        "tasks_from_client": len(client_tasks_in_collision),
                        "relationship": (
                            f"{len(client_tasks_in_collision)} of {col.tasks_due} tasks on "
                            f"{col.date} are from {d.client_name} (drifting)"
                        ),
                    }
                )
                used_collision_indices.add(i)

        groups.append(
            FindingGroup(
                primary_type="drift",
                primary_finding=asdict(d),
                subordinates=collision_refs,
                shared_entity=d.client_id,
                shared_entity_type="client",
            )
        )

    # Process remaining collisions (not absorbed)
    for i, col in enumerate(collisions):
        if i in used_collision_indices:
            continue

        # Check for cross-references to drifting clients
        cross_refs: list[dict[str, Any]] = []
        for task in col.tasks:
            cid = task.get("client_id")
            if cid and cid in drift_by_client:
                drift = drift_by_client[cid]
                cross_refs.append(
                    {
                        "type": "drift_reference",
                        "client_id": cid,
                        "client_name": drift.client_name,
                        "relationship": f"Task from drifting client {drift.client_name}",
                    }
                )

        groups.append(
            FindingGroup(
                primary_type="collision",
                primary_finding=asdict(col),
                subordinates=cross_refs,
                shared_entity=f"{col.person}_{col.date}",
                shared_entity_type="person_day",
            )
        )

    return groups


def groups_to_dicts(groups: list[FindingGroup]) -> list[dict[str, Any]]:
    """Serialize FindingGroups for storage."""
    return [asdict(g) for g in groups]
