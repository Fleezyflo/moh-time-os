"""
Commitment Detector - Pattern-based extraction of promises and requests.

Uses regex patterns and heuristics to identify:
- Promises ("I will", "We'll", "I'm going to")
- Requests ("Can you", "Please", "Would you")
- Deadlines ("by Friday", "before EOD", "next week")
"""

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

logger = logging.getLogger(__name__)


@dataclass
class DetectedCommitment:
    text: str
    type: str  # 'promise' or 'request'
    confidence: float
    deadline: str | None = None
    owner: str | None = None


# Promise patterns (speaker commits to action)
PROMISE_PATTERNS = [
    # Direct promises
    (r"\b(I will|I'll|I'm going to|I am going to)\s+(.+?)(?:\.|$)", 0.9),
    (r"\b(We will|We'll|We're going to|We are going to)\s+(.+?)(?:\.|$)", 0.85),
    (r"\b(I can|I could)\s+(.+?)(?:\.|$)", 0.6),
    # Commitment phrases
    (r"\b(I'll get|I'll send|I'll have|I'll make sure)\s+(.+?)(?:\.|$)", 0.9),
    (r"\b(I'll follow up|I'll check|I'll confirm|I'll update)\s+(.+?)(?:\.|$)", 0.85),
    (r"\b(Let me|Allow me to)\s+(.+?)(?:\.|$)", 0.7),
    # Action commitments
    (r"\b(I'm sending|I'm working on|I'm preparing)\s+(.+?)(?:\.|$)", 0.8),
    (r"\b(Will do|On it|Consider it done)", 0.85),
    # Time-bound promises
    (
        r"(.+?)\s+(by|before|no later than)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|tomorrow|EOD|end of day|end of week|next week)",
        0.9,
    ),
]

# Request patterns (speaker asks for action)
REQUEST_PATTERNS = [
    # Direct requests
    (r"\b(Can you|Could you|Would you|Will you)\s+(.+?)(?:\?|$)", 0.85),
    (r"\b(Please|Pls|Plz)\s+(.+?)(?:\.|$)", 0.8),
    (r"\b(I need you to|I'd like you to)\s+(.+?)(?:\.|$)", 0.9),
    # Question-form requests
    (
        r"\b(Do you think you could|Is it possible to|Would it be possible to)\s+(.+?)(?:\?|$)",
        0.7,
    ),
    (r"\b(When can you|How soon can you)\s+(.+?)(?:\?|$)", 0.75),
    # Indirect requests
    (r"\b(We need|I need|The team needs)\s+(.+?)(?:\.|$)", 0.6),
    (r"\b(It would be great if|It'd be helpful if)\s+(.+?)(?:\.|$)", 0.65),
]

# Deadline extraction patterns
DEADLINE_PATTERNS = [
    # Specific days
    (
        r"\b(by|before|on)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        "day_name",
    ),
    (r"\b(by|before)\s+(tomorrow|tonight|today)\b", "relative"),
    (r"\b(by|before)\s+(EOD|end of day|COB|close of business)\b", "eod"),
    (r"\b(by|before)\s+(end of week|EOW|this week)\b", "eow"),
    (r"\b(by|before)\s+(next week|next Monday)\b", "next_week"),
    # Specific dates
    (r"\b(by|before|on)\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b", "date"),
    (
        r"\b(by|before|on)\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        "month_day",
    ),
    # Relative time
    (r"\b(within|in)\s+(\d+)\s+(hours?|days?|weeks?)\b", "relative_unit"),
    (r"\b(ASAP|as soon as possible|urgent|urgently)\b", "asap"),
]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for cleaner extraction."""
    # Clean text first
    text = re.sub(r"\s+", " ", text)
    # Remove email headers
    text = re.sub(r"^(From|To|Cc|Subject|Date):.*$", "", text, flags=re.MULTILINE)
    # Remove signatures
    text = re.sub(r"--\s*\n.*", "", text, flags=re.DOTALL)

    # Split on sentence-ending punctuation
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Also split on double newlines
    result = []
    for s in sentences:
        parts = re.split(r"\n{2,}", s)
        result.extend(p.strip() for p in parts if p.strip() and len(p.strip()) > 10)

    return result


def detect_promises(text: str) -> list[DetectedCommitment]:
    """
    Detect promises/commitments in text using sentence-based extraction.

    Returns list of detected commitments with confidence scores.
    """
    results = []

    # Split into sentences for cleaner matching
    sentences = _split_sentences(text)

    for sentence in sentences:
        for pattern, confidence in PROMISE_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                # Use the full sentence as context
                full_text = sentence.strip()

                # Skip very short matches
                if len(full_text) < 15:
                    continue

                # Extract deadline if present
                deadline = extract_deadline(full_text)

                results.append(
                    DetectedCommitment(
                        text=full_text,
                        type="promise",
                        confidence=confidence,
                        deadline=deadline,
                    )
                )
                break  # One match per sentence

    # Deduplicate by text similarity
    return _deduplicate(results)


def detect_requests(text: str) -> list[DetectedCommitment]:
    """
    Detect requests in text using sentence-based extraction.

    Returns list of detected requests with confidence scores.
    """
    results = []

    # Split into sentences for cleaner matching
    sentences = _split_sentences(text)

    for sentence in sentences:
        for pattern, confidence in REQUEST_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                # Use the full sentence as context
                full_text = sentence.strip()

                if len(full_text) < 15:
                    continue

                deadline = extract_deadline(full_text)

                results.append(
                    DetectedCommitment(
                        text=full_text,
                        type="request",
                        confidence=confidence,
                        deadline=deadline,
                    )
                )
                break  # One match per sentence

    return _deduplicate(results)


def extract_deadline(text: str) -> str | None:
    """
    Extract deadline from text if present.

    Returns ISO date string or None.
    """
    text.lower()
    today = date.today()

    for pattern, pattern_type in DEADLINE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        try:
            if pattern_type == "day_name":
                day_name = match.group(2).lower()
                target = _next_weekday(today, day_name)
                return target.isoformat()

            if pattern_type == "relative":
                word = match.group(2).lower()
                if word == "today":
                    return today.isoformat()
                if word in ("tomorrow", "tonight"):
                    return (today + timedelta(days=1)).isoformat()

            elif pattern_type == "eod":
                return today.isoformat()

            elif pattern_type == "eow":
                # Find next Friday
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                return (today + timedelta(days=days_until_friday)).isoformat()

            elif pattern_type == "next_week":
                # Next Monday
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                return (today + timedelta(days=days_until_monday)).isoformat()

            elif pattern_type == "relative_unit":
                num = int(match.group(2))
                unit = match.group(3).lower()
                if "hour" in unit:
                    return today.isoformat()  # Same day
                if "day" in unit:
                    return (today + timedelta(days=num)).isoformat()
                if "week" in unit:
                    return (today + timedelta(weeks=num)).isoformat()

            elif pattern_type == "asap":
                return today.isoformat()

        except (sqlite3.Error, ValueError, OSError):
            continue

    return None


def _next_weekday(start_date: date, day_name: str) -> date:
    """Find the next occurrence of a weekday."""
    days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    try:
        target_day = days.index(day_name.lower())
    except ValueError:
        return start_date + timedelta(days=7)

    days_ahead = target_day - start_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7

    return start_date + timedelta(days=days_ahead)


def _deduplicate(items: list[DetectedCommitment]) -> list[DetectedCommitment]:
    """Remove duplicate/overlapping detections using Jaccard similarity."""
    if not items:
        return items

    # Sort by confidence descending
    items.sort(key=lambda x: x.confidence, reverse=True)

    unique = []
    seen_word_sets = []

    for item in items:
        # Normalize text and get word set
        normalized = item.text.lower().strip()
        words = set(re.findall(r"\b\w+\b", normalized))

        # Check similarity with already seen items
        is_duplicate = False
        for seen_words in seen_word_sets:
            # Jaccard similarity
            intersection = len(words & seen_words)
            union = len(words | seen_words)
            similarity = intersection / union if union > 0 else 0

            if similarity > 0.7:  # 70% word overlap = duplicate
                is_duplicate = True
                break

        if not is_duplicate:
            unique.append(item)
            seen_word_sets.append(words)

    return unique


def extract_all(text: str) -> dict:
    """
    Extract all commitments (promises + requests) from text.

    Returns structured dict with all detections.
    """
    promises = detect_promises(text)
    requests = detect_requests(text)

    return {
        "promises": [
            {"text": p.text, "confidence": p.confidence, "deadline": p.deadline} for p in promises
        ],
        "requests": [
            {"text": r.text, "confidence": r.confidence, "deadline": r.deadline} for r in requests
        ],
        "total": len(promises) + len(requests),
    }


# Test
if __name__ == "__main__":
    test_emails = [
        "I'll send you the report by Friday.",
        "Can you please review this by tomorrow?",
        "We're going to have the mockups ready by end of week.",
        "I'll follow up with the client on Monday.",
        "Please let me know your availability for next week.",
        "I need you to complete the task before EOD.",
        "Will do! I'll get that to you ASAP.",
    ]

    logger.info("Testing commitment detection:")
    logger.info("-" * 50)
    for email in test_emails:
        logger.info(f"\nInput: {email}")
        result = extract_all(email)
        if result["promises"]:
            for p in result["promises"]:
                logger.info(
                    f"  → Promise: {p['text']} (conf: {p['confidence']}, deadline: {p['deadline']})"
                )
        if result["requests"]:
            for r in result["requests"]:
                logger.info(
                    f"  → Request: {r['text']} (conf: {r['confidence']}, deadline: {r['deadline']})"
                )
