"""
Evidence Module — Spec Section 6.16

Implements canonical evidence envelope validation and link rendering rules.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Valid evidence kinds per spec 6.16
VALID_EVIDENCE_KINDS = {
    "invoice",
    "asana_task",
    "gmail_thread",
    "calendar_event",
    "minutes_analysis",
    "gchat_message",
    "xero_contact",
}

# Source systems that support clickable links (spec 6.10, 6.16)
LINKABLE_SOURCES = {
    "asana",
    "gmail",
    "gchat",
    "calendar",
}

# Sources that NEVER render links even if URL present
NO_LINK_SOURCES = {
    "xero",  # Per spec 6.10: "Xero does not provide public deep links"
}

# Minutes has special rendering: url is always null, use payload URLs
CONDITIONAL_LINK_SOURCES = {
    "minutes",  # Check payload.recording_url or payload.transcript_url
}


@dataclass
class EvidenceEnvelope:
    """
    Canonical evidence envelope structure.

    Spec: 6.16 Evidence Meta-Schema
    """

    version: str
    kind: str
    url: str | None
    display_text: str
    source_system: str
    source_id: str
    payload: dict[str, Any]


def validate_evidence(evidence: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate evidence structure against spec.

    Spec: 6.16 Evidence Meta-Schema

    Returns:
        (is_valid, error_message)
    """
    # Required fields
    required = ["version", "kind", "display_text", "source_system", "source_id"]
    for field in required:
        if field not in evidence:
            return False, f"Missing required field: {field}"

    # Version check
    if evidence["version"] != "v1":
        return False, f"Unsupported evidence version: {evidence['version']}"

    # Kind validation
    if evidence["kind"] not in VALID_EVIDENCE_KINDS:
        return False, f"Invalid evidence kind: {evidence['kind']}"

    # Payload must be dict
    if "payload" not in evidence:
        return False, "Missing payload field"

    if not isinstance(evidence["payload"], dict):
        return False, "Payload must be an object"

    # Kind-specific validation
    kind = evidence["kind"]
    payload = evidence["payload"]

    if kind == "invoice":
        required_payload = ["number", "amount", "currency", "status"]
        for field in required_payload:
            if field not in payload:
                return False, f"Invoice payload missing: {field}"

    elif kind == "asana_task":
        if "task_gid" not in payload and "name" not in payload:
            return False, "Asana task payload requires task_gid or name"

    elif kind == "minutes_analysis":
        # URL must be null for minutes (spec 6.16)
        if evidence.get("url") is not None:
            return False, "Minutes evidence.url must be null"

    return True, None


def render_link(evidence: dict[str, Any]) -> dict[str, Any]:
    """
    Determine how to render evidence link in UI.

    Spec: 6.16 UI Link Rendering Rules

    Returns dict with:
        - can_render_link: bool
        - link_url: Optional[str]
        - link_text: str
        - is_plain_text: bool (no arrow, no href)
        - additional_links: List[dict] (for minutes recording/transcript)
    """
    source = evidence.get("source_system", "")
    kind = evidence.get("kind", "")
    url = evidence.get("url")
    display_text = evidence.get("display_text", "")
    payload = evidence.get("payload", {})

    result = {
        "can_render_link": False,
        "link_url": None,
        "link_text": display_text,
        "is_plain_text": True,
        "additional_links": [],
    }

    # Rule 1: Xero NEVER renders link even if URL present
    if source == "xero" or kind == "invoice":
        result["link_text"] = f"{payload.get('number', display_text)} (open in Xero)"
        result["is_plain_text"] = True
        return result

    # Rule 2: Minutes - url always null, use payload URLs
    if source == "minutes" or kind == "minutes_analysis":
        result["link_text"] = display_text
        result["is_plain_text"] = True

        # Check for recording URL
        if payload.get("recording_url"):
            result["additional_links"].append(
                {
                    "url": payload["recording_url"],
                    "text": "View Recording ↗",
                }
            )

        # Check for transcript URL
        if payload.get("transcript_url"):
            result["additional_links"].append(
                {
                    "url": payload["transcript_url"],
                    "text": "View Transcript ↗",
                }
            )

        return result

    # Rule 3: Meet - recordings may not be accessible
    if source == "meet":
        result["is_plain_text"] = True
        return result

    # Rule 4: Standard linkable sources
    if source in LINKABLE_SOURCES and url:
        result["can_render_link"] = True
        result["link_url"] = url
        result["is_plain_text"] = False

        # Set appropriate link text per source
        if source == "asana":
            result["link_text"] = "View in Asana ↗"
        elif source == "gmail":
            result["link_text"] = "View Thread ↗"
        elif source == "gchat":
            result["link_text"] = "View in Chat ↗"
        elif source == "calendar":
            result["link_text"] = "View Event ↗"

        return result

    return result


def create_invoice_evidence(
    invoice_number: str,
    amount: float,
    currency: str,
    due_date: str | None,
    days_overdue: int | None,
    status: str,
    source_id: str,
) -> dict[str, Any]:
    """
    Create canonical invoice evidence envelope.

    Spec: 6.4 Invoice issue fallback, 6.16 Kind-specific payload
    """
    payload = {
        "number": invoice_number,
        "amount": amount,
        "currency": currency,
        "status": status,
    }

    if due_date:
        payload["due_date"] = due_date
    if days_overdue is not None:
        payload["days_overdue"] = days_overdue

    # Construct display text
    aging_text = (
        f"({days_overdue}d overdue)" if days_overdue and days_overdue > 0 else ""
    )
    display = f"{invoice_number} · {currency} {amount:,.0f}"
    if due_date:
        display += f" · Due {due_date}"
    if aging_text:
        display += f" {aging_text}"

    return {
        "version": "v1",
        "kind": "invoice",
        "url": None,  # Xero has no stable deep links
        "display_text": display,
        "source_system": "xero",
        "source_id": source_id,
        "payload": payload,
    }


def create_asana_task_evidence(
    task_gid: str,
    name: str,
    assignee: str | None,
    due_date: str | None,
    days_overdue: int | None,
    project_name: str | None,
    project_gid: str,
) -> dict[str, Any]:
    """
    Create canonical Asana task evidence envelope.

    Spec: 6.16 Kind-specific payload
    """
    payload = {
        "task_gid": task_gid,
        "name": name,
    }
    if assignee:
        payload["assignee"] = assignee
    if due_date:
        payload["due_date"] = due_date
    if days_overdue is not None:
        payload["days_overdue"] = days_overdue
    if project_name:
        payload["project_name"] = project_name

    # Asana URL
    url = f"https://app.asana.com/0/{project_gid}/{task_gid}"

    # Display text
    overdue_text = (
        f" — {days_overdue}d overdue" if days_overdue and days_overdue > 0 else ""
    )
    assignee_text = f" ({assignee})" if assignee else ""
    display = f'"{name}"{overdue_text}{assignee_text}'

    return {
        "version": "v1",
        "kind": "asana_task",
        "url": url,
        "display_text": display,
        "source_system": "asana",
        "source_id": task_gid,
        "payload": payload,
    }


def create_gmail_evidence(
    thread_id: str, subject: str, sender: str, snippet: str, received_at: str
) -> dict[str, Any]:
    """Create canonical Gmail thread evidence envelope."""
    return {
        "version": "v1",
        "kind": "gmail_thread",
        "url": f"https://mail.google.com/mail/#all/{thread_id}",
        "display_text": f'"{subject}"',
        "source_system": "gmail",
        "source_id": thread_id,
        "payload": {
            "thread_id": thread_id,
            "subject": subject,
            "sender": sender,
            "snippet": snippet,
            "received_at": received_at,
        },
    }


def create_calendar_evidence(
    event_id: str,
    title: str,
    start_time: str,
    cancelled: bool = False,
    rescheduled: bool = False,
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Create canonical calendar event evidence envelope."""
    return {
        "version": "v1",
        "kind": "calendar_event",
        "url": f"https://calendar.google.com/calendar/r/event?eid={event_id}",
        "display_text": f'"{title}"',
        "source_system": "calendar",
        "source_id": event_id,
        "payload": {
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "cancelled": cancelled,
            "rescheduled": rescheduled,
        },
    }


def create_minutes_evidence(
    meeting_id: str,
    meeting_title: str,
    analysis_provider: str,
    key_points: list[str],
    sentiment_summary: str | None = None,
    recording_url: str | None = None,
    transcript_url: str | None = None,
    meeting_platform: str = "meet",
) -> dict[str, Any]:
    """
    Create canonical meeting minutes evidence envelope.

    Spec: 6.16 - Minutes: evidence.url always null
    """
    return {
        "version": "v1",
        "kind": "minutes_analysis",
        "url": None,  # Always null for minutes
        "display_text": f"{meeting_title}",
        "source_system": "minutes",
        "source_id": meeting_id,
        "payload": {
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
            "meeting_platform": meeting_platform,
            "analysis_provider": analysis_provider,
            "key_points": key_points,
            "sentiment_summary": sentiment_summary,
            "recording_url": recording_url,
            "transcript_url": transcript_url,
        },
    }


def create_gchat_evidence(
    space_id: str,
    message_id: str,
    sender: str,
    snippet: str,
    keywords_detected: list[str],
) -> dict[str, Any]:
    """Create canonical Google Chat message evidence envelope."""
    return {
        "version": "v1",
        "kind": "gchat_message",
        "url": f"https://chat.google.com/room/{space_id}/{message_id}",
        "display_text": f'"{snippet[:100]}..."'
        if len(snippet) > 100
        else f'"{snippet}"',
        "source_system": "gchat",
        "source_id": message_id,
        "payload": {
            "space_id": space_id,
            "message_id": message_id,
            "sender": sender,
            "snippet": snippet,
            "keywords_detected": keywords_detected,
        },
    }


def create_flagged_signal_evidence(
    excerpt: str,
    source: str,
    source_id: str,
    timestamp: str,
    rule_triggered: str,
    rule_params: dict | None = None,
) -> dict[str, Any]:
    """
    Create evidence structure for flagged signals.

    Spec: 6.4 Flagged Signal evidence structure
    """
    return {
        "excerpt": excerpt,
        "source": source,
        "source_id": source_id,
        "timestamp": timestamp,
        "rule_triggered": rule_triggered,
        "rule_params": rule_params or {},
    }


def create_orphan_evidence(
    identifier_type: str,
    identifier_value: str,
    linkage_failure: str,
    source_signal: dict,
    attempted_matches: list | None = None,
) -> dict[str, Any]:
    """
    Create evidence structure for orphan signals.

    Spec: 6.4 Orphan evidence structure
    """
    return {
        "raw_identifier": {
            "type": identifier_type,
            "value": identifier_value,
        },
        "linkage_failure": linkage_failure,
        "attempted_matches": attempted_matches or [],
        "source_signal": source_signal,
    }


def create_ambiguous_evidence(
    candidates: list[dict], source_signal: dict, requires_user_selection: bool = True
) -> dict[str, Any]:
    """
    Create evidence structure for ambiguous signals.

    Spec: 6.4 Ambiguous evidence structure

    Each candidate: {id, name, match_type, confidence}
    """
    return {
        "candidates": candidates,
        "source_signal": source_signal,
        "requires_user_selection": requires_user_selection,
    }


# Test function
def _test_link_rendering():
    """Test link rendering rules."""

    # Test 1: Xero never renders link
    invoice = create_invoice_evidence(
        "INV-1234", 35000, "AED", "2025-12-20", 45, "overdue", "inv_abc"
    )
    result = render_link(invoice)
    assert result["is_plain_text"]
    assert not result["can_render_link"]
    assert "open in Xero" in result["link_text"]
    logger.info("✓ Xero link test passed")
    # Test 2: Asana renders link
    task = create_asana_task_evidence(
        "12345", "Q1 Report", "Sarah", "2026-01-15", 5, "Monthly Retainer", "67890"
    )
    result = render_link(task)
    assert result["can_render_link"]
    assert "asana" in result["link_url"]
    assert "↗" in result["link_text"]
    logger.info("✓ Asana link test passed")
    # Test 3: Minutes uses payload URLs
    minutes = create_minutes_evidence(
        "meet_123",
        "Q1 Review",
        "gemini",
        ["Point 1"],
        recording_url="https://meet.google.com/rec/123",
    )
    result = render_link(minutes)
    assert result["is_plain_text"]
    assert len(result["additional_links"]) == 1
    assert "Recording" in result["additional_links"][0]["text"]
    logger.info("✓ Minutes link test passed")
    logger.info("All link rendering tests passed!")


if __name__ == "__main__":
    _test_link_rendering()
