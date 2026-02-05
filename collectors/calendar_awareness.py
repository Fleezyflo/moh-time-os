#!/usr/bin/env python3
"""
Calendar awareness for Time OS.

Provides:
- Meeting prep reminders
- Time blocking suggestions
- Calendar context for work items
- Conflict detection
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

# Deep work windows from discovery (hours in local time, Dubai = UTC+4)
DEEP_WORK_WINDOWS = [9, 13, 15, 18]  # 9am, 1pm, 3pm, 6pm

# Meeting prep time requirements (minutes)
PREP_REQUIREMENTS = {
    "default": 15,
    "kick-off": 30,
    "client": 30,
    "all-hands": 10,
    "weekly": 10,
    "1:1": 5,
    "interview": 20,
    "presentation": 45,
    "review": 20,
}


def run_gog(args: list, timeout: int = 30) -> tuple[bool, dict | str]:
    """Run a gog command and return (success, result)."""
    cmd = ["gog"] + args + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr or "Unknown error"
        return True, json.loads(result.stdout) if result.stdout.strip() else {}
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {e}"


def get_upcoming_events(hours: int = 24) -> list:
    """Get calendar events for the next N hours."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    
    args = [
        "calendar", "events", "primary",
        "--from", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    
    success, result = run_gog(args)
    if not success:
        return []
    
    events = result.get("events", [])
    parsed = []
    
    for e in events:
        start_str = e.get("start", {}).get("dateTime", e.get("start", {}).get("date"))
        end_str = e.get("end", {}).get("dateTime", e.get("end", {}).get("date"))
        
        try:
            if "T" in start_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            else:
                start_dt = datetime.fromisoformat(start_str)
            
            if "T" in end_str:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            else:
                end_dt = datetime.fromisoformat(end_str)
        except:
            continue
        
        parsed.append({
            "id": e.get("id"),
            "summary": e.get("summary", "No title"),
            "start": start_dt,
            "end": end_dt,
            "location": e.get("location"),
            "description": e.get("description", ""),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
        })
    
    return sorted(parsed, key=lambda x: x["start"])


def get_prep_time(event_title: str) -> int:
    """Determine prep time needed for a meeting based on title."""
    title_lower = event_title.lower()
    
    for keyword, minutes in PREP_REQUIREMENTS.items():
        if keyword in title_lower:
            return minutes
    
    return PREP_REQUIREMENTS["default"]


def generate_prep_reminders(hours_ahead: int = 4) -> list:
    """
    Generate prep reminders for upcoming meetings.
    
    Returns list of reminders with: event, prep_time, reminder_time
    """
    events = get_upcoming_events(hours_ahead)
    now = datetime.now(timezone.utc)
    reminders = []
    
    for event in events:
        prep_minutes = get_prep_time(event["summary"])
        reminder_time = event["start"] - timedelta(minutes=prep_minutes)
        
        # Only include if reminder time is in the future
        if reminder_time > now:
            reminders.append({
                "event": event["summary"],
                "event_start": event["start"].isoformat(),
                "prep_minutes": prep_minutes,
                "reminder_time": reminder_time.isoformat(),
                "attendees": len(event["attendees"]),
            })
    
    return reminders


def find_free_slots(date: datetime = None, min_duration_hours: float = 1.0) -> list:
    """
    Find free time slots on a given day.
    
    Returns list of: {"start": datetime, "end": datetime, "duration_hours": float}
    """
    if date is None:
        date = datetime.now(timezone.utc)
    
    # Get events for the day
    day_start = date.replace(hour=8, minute=0, second=0, microsecond=0)  # 8am
    day_end = date.replace(hour=20, minute=0, second=0, microsecond=0)   # 8pm
    
    args = [
        "calendar", "events", "primary",
        "--from", day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    
    success, result = run_gog(args)
    if not success:
        return []
    
    events = result.get("events", [])
    
    # Parse event times
    busy_periods = []
    for e in events:
        start_str = e.get("start", {}).get("dateTime", e.get("start", {}).get("date"))
        end_str = e.get("end", {}).get("dateTime", e.get("end", {}).get("date"))
        
        try:
            if "T" in start_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                busy_periods.append((start_dt, end_dt))
        except:
            continue
    
    # Sort by start time
    busy_periods.sort(key=lambda x: x[0])
    
    # Find free slots
    free_slots = []
    current = day_start
    
    for busy_start, busy_end in busy_periods:
        if current < busy_start:
            duration = (busy_start - current).total_seconds() / 3600
            if duration >= min_duration_hours:
                free_slots.append({
                    "start": current,
                    "end": busy_start,
                    "duration_hours": round(duration, 1),
                })
        current = max(current, busy_end)
    
    # Check remaining time after last meeting
    if current < day_end:
        duration = (day_end - current).total_seconds() / 3600
        if duration >= min_duration_hours:
            free_slots.append({
                "start": current,
                "end": day_end,
                "duration_hours": round(duration, 1),
            })
    
    return free_slots


def suggest_time_blocks(task_duration_hours: float = 2.0) -> list:
    """
    Suggest time blocks for focused work based on:
    - Free slots in calendar
    - Preferred deep work windows from discovery
    """
    free_slots = find_free_slots(min_duration_hours=task_duration_hours)
    suggestions = []
    
    for slot in free_slots:
        start_hour = slot["start"].hour
        
        # Check if slot overlaps with preferred deep work windows
        is_preferred = any(
            slot["start"].hour <= dw < slot["end"].hour
            for dw in DEEP_WORK_WINDOWS
        )
        
        suggestions.append({
            "start": slot["start"].strftime("%H:%M"),
            "end": slot["end"].strftime("%H:%M"),
            "duration": slot["duration_hours"],
            "preferred": is_preferred,
            "reason": "Deep work window" if is_preferred else "Available slot",
        })
    
    # Sort with preferred windows first
    suggestions.sort(key=lambda x: (not x["preferred"], x["start"]))
    
    return suggestions


def get_calendar_context_for_task(task_title: str, due_date: str = None) -> dict:
    """
    Get calendar context relevant to a task.
    
    Returns:
    - related_meetings: meetings that might relate to this task
    - suggested_blocks: when to work on it
    - conflicts: potential scheduling issues
    """
    events = get_upcoming_events(hours=72)  # Next 3 days
    task_lower = task_title.lower()
    
    # Find related meetings
    related = []
    keywords = task_lower.split()
    
    for event in events:
        event_lower = event["summary"].lower()
        # Check for keyword overlap
        if any(kw in event_lower for kw in keywords if len(kw) > 3):
            related.append({
                "meeting": event["summary"],
                "when": event["start"].strftime("%Y-%m-%d %H:%M"),
            })
    
    # Get time block suggestions
    suggestions = suggest_time_blocks()
    
    return {
        "related_meetings": related[:3],
        "suggested_blocks": suggestions[:3],
        "task": task_title,
    }


if __name__ == "__main__":
    print("Calendar Awareness Test")
    print("=" * 50)
    
    print("\n📅 Upcoming Events (24h):")
    events = get_upcoming_events(24)
    for e in events[:5]:
        print(f"  - {e['start'].strftime('%H:%M')}: {e['summary']}")
    
    print("\n⏰ Prep Reminders:")
    reminders = generate_prep_reminders(hours_ahead=24)
    for r in reminders[:3]:
        print(f"  - {r['event']}: {r['prep_minutes']}min prep needed")
    
    print("\n🎯 Free Slots (1h+ blocks):")
    slots = find_free_slots()
    for s in slots[:3]:
        print(f"  - {s['start'].strftime('%H:%M')}-{s['end'].strftime('%H:%M')} ({s['duration_hours']}h)")
    
    print("\n💡 Time Block Suggestions:")
    suggestions = suggest_time_blocks()
    for s in suggestions[:3]:
        pref = "★" if s["preferred"] else " "
        print(f"  {pref} {s['start']}-{s['end']} — {s['reason']}")
