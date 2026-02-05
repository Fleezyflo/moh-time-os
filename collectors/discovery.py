#!/usr/bin/env python3
"""Discovery engine - analyze 14 days of data to learn patterns."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

OUT_DIR = Path(__file__).parent.parent / "out"


def collect_emails_14d() -> list:
    """Fetch emails from last 14 days."""
    cmd = ["gog", "gmail", "search", "newer_than:14d", "--max", "200", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return []
    return json.loads(result.stdout).get("threads", [])


def collect_calendar_14d() -> list:
    """Fetch calendar events from last 14 days."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=14)
    
    cmd = [
        "gog", "calendar", "events", "primary",
        "--from", start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return []
    return json.loads(result.stdout).get("events", [])


def analyze_email_senders(emails: list) -> dict:
    """Analyze email volume by sender domain."""
    by_domain = defaultdict(int)
    by_sender = defaultdict(int)
    
    for e in emails:
        sender = e.get("from", "")
        if "<" in sender:
            email_part = sender.split("<")[1].split(">")[0]
        else:
            email_part = sender
        
        domain = email_part.split("@")[-1] if "@" in email_part else "unknown"
        by_domain[domain] += 1
        by_sender[sender] += 1
    
    return {
        "by_domain": dict(sorted(by_domain.items(), key=lambda x: -x[1])[:20]),
        "by_sender": dict(sorted(by_sender.items(), key=lambda x: -x[1])[:20]),
        "total": len(emails)
    }


def analyze_calendar_patterns(events: list) -> dict:
    """Analyze meeting patterns."""
    by_day = defaultdict(int)
    by_hour = defaultdict(int)
    recurring = 0
    total_duration_min = 0
    
    for e in events:
        start = e.get("start", {}).get("dateTime", "")
        if not start:
            continue
        
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            by_day[dt.strftime("%A")] += 1
            by_hour[dt.hour] += 1
        except:
            pass
        
        if e.get("recurringEventId"):
            recurring += 1
    
    return {
        "by_day": dict(by_day),
        "by_hour": dict(sorted(by_hour.items())),
        "recurring_count": recurring,
        "total": len(events)
    }


def infer_lanes(emails: list, events: list) -> list:
    """Infer work lanes from email subjects and meeting titles."""
    lane_keywords = {
        "Finance": ["invoice", "payment", "ar", "finance", "budget", "cost"],
        "Creative": ["creative", "design", "brand", "content", "campaign", "shoot"],
        "Operations": ["ops", "operation", "process", "workflow", "project"],
        "Sales": ["proposal", "pitch", "client", "lead", "deal"],
        "People": ["team", "hr", "hiring", "onboard", "people", "weekly"],
        "Personal": ["moh flow", "music", "artist", "spotify"],
    }
    
    lane_counts = defaultdict(int)
    
    for e in emails:
        subj = e.get("subject", "").lower()
        for lane, keywords in lane_keywords.items():
            if any(k in subj for k in keywords):
                lane_counts[lane] += 1
    
    for e in events:
        title = e.get("summary", "").lower()
        for lane, keywords in lane_keywords.items():
            if any(k in title for k in keywords):
                lane_counts[lane] += 1
    
    return dict(sorted(lane_counts.items(), key=lambda x: -x[1]))


def infer_priority_tiers(emails: list) -> dict:
    """Infer priority tiers from sender patterns."""
    # High priority: internal team, known VIPs, finance/legal
    high_keywords = ["@hrmny.co", "finance", "legal", "urgent", "asap"]
    medium_keywords = ["client", "proposal", "meeting", "deadline"]
    
    high = []
    medium = []
    low = []
    
    for e in emails:
        sender = e.get("from", "").lower()
        subj = e.get("subject", "").lower()
        combined = sender + " " + subj
        
        if any(k in combined for k in high_keywords):
            high.append(sender)
        elif any(k in combined for k in medium_keywords):
            medium.append(sender)
        else:
            low.append(sender)
    
    return {
        "high": len(high),
        "medium": len(medium),
        "low": len(low),
        "high_senders": list(set(high))[:10],
    }


def analyze_scheduling_windows(events: list) -> dict:
    """Analyze when meetings typically happen."""
    hour_counts = defaultdict(int)
    
    for e in events:
        start = e.get("start", {}).get("dateTime", "")
        if not start:
            continue
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            hour_counts[dt.hour] += 1
        except:
            pass
    
    # Find gaps (potential deep work windows)
    meeting_hours = set(hour_counts.keys())
    all_work_hours = set(range(9, 19))  # 9am-7pm
    free_hours = all_work_hours - meeting_hours
    
    return {
        "meeting_hours": dict(sorted(hour_counts.items())),
        "potential_deep_work": sorted(list(free_hours)),
    }


def detect_project_enrollment(emails: list, events: list) -> list:
    """Detect potential projects from recurring patterns."""
    # Look for repeated keywords suggesting projects
    subject_words = defaultdict(int)
    
    for e in emails:
        subj = e.get("subject", "").lower()
        # Extract potential project names (capitalized words, brackets)
        import re
        # Match [Project Name] or common project indicators
        brackets = re.findall(r'\[([^\]]+)\]', subj)
        for b in brackets:
            subject_words[b.strip()] += 1
        
        # Match client names we know
        known_clients = ["gmg", "sss", "asics", "gargash", "monoprix", "five guys", "sephora"]
        for client in known_clients:
            if client in subj:
                subject_words[client.upper()] += 1
    
    for e in events:
        title = e.get("summary", "").lower()
        brackets = re.findall(r'\[([^\]]+)\]', title)
        for b in brackets:
            subject_words[b.strip()] += 1
    
    # Filter to items with 2+ occurrences
    projects = [(k, v) for k, v in subject_words.items() if v >= 2]
    projects.sort(key=lambda x: -x[1])
    
    return [{"name": p[0], "signals": p[1]} for p in projects[:15]]


def run_discovery() -> dict:
    """Run full discovery analysis."""
    print("Collecting 14 days of emails...")
    emails = collect_emails_14d()
    
    print("Collecting 14 days of calendar...")
    events = collect_calendar_14d()
    
    print("Analyzing patterns...")
    email_analysis = analyze_email_senders(emails)
    calendar_analysis = analyze_calendar_patterns(events)
    lanes = infer_lanes(emails, events)
    priority_tiers = infer_priority_tiers(emails)
    scheduling = analyze_scheduling_windows(events)
    projects = detect_project_enrollment(emails, events)
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": 14,
        "email": email_analysis,
        "calendar": calendar_analysis,
        "inferred_lanes": lanes,
        "priority_tiers": priority_tiers,
        "scheduling": scheduling,
        "detected_projects": projects,
    }


def save_report(data: dict):
    """Save discovery report."""
    OUT_DIR.mkdir(exist_ok=True)
    
    # Save JSON
    json_path = OUT_DIR / "discovery.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    
    # Generate markdown report
    md_lines = [
        "# Discovery Report",
        f"Generated: {data['generated_at']}",
        f"Period: Last {data['period_days']} days",
        "",
        "## Email Analysis",
        f"Total threads: {data['email']['total']}",
        "",
        "### Top Domains",
    ]
    
    for domain, count in list(data['email']['by_domain'].items())[:10]:
        md_lines.append(f"- {domain}: {count}")
    
    md_lines.extend([
        "",
        "## Calendar Analysis",
        f"Total events: {data['calendar']['total']}",
        f"Recurring: {data['calendar']['recurring_count']}",
        "",
        "### By Day",
    ])
    
    for day, count in data['calendar']['by_day'].items():
        md_lines.append(f"- {day}: {count}")
    
    md_lines.extend([
        "",
        "## Inferred Lanes",
    ])
    
    for lane, count in data['inferred_lanes'].items():
        md_lines.append(f"- {lane}: {count} signals")
    
    md_lines.extend([
        "",
        "## Priority Tiers",
        f"- High priority: {data['priority_tiers']['high']} emails",
        f"- Medium priority: {data['priority_tiers']['medium']} emails", 
        f"- Low priority: {data['priority_tiers']['low']} emails",
        "",
        "### High Priority Senders",
    ])
    
    for sender in data['priority_tiers']['high_senders'][:5]:
        md_lines.append(f"- {sender}")
    
    md_lines.extend([
        "",
        "## Scheduling Analysis",
        "",
        "### Meeting Hours",
    ])
    
    for hour, count in data['scheduling']['meeting_hours'].items():
        md_lines.append(f"- {hour}:00: {count} meetings")
    
    md_lines.extend([
        "",
        "### Deep Work Windows",
        "Hours with no meetings (potential focus time):",
    ])
    
    for hour in data['scheduling']['potential_deep_work']:
        md_lines.append(f"- {hour}:00")
    
    md_lines.extend([
        "",
        "## Detected Projects",
        "Recurring patterns suggesting active projects:",
    ])
    
    for proj in data.get('detected_projects', [])[:10]:
        md_lines.append(f"- {proj['name']}: {proj['signals']} signals")
    
    md_path = OUT_DIR / "DISCOVERY_REPORT.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    
    return json_path, md_path


if __name__ == "__main__":
    data = run_discovery()
    json_path, md_path = save_report(data)
    print(f"\nSaved to {json_path} and {md_path}")
