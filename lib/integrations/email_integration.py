#!/usr/bin/env python3
"""
MOH Time OS — Email Integration

Email intake, routing, and response drafting.
"""

import json
import logging
import subprocess

from ..config_store import get
from ..governance import requires_confirmation

logger = logging.getLogger(__name__)


def fetch_unread(max_count: int = 50) -> list[dict]:
    """Fetch unread inbox threads."""
    cmd = [
        "gog",
        "gmail",
        "search",
        "is:unread in:inbox",
        "--max",
        str(max_count),
        "--json",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("threads", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not fetch unread emails: {e}")

    return []


def get_thread(thread_id: str) -> dict | None:
    """Get a specific thread with full messages."""
    cmd = ["gog", "gmail", "thread", thread_id, "--json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not fetch thread {thread_id}: {e}")

    return None


def classify_thread(thread: dict) -> dict:
    """
    Classify a thread for sensitivity and routing.

    Returns classification with:
    - lane
    - sensitivity_flags
    - urgency
    - action_required
    """
    subject = (thread.get("subject") or "").lower()
    snippet = (thread.get("snippet") or "").lower()
    sender = (thread.get("from") or "").lower()

    classification = {
        "lane": "ops",
        "sensitivity_flags": [],
        "urgency": "medium",
        "action_required": True,
    }

    # Check sensitivity signals
    sensitivity_config = get("sensitivity.detection_signals", {})

    for category, signals in sensitivity_config.items():
        keywords = signals.get("keywords", [])
        for kw in keywords:
            if kw.lower() in subject or kw.lower() in snippet:
                classification["sensitivity_flags"].append(category)
                break

    # Check urgency
    urgent_keywords = ["urgent", "asap", "critical", "immediately", "emergency"]
    for kw in urgent_keywords:
        if kw in subject or kw in snippet:
            classification["urgency"] = "high"
            break

    # Determine lane (simple heuristics)
    if "invoice" in subject or "payment" in subject or "billing" in subject:
        classification["lane"] = "finance"
    elif "meeting" in subject or "calendar" in subject:
        classification["lane"] = "people"
    elif any(s in sender for s in ["client", "customer"]):
        classification["lane"] = "client"

    return classification


def extract_commitments(thread: dict) -> list[dict]:
    """
    Extract commitments from a thread.

    Returns list of potential commitments/tasks.
    """
    commitments = []

    # Simple extraction - look for patterns
    messages = thread.get("messages", [])

    for msg in messages:
        body = msg.get("body", "") or msg.get("snippet", "")

        # Look for commitment patterns
        patterns = [
            "please send",
            "please share",
            "please review",
            "please confirm",
            "need you to",
            "would you",
            "can you",
            "could you",
            "by tomorrow",
            "by end of day",
            "by friday",
        ]

        for pattern in patterns:
            if pattern in body.lower():
                commitments.append(
                    {
                        "source": f"email:{thread.get('id')}",
                        "pattern_matched": pattern,
                        "snippet": body[:200],
                        "from": msg.get("from"),
                        "date": msg.get("date"),
                    }
                )
                break  # One commitment per message

    return commitments


def draft_reply(
    thread_id: str,
    body: str,
    subject: str = None,
) -> tuple[bool, str]:
    """
    Draft a reply to a thread.

    Note: Always requires confirmation per governance spec.
    """
    # Email sending always requires confirmation
    if requires_confirmation("send_email"):
        # Queue as draft
        return True, "Reply drafted (requires confirmation to send)"

    return False, "Email sending not allowed"


def label_thread(thread_id: str, label: str) -> tuple[bool, str]:
    """Apply a label to a thread."""
    cmd = ["gog", "gmail", "label", thread_id, label]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Labeled as {label}"
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout labeling thread: {thread_id}")
        return False, "Error: Label operation timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error labeling thread: {e}")
        return False, f"Error: {e}"


def archive_thread(thread_id: str) -> tuple[bool, str]:
    """Archive a thread (remove from inbox)."""
    cmd = ["gog", "gmail", "archive", thread_id]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, "Archived"
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout archiving thread: {thread_id}")
        return False, "Error: Archive operation timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error archiving thread: {e}")
        return False, f"Error: {e}"


def process_inbox() -> dict:
    """
    Process inbox for new items.

    Returns processing summary.
    """
    threads = fetch_unread()

    results = {
        "processed": 0,
        "classified": [],
        "commitments_found": [],
    }

    for thread in threads:
        # Classify
        classification = classify_thread(thread)
        results["classified"].append(
            {
                "thread_id": thread.get("id"),
                "subject": thread.get("subject"),
                **classification,
            }
        )

        # Extract commitments
        full_thread = get_thread(thread.get("id"))
        if full_thread:
            commitments = extract_commitments(full_thread)
            results["commitments_found"].extend(commitments)

        results["processed"] += 1

    return results
