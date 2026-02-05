#!/usr/bin/env python3
"""
Briefing generator for scheduled operational updates.

Briefing windows (Dubai time, UTC+4):
- Daily Ops Brief: 09:00
- Midday Execution Pulse: 13:00-14:00
- End-of-Day Closeout: 19:30-20:00
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DUBAI_OFFSET = timedelta(hours=4)


def get_dubai_time() -> datetime:
    """Get current time in Dubai."""
    return datetime.now(timezone.utc) + DUBAI_OFFSET


def determine_briefing_type() -> str:
    """Determine which briefing type based on current Dubai time."""
    now = get_dubai_time()
    hour = now.hour
    
    if 8 <= hour < 10:
        return "morning"
    elif 12 <= hour < 15:
        return "midday"
    elif 19 <= hour < 21:
        return "evening"
    else:
        return "adhoc"


def generate_morning_brief() -> str:
    """
    Daily Ops Brief (09:00)
    
    Focus: What needs attention today
    """
    lines = [
        "# ☀️ Daily Ops Brief",
        f"*{get_dubai_time().strftime('%A, %B %d %Y • %H:%M')} Dubai*",
        "",
        "---",
        "",
    ]
    
    # Import collectors
    try:
        from generate_queue import (
            collect_calendar, collect_gmail, collect_chat_mentions,
            collect_time_os_items
        )
        from lanes import categorize_email
        
        # Today's calendar
        events = collect_calendar()
        lines.append("## 📅 Today's Schedule")
        if events:
            for e in events[:8]:
                summary = e.get("summary", "No title")
                start = e.get("start", {}).get("dateTime", "")
                if "T" in start:
                    time_str = start[11:16]
                    lines.append(f"- **{time_str}** {summary}")
        else:
            lines.append("- No meetings scheduled")
        lines.append("")
        
        # Urgent items
        items = collect_time_os_items()
        if "error" not in items:
            overdue = items.get("overdue", [])
            today = items.get("due_today", [])
            
            if overdue or today:
                lines.append("## 🎯 Must Handle Today")
                for i in today[:5]:
                    lines.append(f"- {i['what']}")
                if overdue:
                    lines.append(f"- ⚠️ {len(overdue)} overdue items need attention")
                lines.append("")
        
        # Top emails by lane
        threads = collect_gmail()
        if threads:
            lines.append("## 📧 Priority Inbox")
            finance = [t for t in threads if "invoice" in t.get("subject", "").lower() or "payment" in t.get("subject", "").lower()][:2]
            for t in finance:
                lines.append(f"- 💰 {t.get('subject', '')[:50]}")
            lines.append("")
        
        # Chat mentions
        mentions = collect_chat_mentions()
        if mentions:
            lines.append(f"## 💬 {len(mentions)} Chat Mentions Pending")
            for m in mentions[:3]:
                text = m.get("text", "")[:60]
                lines.append(f"- {text}")
            lines.append("")
            
    except Exception as e:
        lines.append(f"*Error generating brief: {e}*")
    
    return "\n".join(lines)


def generate_midday_pulse() -> str:
    """
    Midday Execution Pulse (13:00-14:00)
    
    Focus: Progress check, blockers, afternoon priorities
    """
    lines = [
        "# 🔄 Midday Execution Pulse",
        f"*{get_dubai_time().strftime('%A, %B %d %Y • %H:%M')} Dubai*",
        "",
        "---",
        "",
    ]
    
    try:
        from generate_queue import collect_calendar, collect_time_os_items
        
        # Afternoon calendar
        events = collect_calendar()
        afternoon = [e for e in events if "T" in e.get("start", {}).get("dateTime", "") 
                     and int(e.get("start", {}).get("dateTime", "T00")[11:13]) >= 12][:5]
        
        lines.append("## 📅 Afternoon")
        if afternoon:
            for e in afternoon:
                time_str = e.get("start", {}).get("dateTime", "")[11:16]
                lines.append(f"- **{time_str}** {e.get('summary', '')}")
        else:
            lines.append("- Clear — focus time available")
        lines.append("")
        
        # Still due today
        items = collect_time_os_items()
        if "error" not in items:
            today = items.get("due_today", [])
            if today:
                lines.append("## ⏰ Still Due Today")
                for i in today:
                    lines.append(f"- {i['what']}")
                lines.append("")
        
        # Read ops ledger for blockers
        ledger_path = Path(__file__).parent.parent / "OPS_LEDGER.md"
        if ledger_path.exists():
            lines.append("## 🚧 Check Blockers")
            lines.append("*See OPS_LEDGER.md for current blockers and waiting-for items*")
            lines.append("")
            
    except Exception as e:
        lines.append(f"*Error: {e}*")
    
    return "\n".join(lines)


def generate_evening_closeout() -> str:
    """
    End-of-Day Closeout (19:30-20:00)
    
    Focus: What got done, what carries over, tomorrow prep
    """
    lines = [
        "# 🌙 End-of-Day Closeout",
        f"*{get_dubai_time().strftime('%A, %B %d %Y • %H:%M')} Dubai*",
        "",
        "---",
        "",
    ]
    
    try:
        from generate_queue import collect_calendar, collect_time_os_items
        
        # Tomorrow preview
        lines.append("## 📅 Tomorrow Preview")
        events = collect_calendar()
        # Filter for tomorrow (rough heuristic)
        tomorrow = [e for e in events if "02-02" in e.get("start", {}).get("dateTime", "")][:5]
        if tomorrow:
            for e in tomorrow:
                time_str = e.get("start", {}).get("dateTime", "")[11:16]
                lines.append(f"- **{time_str}** {e.get('summary', '')}")
        else:
            lines.append("- No meetings scheduled")
        lines.append("")
        
        # Carryover
        items = collect_time_os_items()
        if "error" not in items:
            overdue = items.get("overdue", [])
            today = items.get("due_today", [])
            if overdue or today:
                lines.append("## 📋 Carryover")
                lines.append(f"- {len(today)} items still marked due today")
                lines.append(f"- {len(overdue)} overdue items")
                lines.append("")
        
        lines.append("## ✅ Update OPS_LEDGER.md")
        lines.append("- Update priorities for tomorrow")
        lines.append("- Clear completed items")
        lines.append("- Note any new blockers or waiting-for items")
        lines.append("")
        
    except Exception as e:
        lines.append(f"*Error: {e}*")
    
    return "\n".join(lines)


def generate_briefing(briefing_type: str = None) -> str:
    """Generate appropriate briefing based on time or explicit type."""
    if briefing_type is None:
        briefing_type = determine_briefing_type()
    
    if briefing_type == "morning":
        return generate_morning_brief()
    elif briefing_type == "midday":
        return generate_midday_pulse()
    elif briefing_type == "evening":
        return generate_evening_closeout()
    else:
        # Adhoc - just run queue generator
        from generate_queue import generate_queue
        return generate_queue()


if __name__ == "__main__":
    import sys
    
    # Allow explicit type override
    if len(sys.argv) > 1:
        btype = sys.argv[1]
    else:
        btype = None
    
    print(generate_briefing(btype))
