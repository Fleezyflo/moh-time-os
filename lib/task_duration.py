"""
Smart task duration estimation based on title patterns.

Infers duration from task title when no explicit estimate exists.
"""

import re
from typing import Optional

# Duration patterns (minutes)
DURATION_PATTERNS = [
    # Quick tasks (15 min)
    (15, [
        r'\b(approve|sign.?off|confirm|acknowledge)\b',
        r'\b(send|forward|share|post)\b',
        r'\b(reply|respond|follow.?up)\b',
        r'\b(check|verify|validate)\b',
        r'\b(remind|ping|nudge)\b',
        r'\binvoice\b',  # Invoice processing
        r'\bretouch\b',  # Quick edits
        r'\bSOA\b',  # Statement of account
    ]),
    
    # Short tasks (30 min)
    (30, [
        r'\b(review|read|look.?at)\b',
        r'\b(update|edit|revise|tweak)\b',
        r'\b(schedule|book|arrange)\b',
        r'\b(upload|download|export|import)\b',
        r'\b(call|sync|catch.?up)\b',
        r'\b(feedback|comment|note)\b',
        r'\bretainer\b',  # Retainer admin
        r'\bRFP\b',  # RFP response (initial)
        r'\bphotoshoot\b',  # Coordination (not production)
    ]),
    
    # Medium tasks (60 min / 1h)
    (60, [
        r'\b(write|draft|compose)\b',
        r'\b(prepare|setup|configure)\b',
        r'\b(meet|meeting|discussion)\b',
        r'\b(analyze|assess|evaluate)\b',
        r'\b(fix|resolve|debug|troubleshoot)\b',
        r'\b(organize|sort|clean.?up)\b',
    ]),
    
    # Long tasks (90 min)
    (90, [
        r'\b(create|build|develop|design)\b',
        r'\b(plan|strategy|roadmap)\b',
        r'\b(research|investigate|explore)\b',
        r'\b(document|report|presentation)\b',
        r'\b(train|onboard|teach)\b',
    ]),
    
    # Extended tasks (120 min / 2h)
    (120, [
        r'\b(produce|shoot|film|record)\b',
        r'\b(implement|integrate|migrate)\b',
        r'\b(audit|deep.?dive|comprehensive)\b',
        r'\b(workshop|session|training)\b',
    ]),
    
    # Major tasks (180 min / 3h)
    (180, [
        r'\b(campaign|launch|release)\b',
        r'\b(overhaul|redesign|rebuild)\b',
        r'\b(full|complete|entire)\b',
    ]),
]

# Lane-based defaults (when no pattern matches)
# Most tasks without clear verbs are quick admin/follow-up work
LANE_DEFAULTS = {
    'ops': 20,
    'admin': 15,
    'finance': 20,
    'client': 30,
    'creative': 45,
    'production': 60,
    'growth': 30,
    'people': 20,
    'music': 45,
    'personal': 15,
}

DEFAULT_DURATION = 20  # Global fallback - assume quick task


def estimate_duration(title: str, lane: str = None) -> int:
    """
    Estimate task duration in minutes based on title patterns.
    
    Args:
        title: Task title to analyze
        lane: Optional lane for fallback defaults
        
    Returns:
        Estimated duration in minutes
    """
    if not title:
        return LANE_DEFAULTS.get(lane, DEFAULT_DURATION) if lane else DEFAULT_DURATION
    
    title_lower = title.lower()
    
    # Check each pattern group (ordered by duration)
    for duration, patterns in DURATION_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, title_lower):
                return duration
    
    # Fallback to lane default or global default
    if lane:
        return LANE_DEFAULTS.get(lane.lower(), DEFAULT_DURATION)
    
    return DEFAULT_DURATION


def estimate_duration_batch(tasks: list) -> list:
    """
    Estimate durations for a batch of tasks.
    
    Args:
        tasks: List of dicts with 'title' and optionally 'lane'
        
    Returns:
        Same list with 'estimated_duration_min' added
    """
    for task in tasks:
        title = task.get('title', '')
        lane = task.get('lane') or task.get('resolved_lane')
        task['estimated_duration_min'] = estimate_duration(title, lane)
    
    return tasks


if __name__ == "__main__":
    # Test cases
    test_tasks = [
        "Review contract draft",
        "Send invoice to client",
        "Create social media campaign",
        "Approve design mockup",
        "Prepare quarterly report",
        "Fix bug in dashboard",
        "Produce video content",
        "Quick sync with team",
        "Full website redesign",
        "Update spreadsheet",
    ]
    
    print("Duration estimates:")
    for title in test_tasks:
        mins = estimate_duration(title)
        print(f"  {title:40} → {mins:3} min ({mins/60:.1f}h)")
