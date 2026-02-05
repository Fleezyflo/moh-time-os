#!/usr/bin/env python3
"""Lanes categorization - auto-classify work into lanes."""

import re
from typing import Optional

# Lane definitions based on CONFIG_PROPOSAL.md discovery
LANES = {
    "Finance": {
        "keywords": [
            "invoice", "payment", "ar", "ap", "budget", "cost", "expense",
            "revenue", "billing", "xero", "bank", "transfer", "salary",
            "payroll", "tax", "vat", "receipt", "refund", "credit", "debit",
            "financial", "accounting", "authorize", "authorization"
        ],
        "senders": [
            "xero", "emiratesnbd", "wio", "tabby", "bank", "finance"
        ],
        "priority_weight": 1.0
    },
    "People": {
        "keywords": [
            "hr", "hiring", "interview", "candidate", "onboarding", "leave",
            "vacation", "sick", "benefits", "team", "employee", "staff",
            "performance", "review", "1:1", "all-hands", "weekly", "bayzat",
            "visa", "contract", "probation"
        ],
        "senders": [
            "bayzat", "hr@", "people@", "linkedin"
        ],
        "priority_weight": 0.9
    },
    "Creative": {
        "keywords": [
            "design", "brand", "creative", "content", "video", "photo",
            "shoot", "campaign", "concept", "storyboard", "deck", "pitch",
            "visual", "artwork", "asset", "deliverable", "revision", "feedback"
        ],
        "senders": [
            "creative@", "design@", "wetransfer", "dropbox"
        ],
        "priority_weight": 0.8
    },
    "Sales": {
        "keywords": [
            "proposal", "pitch", "lead", "prospect", "deal", "contract",
            "pricing", "quote", "rfp", "rfq", "tender", "bid", "client",
            "opportunity", "pipeline", "close", "won", "lost", "apollo"
        ],
        "senders": [
            "apollo", "sales@", "bd@"
        ],
        "priority_weight": 0.85
    },
    "Operations": {
        "keywords": [
            "ops", "operation", "process", "workflow", "project", "asana",
            "task", "deadline", "milestone", "delivery", "schedule", "planning",
            "coordination", "status", "update", "wip", "blockers"
        ],
        "senders": [
            "asana", "ops@", "pm@"
        ],
        "priority_weight": 0.75
    },
    "Personal": {
        "keywords": [
            "personal", "family", "home", "doctor", "appointment", "travel",
            "flight", "hotel", "booking", "amazon", "order", "delivery"
        ],
        "senders": [
            "amazon", "noon", "talabat", "careem", "uber"
        ],
        "priority_weight": 0.5
    }
}

# Known clients/projects for auto-tagging
KNOWN_PROJECTS = {
    "GMG": ["gmg", "global media group"],
    "FIVE GUYS": ["five guys", "fiveguys"],
    "SSS": ["sss", "ramadan"],
    "Monoprix": ["monoprix", "mp"],
    "BinSina": ["binsina", "bin sina"],
    "JWMM": ["jwmm", "dining destination"],
    "CS": ["cs", "client services"],
}


def categorize_by_lane(text: str, sender: str = "") -> tuple[str, float]:
    """
    Categorize a piece of work (email subject, task title) into a lane.
    
    Returns: (lane_name, confidence_score)
    """
    text_lower = text.lower()
    sender_lower = sender.lower()
    
    scores = {}
    
    for lane, config in LANES.items():
        score = 0.0
        
        # Check keywords
        for kw in config["keywords"]:
            if kw in text_lower:
                score += 1.0
        
        # Check sender patterns
        for pattern in config["senders"]:
            if pattern in sender_lower:
                score += 2.0  # Sender match is stronger signal
        
        # Apply weight
        score *= config["priority_weight"]
        scores[lane] = score
    
    if not scores or max(scores.values()) == 0:
        return ("Uncategorized", 0.0)
    
    best_lane = max(scores, key=scores.get)
    confidence = min(scores[best_lane] / 5.0, 1.0)  # Normalize to 0-1
    
    return (best_lane, confidence)


def detect_project(text: str) -> Optional[str]:
    """Detect if text mentions a known project."""
    text_lower = text.lower()
    
    for project, patterns in KNOWN_PROJECTS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return project
    
    # Check for bracketed project names [PROJECT]
    brackets = re.findall(r'\[([^\]]+)\]', text)
    for b in brackets:
        b_upper = b.strip().upper()
        if b_upper in KNOWN_PROJECTS:
            return b_upper
    
    return None


def categorize_email(subject: str, sender: str, snippet: str = "") -> dict:
    """Categorize an email into lane and detect project."""
    combined_text = f"{subject} {snippet}"
    lane, confidence = categorize_by_lane(combined_text, sender)
    project = detect_project(combined_text)
    
    return {
        "lane": lane,
        "confidence": round(confidence, 2),
        "project": project,
    }


def categorize_task(title: str, notes: str = "") -> dict:
    """Categorize a task into lane and detect project."""
    combined_text = f"{title} {notes}"
    lane, confidence = categorize_by_lane(combined_text)
    project = detect_project(combined_text)
    
    return {
        "lane": lane,
        "confidence": round(confidence, 2),
        "project": project,
    }


if __name__ == "__main__":
    # Test categorization
    test_cases = [
        ("Invoice for January services", "finance@hrmny.co"),
        ("Interview candidate - Senior Designer", "hr@hrmny.co"),
        ("GMG Campaign Deck v2", "creative@hrmny.co"),
        ("New lead from Apollo", "hello@mail.apollo.io"),
        ("[PEOPLE] hrmny Weekly (All-hands)", "calendar@google.com"),
        ("Shipped: Orijen Kitten Dry Food", "store-news@amazon.ae"),
        ("Re: SSS Ramadan Project", "dana@hrmny.co"),
    ]
    
    print("Lane Categorization Tests:")
    print("-" * 60)
    for subject, sender in test_cases:
        result = categorize_email(subject, sender)
        print(f"Subject: {subject[:40]}")
        print(f"  → Lane: {result['lane']} ({result['confidence']:.0%})")
        if result['project']:
            print(f"  → Project: {result['project']}")
        print()
