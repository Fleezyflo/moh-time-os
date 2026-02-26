#!/usr/bin/env python3
"""
Promise Debt Tracker — Captures and tracks commitments made in conversation.

A "promise" is any commitment made to someone:
- "I'll send you X by Friday"
- "Will follow up with Y tomorrow"
- "Let me get back to you on Z"

This module:
1. Parses natural language to extract commitments
2. Stores them with context (who, what, when)
3. Surfaces approaching/overdue promises
4. Tracks completion status
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta

from lib import paths

logger = logging.getLogger(__name__)

# Storage
PROMISES_FILE = paths.data_dir() / "promises.json"

# Commitment signal phrases
COMMITMENT_SIGNALS = [
    r"\b(i'll|i will|will)\s+(send|share|get|follow up|reach out|check|confirm|update|prepare|draft|review)",
    r"\b(let me|gonna|going to)\s+(send|share|get|follow up|reach out|check|confirm|update|prepare|draft|review)",
    r"\b(will get back|get back to you|follow up with you)",
    r"\b(by (today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|end of (day|week)))",
    r"\b(before|by) (the )?(meeting|call|end of)",
]

# Time extraction patterns
TIME_PATTERNS = {
    "today": 0,
    "tomorrow": 1,
    "monday": None,  # Calculated
    "tuesday": None,
    "wednesday": None,
    "thursday": None,
    "friday": None,
    "saturday": None,
    "sunday": None,
    "end of day": 0,
    "end of week": None,  # Friday
    "eod": 0,
    "eow": None,
}

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def load_promises() -> list:
    """Load promises from storage."""
    if not PROMISES_FILE.exists():
        return []
    try:
        with open(PROMISES_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load promises file: {e}")
        return []


def save_promises(promises: list) -> None:
    """Save promises to storage."""
    PROMISES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMISES_FILE, "w") as f:
        json.dump(promises, f, indent=2, default=str)


def generate_id(text: str, timestamp: str) -> str:
    """Generate unique ID for a promise."""
    return hashlib.sha256(f"{text}{timestamp}".encode()).hexdigest()[:8]


def parse_due_date(text: str) -> date | None:
    """Extract due date from text."""
    text_lower = text.lower()
    today = date.today()

    # Check for explicit patterns
    if "today" in text_lower or "eod" in text_lower or "end of day" in text_lower:
        return today

    if "tomorrow" in text_lower:
        return today + timedelta(days=1)

    if "end of week" in text_lower or "eow" in text_lower:
        # Find next Friday
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and datetime.now().hour >= 17:
            days_until_friday = 7
        return today + timedelta(days=days_until_friday)

    # Check for weekday names
    for i, day in enumerate(WEEKDAYS):
        if day in text_lower:
            current_weekday = today.weekday()
            days_ahead = i - current_weekday
            if days_ahead <= 0:  # Already passed this week
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # Check for date patterns (Feb 5, 2/5, etc.)
    date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", text)
    if date_match:
        month, day = int(date_match.group(1)), int(date_match.group(2))
        try:
            return date(today.year, month, day)
        except ValueError:
            # Invalid date (e.g., 2/30)
            pass

    return None


def extract_recipient(text: str) -> str | None:
    """Extract who the promise is to."""
    # Known team members (prioritize these)
    known_names = ["dana", "ayham", "krystie", "youssef", "john", "molham", "moh"]
    text_lower = text.lower()

    for name in known_names:
        if name in text_lower:
            return name.capitalize()

    # Pattern-based extraction
    patterns = [
        r"(?:follow up with|reach out to|check with|update|send to|share with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:to|with)\s+([A-Z][a-z]+)\s+(?:on|about|by|before)",
        r"@([A-Za-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            recipient = match.group(1).strip()
            # Filter out common non-names
            if recipient.lower() not in [
                "you",
                "them",
                "the",
                "a",
                "an",
                "this",
                "that",
                "me",
            ]:
                return recipient

    return None


def extract_action(text: str) -> str:
    """Extract the promised action."""
    # Remove time references for cleaner action
    action = re.sub(
        r"\b(by|before)\s+(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|end of (day|week)|eod|eow|\d{1,2}[/-]\d{1,2})\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    action = re.sub(r"\s+", " ", action).strip()
    return action[:200]  # Truncate if too long


def detect_commitment(text: str) -> bool:
    """Check if text contains a commitment."""
    text_lower = text.lower()

    return any(re.search(pattern, text_lower) for pattern in COMMITMENT_SIGNALS)


def capture_promise(
    text: str, speaker: str = "Moh", context: str = "", force: bool = False
) -> dict | None:
    """
    Capture a promise from text.

    Args:
        text: The message containing the promise
        speaker: Who made the promise
        context: Additional context (conversation, channel, etc.)
        force: Capture even if no commitment signal detected

    Returns:
        Promise dict if captured, None otherwise
    """
    if not force and not detect_commitment(text):
        return None

    now = datetime.now()
    due_date = parse_due_date(text)
    recipient = extract_recipient(text)
    action = extract_action(text)

    promise = {
        "id": generate_id(text, now.isoformat()),
        "action": action,
        "to": recipient,
        "due": due_date.isoformat() if due_date else None,
        "created_at": now.isoformat(),
        "speaker": speaker,
        "context": context,
        "status": "open",
        "original_text": text[:500],
    }

    # Save
    promises = load_promises()
    promises.append(promise)
    save_promises(promises)

    return promise


def get_open_promises() -> list:
    """Get all open (incomplete) promises."""
    promises = load_promises()
    return [p for p in promises if p.get("status") == "open"]


def get_overdue_promises() -> list:
    """Get promises that are past due."""
    today = date.today()
    open_promises = get_open_promises()

    overdue = []
    for p in open_promises:
        if p.get("due"):
            due_date = date.fromisoformat(p["due"])
            if due_date < today:
                p["days_overdue"] = (today - due_date).days
                overdue.append(p)

    overdue.sort(key=lambda x: -x.get("days_overdue", 0))
    return overdue


def get_due_today() -> list:
    """Get promises due today."""
    today = date.today().isoformat()
    open_promises = get_open_promises()
    return [p for p in open_promises if p.get("due") == today]


def get_due_soon(days: int = 3) -> list:
    """Get promises due within N days."""
    today = date.today()
    cutoff = today + timedelta(days=days)
    open_promises = get_open_promises()

    upcoming = []
    for p in open_promises:
        if p.get("due"):
            due_date = date.fromisoformat(p["due"])
            if today <= due_date <= cutoff:
                p["days_until"] = (due_date - today).days
                upcoming.append(p)

    upcoming.sort(key=lambda x: x.get("days_until", 999))
    return upcoming


def complete_promise(promise_id: str) -> bool:
    """Mark a promise as complete."""
    promises = load_promises()
    for p in promises:
        if p.get("id") == promise_id:
            p["status"] = "done"
            p["completed_at"] = datetime.now().isoformat()
            save_promises(promises)
            return True
    return False


def cancel_promise(promise_id: str, reason: str = "") -> bool:
    """Cancel a promise."""
    promises = load_promises()
    for p in promises:
        if p.get("id") == promise_id:
            p["status"] = "cancelled"
            p["cancelled_at"] = datetime.now().isoformat()
            p["cancel_reason"] = reason
            save_promises(promises)
            return True
    return False


def format_promise(p: dict) -> str:
    """Format a promise for display."""
    action = p.get("action", "")[:60]
    to = p.get("to", "")
    due = p.get("due", "")

    parts = [f"- {action}"]
    if to:
        parts.append(f"→ {to}")
    if due:
        parts.append(f"(due {due})")

    return " ".join(parts)


def generate_promise_report() -> dict:
    """Generate promise debt report."""
    overdue = get_overdue_promises()
    due_today = get_due_today()
    due_soon = get_due_soon(days=3)
    all_open = get_open_promises()

    return {
        "overdue": overdue,
        "due_today": due_today,
        "due_soon": [p for p in due_soon if p not in due_today],
        "total_open": len(all_open),
    }


def format_report(report: dict) -> str:
    """Format promise report as markdown."""
    lines = ["## 🤝 Promise Debt", ""]

    overdue = report.get("overdue", [])
    if overdue:
        lines.append(f"### ⚠️ Overdue ({len(overdue)})")
        for p in overdue[:5]:
            days = p.get("days_overdue", 0)
            lines.append(f"{format_promise(p)} — {days}d overdue")
        lines.append("")

    due_today = report.get("due_today", [])
    if due_today:
        lines.append(f"### 📅 Due Today ({len(due_today)})")
        for p in due_today:
            lines.append(format_promise(p))
        lines.append("")

    due_soon = report.get("due_soon", [])
    if due_soon:
        lines.append(f"### 🔜 Due Soon ({len(due_soon)})")
        for p in due_soon[:5]:
            lines.append(format_promise(p))
        lines.append("")

    if not overdue and not due_today and not due_soon:
        lines.append("*No promise debt tracked.*")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    logger.info("Promise Tracker Test")
    logger.info("=" * 50)
    test_messages = [
        "I'll send you the proposal by tomorrow",
        "Will follow up with Dana on the Ramadan campaign",
        "Let me get back to you on the GMG pricing by Friday",
        "Going to check with Ayham about the BinSina deliverables today",
    ]

    logger.info("\nTesting commitment detection:")
    for msg in test_messages:
        is_commitment = detect_commitment(msg)
        due = parse_due_date(msg)
        recipient = extract_recipient(msg)
        logger.info(f"\n  '{msg[:50]}...'")
        logger.info(f"    Commitment: {is_commitment}")
        logger.info(f"    Due: {due}")
        logger.info(f"    To: {recipient}")
    logger.info("\n\nCurrent promise debt:")
    report = generate_promise_report()
    logger.info(format_report(report))
