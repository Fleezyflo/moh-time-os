#!/usr/bin/env python3
"""Run all collectors and generate OPERATOR_QUEUE.md."""

import json
from datetime import datetime, timezone
from pathlib import Path

from calendar_collector import collect_calendar, save as save_calendar
from gmail import collect_gmail, save as save_gmail
from tasks import collect_tasks, save as save_tasks
from chat import collect_chat, save as save_chat

OUT_DIR = Path(__file__).parent.parent / "out"


def collect_all():
    """Run all collectors."""
    print("Collecting calendar...")
    cal = collect_calendar()
    save_calendar(cal)
    
    print("Collecting gmail...")
    gmail = collect_gmail()
    save_gmail(gmail)
    
    print("Collecting tasks...")
    tasks = collect_tasks()
    save_tasks(tasks)
    
    print("Collecting chat...")
    chat = collect_chat()
    save_chat(chat)
    
    return {
        "calendar": cal,
        "gmail": gmail,
        "tasks": tasks,
        "chat": chat
    }


def generate_queue(data: dict) -> str:
    """Generate OPERATOR_QUEUE.md from collected data."""
    now = datetime.now(timezone.utc)
    lines = [
        "# Time OS — Operator Queue",
        f"Generated: {now.isoformat()}",
        "",
        "---",
        ""
    ]
    
    # Calendar section
    events = data.get("calendar", {}).get("events", [])
    lines.append("## Calendar (next 48h)")
    if events:
        for e in events[:10]:
            summary = e.get("summary", "No title")
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "?"))
            lines.append(f"- {start}: {summary}")
    else:
        lines.append("- No upcoming events")
    lines.append("")
    
    # Gmail section
    threads = data.get("gmail", {}).get("threads", [])
    lines.append(f"## Gmail Unread ({len(threads)})")
    if threads:
        for t in threads[:15]:
            subj = t.get("subject", "No subject")
            sender = t.get("from", "Unknown")
            date = t.get("date", "?")
            lines.append(f"- [{date}] {sender}: {subj}")
    else:
        lines.append("- Inbox zero 🎉")
    lines.append("")
    
    # Tasks section
    tasks = data.get("tasks", {}).get("tasks", [])
    # Filter to incomplete tasks
    incomplete = [t for t in tasks if t.get("status") != "completed"]
    lines.append(f"## Tasks ({len(incomplete)} incomplete)")
    if incomplete:
        for t in incomplete[:15]:
            title = t.get("title", "No title")
            list_name = t.get("_list_name", "")
            due = t.get("due", "")
            due_str = f" (due {due[:10]})" if due else ""
            lines.append(f"- [{list_name}] {title}{due_str}")
    else:
        lines.append("- All tasks complete 🎉")
    lines.append("")
    
    # Chat mentions section
    mentions = data.get("chat", {}).get("mentions", [])
    lines.append(f"## Chat Mentions ({len(mentions)})")
    if mentions:
        for m in mentions[:10]:
            space = m.get("_space_name", "?")
            text = m.get("text", "")[:100]
            sender = m.get("sender", {}).get("name", "Unknown")
            uri = m.get("_space_uri", "")
            lines.append(f"- [{space}] {text}")
            if uri:
                lines.append(f"  - open: {uri}")
    else:
        lines.append("- No unread mentions")
    lines.append("")
    
    return "\n".join(lines)


def save_queue(content: str):
    """Save OPERATOR_QUEUE.md."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "OPERATOR_QUEUE.md"
    with open(path, "w") as f:
        f.write(content)
    return path


if __name__ == "__main__":
    data = collect_all()
    queue = generate_queue(data)
    path = save_queue(queue)
    print(f"\nSaved OPERATOR_QUEUE.md to {path}")
