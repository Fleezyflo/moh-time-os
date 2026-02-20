"""
Commitment Extractor

Extracts commitments (promises, requests) from communications.
Creates commitment records linked to client + communication.
"""

import hashlib
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()

# Commitment signal phrases
COMMITMENT_PATTERNS = [
    # Promises
    (
        r"\b(i'll|i will|will)\s+(send|share|get|follow up|reach out|check|confirm|update|prepare|draft|review|deliver|complete|finish)",
        "promise",
    ),
    (
        r"\b(let me|gonna|going to)\s+(send|share|get|follow up|reach out|check|confirm|update|prepare|draft|review)",
        "promise",
    ),
    (r"\b(will get back|get back to you|follow up with you)", "promise"),
    (r"\bpromise to\b", "promise"),
    (r"\bcommit to\b", "promise"),
    (r"\bwill make sure\b", "promise"),
    (r"\bwill ensure\b", "promise"),
    # Requests
    (
        r"\b(can you|could you|would you|please)\s+(send|share|provide|confirm|update|review|check)",
        "request",
    ),
    (r"\b(need you to|asking you to|requesting)\b", "request"),
    (r"\bwaiting for\b", "request"),
    (r"\bexpecting\b.*\bfrom you\b", "request"),
]

# Time extraction patterns
TIME_PATTERNS = {
    "today": 0,
    "tomorrow": 1,
    "by eod": 0,
    "end of day": 0,
    "by eow": None,  # Friday
    "end of week": None,
    "by friday": None,
    "by monday": None,
    "by tuesday": None,
    "by wednesday": None,
    "by thursday": None,
    "next week": 7,
    "this week": None,
    "asap": 1,
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extract_deadline(text: str) -> str:
    """Extract deadline from text. Returns ISO date or None."""
    text_lower = text.lower()
    today = date.today()

    for pattern, days in TIME_PATTERNS.items():
        if pattern in text_lower:
            if days is not None:
                deadline = today + timedelta(days=days)
                return deadline.isoformat()
            if "friday" in pattern:
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                deadline = today + timedelta(days=days_until_friday)
                return deadline.isoformat()
            if "monday" in pattern:
                days_until = (0 - today.weekday()) % 7
                if days_until == 0:
                    days_until = 7
                deadline = today + timedelta(days=days_until)
                return deadline.isoformat()
            if "end of week" in pattern or "eow" in pattern or "this week" in pattern:
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                deadline = today + timedelta(days=days_until_friday)
                return deadline.isoformat()

    return None


def extract_commitments_from_text(text: str) -> list:
    """Extract commitment phrases from text."""
    if not text:
        return []

    commitments = []

    for pattern, commit_type in COMMITMENT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Get surrounding context (up to 100 chars)
            match_str = " ".join(match) if isinstance(match, tuple) else match

            # Find match position and extract context
            match_pos = text.lower().find(match_str.lower())
            if match_pos >= 0:
                start = max(0, match_pos - 20)
                end = min(len(text), match_pos + len(match_str) + 80)
                context = text[start:end].strip()

                # Clean up context
                context = re.sub(r"\s+", " ", context)
                context = context[:100]

                commitments.append(
                    {
                        "type": commit_type,
                        "text": context,
                        "deadline": extract_deadline(text),
                    }
                )

    return commitments


def generate_commitment_id(source_id: str, text: str) -> str:
    """Generate deterministic ID for deduplication."""
    content = f"{source_id}:{text[:50]}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def extract_from_communications(limit: int = 100) -> dict:
    """Extract commitments from unprocessed communications with body_text."""
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Get communications with body_text that haven't been fully processed
    cursor.execute(
        """
        SELECT id, client_id, body_text, from_email, subject, received_at
        FROM communications
        WHERE body_text IS NOT NULL
        AND body_text != ''
        AND LENGTH(body_text) > 50
        ORDER BY received_at DESC
        LIMIT ?
    """,
        (limit,),
    )

    comms = cursor.fetchall()

    extracted = 0
    skipped = 0

    for comm in comms:
        body = comm["body_text"]
        source_id = comm["id"]
        client_id = comm["client_id"]

        commitments = extract_commitments_from_text(body)

        for c in commitments:
            # Generate deterministic ID
            commit_id = generate_commitment_id(source_id, c["text"])

            # Check if already exists
            cursor.execute("SELECT id FROM commitments WHERE id = ?", (commit_id,))
            if cursor.fetchone():
                skipped += 1
                continue

            # Determine speaker (from_email → hrmny = us, else = client)
            from_email = comm["from_email"] or ""
            if "hrmny" in from_email.lower():
                speaker = "hrmny"
                target = "client"
            else:
                speaker = "client"
                target = "hrmny"

            # Insert commitment
            cursor.execute(
                """
                INSERT INTO commitments (
                    id, source_type, source_id, text, type, confidence,
                    deadline, speaker, target, client_id, status, created_at
                ) VALUES (?, 'communication', ?, ?, ?, 0.7, ?, ?, ?, ?, 'open', ?)
            """,
                (
                    commit_id,
                    source_id,
                    c["text"],
                    c["type"],
                    c["deadline"],
                    speaker,
                    target,
                    client_id,
                    now,
                ),
            )
            extracted += 1

    conn.commit()
    conn.close()

    return {
        "communications_scanned": len(comms),
        "commitments_extracted": extracted,
        "skipped_duplicates": skipped,
    }


def run():
    """Run commitment extraction."""
    conn = get_conn()
    cursor = conn.cursor()

    # Count before
    cursor.execute("SELECT COUNT(*) as cnt FROM commitments")
    before = cursor.fetchone()["cnt"]

    logger.info("Extracting commitments from communications...")
    result = extract_from_communications(limit=500)

    # Count after
    cursor.execute("SELECT COUNT(*) as cnt FROM commitments")
    after = cursor.fetchone()["cnt"]

    logger.info(f"\nCommitments: {before} → {after} (+{result['commitments_extracted']})")
    logger.info(f"Communications scanned: {result['communications_scanned']}")
    logger.info(f"Skipped duplicates: {result['skipped_duplicates']}")
    # Show recent commitments
    cursor.execute("""
        SELECT cm.text, cm.type, cm.deadline, cm.speaker, c.name as client
        FROM commitments cm
        LEFT JOIN clients c ON cm.client_id = c.id
        ORDER BY cm.created_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    logger.info(f"\nRecent commitments ({len(rows)}):")
    for r in rows:
        client = r["client"] or "Unknown"
        deadline = r["deadline"] or "No deadline"
        logger.info(f"  [{r['type']}] {r['text'][:60]}...")
        logger.info(
            f"       Speaker: {r['speaker']} | Client: {client[:20]} | Deadline: {deadline}"
        )
    conn.close()
    return result


if __name__ == "__main__":
    run()
