#!/usr/bin/env python3
"""
MOH Time OS — Delegation Engine

Per MOH_TIME_OS_DELEGATION.md:
- Delegation-first bias
- Delegation packets with completeness gate
- Least-disclosure rule
- Follow-up and escalation
- Confirmation gates
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from lib import paths

from .config_store import get
from .delegation_graph import Delegatee, get_delegatee

logger = logging.getLogger(__name__)


@dataclass
class DelegationPacket:
    """A delegation packet per spec 4.1."""

    id: str
    item_id: str

    # Required fields
    objective: str  # Definition of done
    context: str
    source_refs: list[str]
    constraints: dict  # deadline, lane, sensitivity
    deliverable_format: str
    escalation_rule: str

    # Delegation target
    delegatee_id: str
    delegatee_name: str

    # Status
    status: str = (
        "draft"  # draft, pending_approval, sent, acknowledged, completed, escalated
    )

    # Tracking
    created_at: str = None
    sent_at: str = None
    acknowledged_at: str = None
    completed_at: str = None

    # Follow-up
    next_nudge_at: str = None
    escalation_at: str = None
    nudge_count: int = 0

    # Metadata
    sensitivity_redacted: bool = False
    completeness_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DelegationPacket":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


PACKETS_FILE = paths.data_dir() / "delegation_packets.json"


def load_packets() -> dict[str, DelegationPacket]:
    """Load all delegation packets."""
    if not PACKETS_FILE.exists():
        return {}
    try:
        data = json.loads(PACKETS_FILE.read_text())
        return {pid: DelegationPacket.from_dict(p) for pid, p in data.items()}
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
        logger.warning(f"Could not load delegation packets: {e}")
        return {}


def save_packets(packets: dict[str, DelegationPacket]) -> None:
    """Save all packets."""
    data = {pid: p.to_dict() for pid, p in packets.items()}
    PACKETS_FILE.write_text(json.dumps(data, indent=2))


def calculate_completeness(packet: DelegationPacket) -> float:
    """Calculate completeness score for a packet."""
    score = 0.0
    total = 6.0

    if packet.objective and len(packet.objective) > 10:
        score += 1.0
    if packet.context and len(packet.context) > 20:
        score += 1.0
    if packet.source_refs:
        score += 1.0
    if packet.constraints and packet.constraints.get("deadline"):
        score += 1.0
    if packet.deliverable_format:
        score += 1.0
    if packet.escalation_rule:
        score += 1.0

    return score / total


def apply_least_disclosure(
    packet: DelegationPacket, delegatee: Delegatee
) -> DelegationPacket:
    """Apply least-disclosure rule - redact sensitive info."""
    sensitivity = packet.constraints.get("sensitivity", [])

    # Check what delegatee can see
    for flag in sensitivity:
        if flag in delegatee.sensitivity_denied:
            # Redact sensitive context
            packet.context = "[REDACTED - sensitive context]"
            packet.sensitivity_redacted = True
            break

    return packet


def create_delegation_packet(
    item: dict,
    delegatee_id: str,
    objective: str,
    deliverable_format: str = "Email confirmation or artifact link",
    escalation_rule: str = "Escalate to Moh after 5 days",
) -> tuple[DelegationPacket, str]:
    """
    Create a delegation packet for an item.

    Returns: (packet, error_message)
    """
    import uuid

    delegatee = get_delegatee(delegatee_id)
    if not delegatee:
        return None, f"Delegatee not found: {delegatee_id}"

    packet_id = str(uuid.uuid4())[:8]
    now = datetime.now(UTC)

    # Build constraints
    constraints = {
        "deadline": item.get("due"),
        "lane": item.get("lane"),
        "sensitivity": item.get("sensitivity_flags", []),
    }

    # Build context
    context = item.get("context_summary") or item.get("notes") or item.get("what", "")

    # Source refs
    source_refs = []
    if item.get("source_ref"):
        source_refs.append(
            f"{item.get('source_type', 'unknown')}:{item.get('source_ref')}"
        )

    packet = DelegationPacket(
        id=packet_id,
        item_id=item.get("id"),
        objective=objective,
        context=context,
        source_refs=source_refs,
        constraints=constraints,
        deliverable_format=deliverable_format,
        escalation_rule=escalation_rule,
        delegatee_id=delegatee_id,
        delegatee_name=delegatee.name,
        created_at=now.isoformat(),
    )

    # Apply least disclosure
    packet = apply_least_disclosure(packet, delegatee)

    # Calculate completeness
    packet.completeness_score = calculate_completeness(packet)

    # Set follow-up schedule
    nudge_days = get("delegation.follow_up_cadence_days", 2)
    escalation_days = get("delegation.escalation_threshold_days", 5)

    packet.next_nudge_at = (now + timedelta(days=nudge_days)).isoformat()
    packet.escalation_at = (now + timedelta(days=escalation_days)).isoformat()

    # Save
    packets = load_packets()
    packets[packet_id] = packet
    save_packets(packets)

    return packet, None


def get_packet(packet_id: str) -> DelegationPacket | None:
    """Get a packet by ID."""
    packets = load_packets()
    return packets.get(packet_id)


def approve_and_send(packet_id: str) -> tuple[bool, str]:
    """Approve and mark a packet as sent."""
    packets = load_packets()

    if packet_id not in packets:
        return False, "Packet not found"

    packet = packets[packet_id]

    # Check completeness threshold
    min_completeness = get("delegation.min_completeness", 0.7)
    if packet.completeness_score < min_completeness:
        return (
            False,
            f"Packet incomplete ({packet.completeness_score:.0%} < {min_completeness:.0%})",
        )

    packet.status = "sent"
    packet.sent_at = datetime.now(UTC).isoformat()

    save_packets(packets)
    return True, "Packet approved and marked as sent"


def mark_acknowledged(packet_id: str) -> tuple[bool, str]:
    """Mark packet as acknowledged by delegatee."""
    packets = load_packets()

    if packet_id not in packets:
        return False, "Packet not found"

    packet = packets[packet_id]
    packet.status = "acknowledged"
    packet.acknowledged_at = datetime.now(UTC).isoformat()

    save_packets(packets)
    return True, "Marked as acknowledged"


def mark_completed(packet_id: str, notes: str = None) -> tuple[bool, str]:
    """Mark delegation as completed."""
    packets = load_packets()

    if packet_id not in packets:
        return False, "Packet not found"

    packet = packets[packet_id]
    packet.status = "completed"
    packet.completed_at = datetime.now(UTC).isoformat()

    save_packets(packets)
    return True, "Marked as completed"


def check_nudges_due() -> list[DelegationPacket]:
    """Find packets that need a nudge."""
    packets = load_packets()
    now = datetime.now(UTC)
    due = []

    for packet in packets.values():
        if packet.status not in ["sent", "acknowledged"]:
            continue

        if packet.next_nudge_at:
            nudge_time = datetime.fromisoformat(
                packet.next_nudge_at.replace("Z", "+00:00")
            )
            if now >= nudge_time:
                due.append(packet)

    return due


def check_escalations_due() -> list[DelegationPacket]:
    """Find packets that need escalation."""
    packets = load_packets()
    now = datetime.now(UTC)
    due = []

    for packet in packets.values():
        if packet.status not in ["sent", "acknowledged"]:
            continue

        if packet.escalation_at:
            esc_time = datetime.fromisoformat(
                packet.escalation_at.replace("Z", "+00:00")
            )
            if now >= esc_time:
                due.append(packet)

    return due


def send_nudge(packet_id: str) -> tuple[bool, str]:
    """Record that a nudge was sent."""
    packets = load_packets()

    if packet_id not in packets:
        return False, "Packet not found"

    packet = packets[packet_id]
    packet.nudge_count += 1

    # Schedule next nudge
    nudge_days = get("delegation.follow_up_cadence_days", 2)
    packet.next_nudge_at = (datetime.now(UTC) + timedelta(days=nudge_days)).isoformat()

    save_packets(packets)
    return True, f"Nudge recorded (count: {packet.nudge_count})"


def escalate(packet_id: str, reason: str = None) -> tuple[bool, str]:
    """Escalate a delegation."""
    packets = load_packets()

    if packet_id not in packets:
        return False, "Packet not found"

    packet = packets[packet_id]
    packet.status = "escalated"

    save_packets(packets)
    return True, f"Escalated: {reason or 'No response within threshold'}"


def list_active_delegations() -> list[DelegationPacket]:
    """List all active (non-completed) delegations."""
    packets = load_packets()
    return [p for p in packets.values() if p.status not in ["completed", "escalated"]]


def format_packet_message(packet: DelegationPacket) -> str:
    """Format packet as a message to send."""
    lines = [
        f"**Task Delegation: {packet.objective}**",
        "",
        "**Context:**",
        packet.context,
        "",
        f"**Deliverable:** {packet.deliverable_format}",
    ]

    if packet.constraints.get("deadline"):
        lines.append(f"**Deadline:** {packet.constraints['deadline']}")

    lines.extend(
        [
            "",
            f"**Escalation:** {packet.escalation_rule}",
        ]
    )

    return "\n".join(lines)


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Commands: list, create, approve <id>, nudges, escalations")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        for p in list_active_delegations():
            logger.info(f"{p.id}: {p.objective[:40]} → {p.delegatee_name} [{p.status}]")
    elif cmd == "nudges":
        for p in check_nudges_due():
            logger.info(f"{p.id}: {p.objective[:40]} → {p.delegatee_name} (nudge due)")
    elif cmd == "escalations":
        for p in check_escalations_due():
            logger.info(
                f"{p.id}: {p.objective[:40]} → {p.delegatee_name} (escalation due)"
            )
    elif cmd == "approve" and len(sys.argv) >= 3:
        ok, msg = approve_and_send(sys.argv[2])
        logger.info(msg)
