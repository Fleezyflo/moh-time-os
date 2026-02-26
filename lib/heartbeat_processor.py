#!/usr/bin/env python3
"""
Heartbeat Processor — Intelligent heartbeat handling.

Instead of regenerating everything from scratch, this:
1. Reads cached data from last collection
2. Queries Time OS database for overdue/due items
3. Filters to NEW/CHANGED items only
4. Applies urgency rules to decide what to surface
5. Tracks what was surfaced to avoid duplicates
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from lib import paths
from lib.state_tracker import filter_new_items, mark_surfaced

logger = logging.getLogger(__name__)

# Import Time OS queries
TIME_OS_DB_AVAILABLE = False
overdue = None
due_today_fn = None

try:
    from lib.queries import due_today as due_today_fn
    from lib.queries import overdue

    TIME_OS_DB_AVAILABLE = True
except ImportError:
    pass

DATA_DIR = paths.out_dir()
OPS_LEDGER = paths.app_home() / "OPS_LEDGER.md"

# Urgency thresholds
URGENT_KEYWORDS = ["urgent", "asap", "critical", "immediately", "emergency"]
VIP_SENDERS = []  # Populated from config


def load_cached_data() -> dict:
    """Load latest cached data from collectors."""
    data = {}

    # Calendar
    cal_file = DATA_DIR / "calendar-next.json"
    if cal_file.exists():
        try:
            data["calendar"] = json.loads(cal_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read calendar data from {cal_file}: {e}")
            data["calendar"] = {"events": []}

    # Gmail
    gmail_file = DATA_DIR / "gmail-unread.json"
    if gmail_file.exists():
        try:
            data["gmail"] = json.loads(gmail_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read gmail data from {gmail_file}: {e}")
            data["gmail"] = {"threads": []}

    # Tasks
    tasks_file = DATA_DIR / "tasks-all.json"
    if tasks_file.exists():
        try:
            data["tasks"] = json.loads(tasks_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read tasks data from {tasks_file}: {e}")
            data["tasks"] = {"tasks": []}

    # Chat (mentions)
    chat_file = DATA_DIR / "chat-unread-full.json"
    if chat_file.exists():
        try:
            data["chat"] = json.loads(chat_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read chat data from {chat_file}: {e}")
            data["chat"] = {"messages": []}

    return data


def is_urgent_email(thread: dict) -> bool:
    """Check if email thread is urgent."""
    subject = (thread.get("subject") or "").lower()
    snippet = (thread.get("snippet") or "").lower()
    sender = (thread.get("from") or "").lower()

    # Check keywords
    for kw in URGENT_KEYWORDS:
        if kw in subject or kw in snippet:
            return True

    # Check VIP senders
    return any(vip.lower() in sender for vip in VIP_SENDERS)


def is_urgent_task(task: dict) -> bool:
    """Check if task is urgent (overdue or due today)."""
    due = task.get("due")
    if not due:
        return False

    try:
        due_date = datetime.fromisoformat(due.replace("Z", "+00:00")).date()
        today = datetime.now(UTC).date()
        return due_date <= today
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"Could not parse due date for task {task.get('id', 'unknown')}: {e}")
        return False


def get_overdue_tasks(tasks: list[dict]) -> list[dict]:
    """Get tasks that are overdue."""
    today = datetime.now(UTC).date()
    overdue = []

    for task in tasks:
        due = task.get("due")
        if not due:
            continue
        try:
            due_date = datetime.fromisoformat(due.replace("Z", "+00:00")).date()
            if due_date < today:
                overdue.append(task)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse due date for task {task.get('id', 'unknown')}: {e}")

    return overdue


def get_due_today(tasks: list[dict]) -> list[dict]:
    """Get tasks due today."""
    today = datetime.now(UTC).date()
    due_today = []

    for task in tasks:
        due = task.get("due")
        if not due:
            continue
        try:
            due_date = datetime.fromisoformat(due.replace("Z", "+00:00")).date()
            if due_date == today:
                due_today.append(task)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse due date for task {task.get('id', 'unknown')}: {e}")

    return due_today


def get_upcoming_events(events: list[dict], hours: int = 2) -> list[dict]:
    """Get events starting within N hours."""
    now = datetime.now(UTC)
    cutoff = now + timedelta(hours=hours)
    upcoming = []

    for event in events:
        start = event.get("start", {}).get("dateTime")
        if not start:
            continue
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if now <= start_dt <= cutoff:
                upcoming.append(event)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse event start time: {e}")

    return upcoming


def process_heartbeat() -> tuple[bool, str]:
    """
    Process heartbeat and return (needs_attention, message).

    Returns:
        - (False, "") if nothing needs attention (HEARTBEAT_OK)
        - (True, message) if something needs to be surfaced
    """
    data = load_cached_data()
    datetime.now(UTC)
    alerts = []

    # Check for upcoming events (< 2 hours)
    events = data.get("calendar", {}).get("events", [])
    upcoming = get_upcoming_events(events, hours=2)
    for event in upcoming:
        summary = event.get("summary", "No title")
        start = event.get("start", {}).get("dateTime", "?")
        alerts.append(f"📅 **Upcoming ({start[:16]}):** {summary}")

    # Check for urgent NEW emails
    threads = data.get("gmail", {}).get("threads", [])
    new_threads = filter_new_items("gmail", threads, ["id"])
    urgent_new = [t for t in new_threads if is_urgent_email(t)]
    for t in urgent_new[:3]:  # Max 3
        sender = t.get("from", "Unknown")[:30]
        subject = t.get("subject", "No subject")[:50]
        alerts.append(f"📧 **Urgent email:** {sender} — {subject}")

    # Check for NEW chat mentions
    messages = data.get("chat", {}).get("messages", [])
    mentions = [m for m in messages if "@molham" in (m.get("text") or "").lower()]
    new_mentions = filter_new_items("chat", mentions, ["id", "text"])
    for m in new_mentions[:3]:
        space = m.get("_space_name", m.get("space_name", "Unknown"))[:20]
        text = (m.get("text") or "")[:60]
        alerts.append(f"💬 **Chat mention ({space}):** {text}")

    # Check Time OS database for overdue/due today
    if TIME_OS_DB_AVAILABLE and overdue is not None:
        try:
            overdue_items = overdue()
            if overdue_items:
                alerts.append(f"⚠️ **{len(overdue_items)} overdue items**")

            today_items = due_today_fn() if due_today_fn else []
            if today_items:
                alerts.append(f"📋 **{len(today_items)} items due today**")
        except (sqlite3.Error, ValueError, OSError):
            logger.debug("Database not initialized for heartbeat alerts")

    # Fallback: check Google Tasks for overdue (if no Time OS)
    if not TIME_OS_DB_AVAILABLE:
        tasks = data.get("tasks", {}).get("tasks", [])
        overdue_tasks = get_overdue_tasks(tasks)
        if overdue_tasks:
            alerts.append(f"⚠️ **{len(overdue_tasks)} overdue tasks**")

        due_today_tasks = get_due_today(tasks)
        if due_today_tasks:
            alerts.append(f"📋 **{len(due_today_tasks)} tasks due today**")

    # Mark what we surfaced
    if urgent_new:
        mark_surfaced("gmail", urgent_new, ["id"])
    if new_mentions:
        mark_surfaced("chat", new_mentions, ["id", "text"])

    if alerts:
        message = "\n".join(alerts)
        return True, message

    return False, ""


def get_full_status() -> str:
    """Get full status for morning brief or on-demand."""
    data = load_cached_data()
    lines = []

    # Calendar
    events = data.get("calendar", {}).get("events", [])
    if events:
        lines.append(f"## Calendar — {len(events)} events next 48h")
        for e in events[:5]:
            summary = e.get("summary", "No title")
            start = e.get("start", {}).get("dateTime", "?")[:16]
            lines.append(f"- {start}: {summary}")
        if len(events) > 5:
            lines.append(f"  ... +{len(events) - 5} more")
        lines.append("")

    # Gmail
    threads = data.get("gmail", {}).get("threads", [])
    if threads:
        lines.append(f"## Gmail — {len(threads)} unread")
        for t in threads[:5]:
            sender = t.get("from", "?")[:25]
            subject = t.get("subject", "?")[:40]
            lines.append(f"- {sender}: {subject}")
        if len(threads) > 5:
            lines.append(f"  ... +{len(threads) - 5} more")
        lines.append("")

    # Tasks
    tasks = data.get("tasks", {}).get("tasks", [])
    overdue = get_overdue_tasks(tasks)
    due_today = get_due_today(tasks)

    if overdue:
        lines.append(f"## ⚠️ Overdue — {len(overdue)} tasks")
        for t in overdue[:5]:
            title = t.get("title", "?")[:50]
            lines.append(f"- {title}")
        if len(overdue) > 5:
            lines.append(f"  ... +{len(overdue) - 5} more")
        lines.append("")

    if due_today:
        lines.append(f"## Due Today — {len(due_today)} tasks")
        for t in due_today[:5]:
            title = t.get("title", "?")[:50]
            lines.append(f"- {title}")
        if len(due_today) > 5:
            lines.append(f"  ... +{len(due_today) - 5} more")
        lines.append("")

    # Chat mentions
    messages = data.get("chat", {}).get("messages", [])
    mentions = [m for m in messages if "@molham" in (m.get("text") or "").lower()]
    if mentions:
        lines.append(f"## Chat Mentions — {len(mentions)}")
        for m in mentions[:3]:
            space = m.get("space_name", "?")[:20]
            text = (m.get("text") or "")[:50]
            lines.append(f"- [{space}] {text}")
        lines.append("")

    return "\n".join(lines) if lines else "All clear."


if __name__ == "__main__":
    needs_attention, message = process_heartbeat()
    if needs_attention:
        logger.info("NEEDS ATTENTION:")
        logger.info(message)
    else:
        logger.info("HEARTBEAT_OK")
