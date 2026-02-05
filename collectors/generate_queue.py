#!/usr/bin/env python3
"""Generate OPERATOR_QUEUE.md from latest snapshots."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Import lanes categorization
try:
    from lanes import categorize_email, LANES
    LANES_AVAILABLE = True
except ImportError:
    LANES_AVAILABLE = False

# Import calendar awareness
try:
    from calendar_awareness import generate_prep_reminders, suggest_time_blocks
    CALENDAR_AWARENESS_AVAILABLE = True
except ImportError:
    CALENDAR_AWARENESS_AVAILABLE = False

# Import delegation suggestions
try:
    from delegation import format_delegation_suggestion, can_delegate
    DELEGATION_AVAILABLE = True
except ImportError:
    DELEGATION_AVAILABLE = False

# Import Asana ops
try:
    from asana_ops import generate_asana_report, format_report as format_asana_report
    ASANA_OPS_AVAILABLE = True
except ImportError:
    ASANA_OPS_AVAILABLE = False

# Import Xero ops
try:
    from xero_ops import generate_xero_report, format_report as format_xero_report
    XERO_OPS_AVAILABLE = True
except ImportError:
    XERO_OPS_AVAILABLE = False

# Import Promise tracker
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
try:
    from promise_tracker import generate_promise_report, format_report as format_promise_report
    PROMISE_TRACKER_AVAILABLE = True
except ImportError:
    PROMISE_TRACKER_AVAILABLE = False

OUT_DIR = Path(__file__).parent.parent / "out"


def collect_calendar():
    """Fetch calendar events for next 48h."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    end = now + timedelta(hours=48)
    
    cmd = [
        "gog", "calendar", "events", "primary",
        "--from", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return []
    return json.loads(result.stdout).get("events", [])


def collect_gmail():
    """Fetch unread inbox threads."""
    cmd = ["gog", "gmail", "search", "is:unread in:inbox", "--max", "50", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return []
    return json.loads(result.stdout).get("threads", [])


def collect_chat_mentions():
    """Fetch recent chat mentions (optimized - only check key spaces)."""
    # Get spaces
    cmd = ["gog", "chat", "spaces", "list", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return []
    
    spaces = json.loads(result.stdout).get("spaces", [])
    mentions = []
    
    # Only check first 5 spaces to avoid timeout
    for space in spaces[:5]:
        space_id = space.get("resource", "").replace("spaces/", "")
        if not space_id:
            continue
        
        cmd = ["gog", "chat", "messages", "list", space_id, "--max", "5", "--json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                msgs = json.loads(result.stdout).get("messages", [])
                for msg in msgs:
                    text = msg.get("text", "")
                    if "@Molham" in text or "molham" in text.lower():
                        msg["_space_name"] = space.get("name", "?")
                        msg["_space_uri"] = space.get("uri", "")
                        mentions.append(msg)
        except:
            pass
    
    return mentions


def collect_tasks():
    """Get incomplete tasks from main list."""
    MAIN_LIST_ID = "c0VUdndncDZlYU9zM3FWRA"
    cmd = ["gog", "tasks", "list", MAIN_LIST_ID, "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        tasks = data.get("tasks", [])
        return [t for t in tasks if t.get("status") != "completed"]
    except:
        return []


def collect_time_os_items():
    """Get open/overdue items from Time OS."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from lib.queries import overdue, due_today, due_this_week
        
        return {
            "overdue": [{"what": i.what, "due": i.due, "client": i.client_id} for i in overdue()[:10]],
            "due_today": [{"what": i.what, "due": i.due} for i in due_today()[:5]],
            "due_week": [{"what": i.what, "due": i.due} for i in due_this_week()[:5]],
        }
    except Exception as e:
        return {"error": str(e)}


def generate_queue() -> str:
    """Generate OPERATOR_QUEUE.md."""
    now = datetime.now(timezone.utc)
    
    print("Collecting calendar...")
    events = collect_calendar()
    
    print("Collecting gmail...")
    threads = collect_gmail()
    
    print("Collecting chat mentions...")
    mentions = collect_chat_mentions()
    
    print("Collecting tasks...")
    tasks = collect_tasks()
    
    print("Collecting Time OS items...")
    items = collect_time_os_items()
    
    # Collect Asana ops (workflow hygiene)
    asana_report = None
    if ASANA_OPS_AVAILABLE:
        print("Collecting Asana ops...")
        try:
            asana_report = generate_asana_report()
        except Exception as e:
            print(f"Asana ops error: {e}")
    
    # Collect Xero ops (AR, invoices)
    xero_report = None
    if XERO_OPS_AVAILABLE:
        print("Collecting Xero AR...")
        try:
            xero_report = generate_xero_report()
        except Exception as e:
            print(f"Xero ops error: {e}")
    
    # Collect Promise debt
    promise_report = None
    if PROMISE_TRACKER_AVAILABLE:
        print("Collecting promise debt...")
        try:
            promise_report = generate_promise_report()
        except Exception as e:
            print(f"Promise tracker error: {e}")
    
    lines = [
        "# Time OS — Operator Queue",
        f"Generated: {now.isoformat()}",
        "",
        "---",
        ""
    ]
    
    # Calendar
    lines.append(f"## Calendar (next 48h) — {len(events)} events")
    if events:
        for e in events[:10]:
            summary = e.get("summary", "No title")
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "?"))
            if "T" in start:
                start = start[:16].replace("T", " ")
            lines.append(f"- {start}: {summary}")
    else:
        lines.append("- No upcoming events")
    lines.append("")
    
    # Prep Reminders & Time Blocks (Calendar Awareness)
    if CALENDAR_AWARENESS_AVAILABLE:
        reminders = generate_prep_reminders(hours_ahead=8)
        if reminders:
            lines.append("### ⏰ Prep Reminders")
            for r in reminders[:3]:
                lines.append(f"- {r['event']}: prep {r['prep_minutes']}min before start")
            lines.append("")
        
        blocks = suggest_time_blocks(task_duration_hours=1.5)
        if blocks:
            lines.append("### 🎯 Focus Time Available")
            for b in blocks[:2]:
                pref = "★" if b["preferred"] else ""
                lines.append(f"- {b['start']}–{b['end']} ({b['duration']}h) {pref}")
            lines.append("")
    
    # Gmail - filter and prioritize
    # Filter out promotional/low-priority
    noise_domains = ['ounass.com', 'tabby.ai', 'americaneagle', 'boots', 'dubaichamber', 'paddle.com', 'tax.gov', 'forsah']
    noise_subjects = ['buy', 'sale', 'off', 'discount', 'free', 'promotion', 'newsletter']
    
    important = []
    other = []
    for t in threads:
        sender = t.get("from", "").lower()
        subj = t.get("subject", "").lower()
        
        is_noise = any(d in sender for d in noise_domains) or any(s in subj for s in noise_subjects)
        
        if is_noise:
            other.append(t)
        else:
            important.append(t)
    
    lines.append(f"## Gmail — {len(important)} important, {len(other)} other")
    
    # Categorize by lane if available
    by_lane = {}
    if LANES_AVAILABLE and important:
        for t in important:
            subj = t.get("subject", "")
            sender = t.get("from", "")
            cat = categorize_email(subj, sender)
            lane = cat.get("lane", "Uncategorized")
            if lane not in by_lane:
                by_lane[lane] = []
            by_lane[lane].append(t)
    
    if by_lane:
        # Show by lane
        for lane in ["Finance", "People", "Creative", "Sales", "Operations", "Personal", "Uncategorized"]:
            if lane in by_lane and by_lane[lane]:
                lines.append(f"### {lane} ({len(by_lane[lane])})")
                for t in by_lane[lane][:5]:
                    subj = t.get("subject", "No subject")[:50]
                    sender = t.get("from", "Unknown")
                    if "<" in sender:
                        sender = sender.split("<")[0].strip()[:20]
                    date = t.get("date", "?")
                    lines.append(f"- [{date}] {sender}: {subj}")
                if len(by_lane[lane]) > 5:
                    lines.append(f"  ... +{len(by_lane[lane]) - 5} more")
    elif important:
        for t in important[:15]:
            subj = t.get("subject", "No subject")[:60]
            sender = t.get("from", "Unknown")
            if "<" in sender:
                sender = sender.split("<")[0].strip()
            date = t.get("date", "?")
            lines.append(f"- [{date}] {sender}: {subj}")
    else:
        lines.append("- No important unread")
    lines.append("")
    
    # Chat mentions
    lines.append(f"## Chat Mentions — {len(mentions)}")
    if mentions:
        for m in mentions[:10]:
            space = m.get("_space_name", "?")
            text = m.get("text", "")[:80].replace("\n", " ")
            uri = m.get("_space_uri", "")
            lines.append(f"- [{space}] {text}")
            if uri:
                lines.append(f"  → {uri}")
    else:
        lines.append("- No recent mentions")
    lines.append("")
    
    # Google Tasks
    if tasks:
        lines.append(f"## Google Tasks — {len(tasks)} incomplete")
        for t in tasks[:10]:
            title = t.get("title", "No title")
            due = t.get("due", "")
            due_str = f" (due {due[:10]})" if due else ""
            lines.append(f"- {title}{due_str}")
        if len(tasks) > 10:
            lines.append(f"  ... and {len(tasks) - 10} more")
        lines.append("")
    
    # Time OS Items
    if "error" not in items:
        overdue_items = items.get("overdue", [])
        today_items = items.get("due_today", [])
        week_items = items.get("due_week", [])
        
        if overdue_items:
            lines.append(f"## ⚠️ Overdue Items — {len(overdue_items)}")
            for i in overdue_items[:5]:
                task_text = i['what']
                lines.append(f"- {task_text}")
                # Add delegation suggestion if available
                if DELEGATION_AVAILABLE:
                    suggestion = format_delegation_suggestion(task_text)
                    if suggestion:
                        lines.append(f"  {suggestion}")
            if len(overdue_items) > 5:
                lines.append(f"  ... and {len(overdue_items) - 5} more")
            lines.append("")
        
        if today_items:
            lines.append(f"## Due Today — {len(today_items)}")
            for i in today_items:
                task_text = i['what']
                lines.append(f"- {task_text}")
                # Add delegation suggestion if available
                if DELEGATION_AVAILABLE:
                    suggestion = format_delegation_suggestion(task_text)
                    if suggestion:
                        lines.append(f"  {suggestion}")
            lines.append("")
        
        if week_items:
            lines.append(f"## Due This Week — {len(week_items)}")
            for i in week_items:
                task_text = i['what']
                lines.append(f"- {task_text} (due {i['due']})")
                # Add delegation suggestion if available
                if DELEGATION_AVAILABLE:
                    suggestion = format_delegation_suggestion(task_text)
                    if suggestion:
                        lines.append(f"  {suggestion}")
            lines.append("")
    
    # Asana Operational Intelligence
    if asana_report:
        lines.append("---")
        lines.append("")
        lines.append("## 🔧 Asana Workflow Health")
        lines.append(f"Total incomplete: {asana_report.get('total_tasks', 0)}")
        lines.append("")
        
        # Overdue (top 5 only, with recent ones first)
        overdue = asana_report.get("overdue", [])
        recent_overdue = [t for t in overdue if t.get("days_overdue", 0) < 30][:5]
        if recent_overdue:
            lines.append(f"### ⚠️ Recently Overdue ({len(recent_overdue)} of {len(overdue)} total)")
            for t in recent_overdue:
                days = t.get("days_overdue", 0)
                assignee = t.get("assignee") or "unassigned"
                lines.append(f"- {t['name']} ({days}d) — {assignee}")
            lines.append("")
        
        # Stale tasks
        stale = asana_report.get("stale", [])
        if stale:
            lines.append(f"### 🔇 Stale ({len(stale)})")
            for t in stale[:3]:
                days = t.get("days_stale", 0)
                assignee = t.get("assignee") or "unassigned"
                lines.append(f"- {t['name']} ({days}d no activity)")
            if len(stale) > 3:
                lines.append(f"  ... +{len(stale) - 3} more")
            lines.append("")
        
        # Missing assignee (just count)
        no_assignee = asana_report.get("no_assignee", [])
        no_due = asana_report.get("no_due_date", [])
        if no_assignee or no_due:
            lines.append("### 📋 Hygiene Issues")
            if no_assignee:
                lines.append(f"- {len(no_assignee)} tasks missing assignee")
            if no_due:
                lines.append(f"- {len(no_due)} tasks missing due date")
            lines.append("")
    
    # Xero AR Intelligence
    if xero_report:
        total_ar = xero_report.get("total_ar", 0)
        overdue_amount = xero_report.get("overdue_amount", 0)
        overdue_count = xero_report.get("overdue_count", 0)
        
        if total_ar > 0:
            lines.append("## 💰 Accounts Receivable")
            lines.append(f"**Total AR:** AED {total_ar:,.2f}")
            if overdue_amount > 0:
                lines.append(f"**⚠️ Overdue:** AED {overdue_amount:,.2f} ({overdue_count} invoices)")
            lines.append("")
            
            # Show top overdue
            overdue_invoices = xero_report.get("overdue_invoices", [])
            if overdue_invoices:
                lines.append("### Overdue Invoices")
                for inv in overdue_invoices[:5]:
                    days = inv["days_overdue"]
                    lines.append(
                        f"- {inv['contact']}: AED {inv['amount_due']:,.2f} "
                        f"({days}d) — #{inv['number']}"
                    )
                if len(overdue_invoices) > 5:
                    lines.append(f"  ... +{len(overdue_invoices) - 5} more")
                lines.append("")
    
    # Promise Debt
    if promise_report:
        overdue_promises = promise_report.get("overdue", [])
        due_today_promises = promise_report.get("due_today", [])
        due_soon_promises = promise_report.get("due_soon", [])
        
        if overdue_promises or due_today_promises or due_soon_promises:
            lines.append("## 🤝 Promise Debt")
            lines.append("")
            
            if overdue_promises:
                lines.append(f"### ⚠️ Overdue Promises ({len(overdue_promises)})")
                for p in overdue_promises[:3]:
                    action = p.get("action", "")[:50]
                    to = p.get("to", "")
                    days = p.get("days_overdue", 0)
                    line = f"- {action}"
                    if to:
                        line += f" → {to}"
                    line += f" ({days}d overdue)"
                    lines.append(line)
                lines.append("")
            
            if due_today_promises:
                lines.append(f"### 📅 Promises Due Today ({len(due_today_promises)})")
                for p in due_today_promises[:3]:
                    action = p.get("action", "")[:50]
                    to = p.get("to", "")
                    line = f"- {action}"
                    if to:
                        line += f" → {to}"
                    lines.append(line)
                lines.append("")
            
            if due_soon_promises:
                lines.append(f"### 🔜 Promises Due Soon ({len(due_soon_promises)})")
                for p in due_soon_promises[:3]:
                    action = p.get("action", "")[:50]
                    to = p.get("to", "")
                    due = p.get("due", "")
                    line = f"- {action}"
                    if to:
                        line += f" → {to}"
                    if due:
                        line += f" (due {due})"
                    lines.append(line)
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
    queue = generate_queue()
    path = save_queue(queue)
    print(f"\nSaved to {path}")
    print("\n" + queue)
