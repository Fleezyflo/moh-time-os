#!/usr/bin/env python3
"""
LLM-based Commitment Extraction

Uses Claude API to extract promises/requests from communications
when pattern-based detection isn't sufficient.
"""

import hashlib
import json
import logging
import os
import sqlite3

from lib import paths

logger = logging.getLogger(__name__)


try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

DB_PATH = paths.db_path()

EXTRACTION_PROMPT = """Extract any promises or commitments from this email/message.

For each commitment found, identify:
- text: The exact commitment text
- type: "promise" (sender commits to action) or "request" (sender asks recipient for action)
- owner: Who is responsible (if clear)
- target_date: When it's due (ISO format YYYY-MM-DD if mentioned, null otherwise)
- confidence: 0.0-1.0 how clear the commitment is

Return JSON array. If no commitments, return [].

Example output:
[
  {"text": "I'll send the report by Friday", "type": "promise", "owner": "sender", "target_date": "2026-02-07", "confidence": 0.9},
  {"text": "Can you review this by tomorrow?", "type": "request", "owner": "recipient", "target_date": "2026-02-04", "confidence": 0.85}
]

Email content:
---
{content}
---

JSON output (array only, no explanation):"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extract_with_llm(text: str, subject: str = "") -> list[dict]:
    """Extract commitments using Claude API."""
    if not HAS_ANTHROPIC:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    content = f"Subject: {subject}\n\n{text}" if subject else text

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(content=content[:2000]),
                }
            ],
        )

        result_text = response.content[0].text.strip()

        # Parse JSON
        if result_text.startswith("["):
            return json.loads(result_text)

        # Try to find JSON array in response
        import re

        match = re.search(r"\[.*\]", result_text, re.DOTALL)
        if match:
            return json.loads(match.group())

        return []

    except Exception as e:
        logger.info(f"LLM extraction error: {e}")
        return []


def process_unextracted_communications(limit: int = 50) -> dict:
    """
    Process communications that have body_text but no commitments extracted.

    Returns stats on extraction.
    """
    conn = get_conn()

    # Find communications with body text but no commitments
    comms = conn.execute(
        """
        SELECT c.id, c.subject, c.body_text, c.from_email
        FROM communications c
        LEFT JOIN commitments cm ON cm.source_id = c.id AND cm.source_type = 'email'
        WHERE c.body_text IS NOT NULL
          AND LENGTH(c.body_text) >= 50
          AND cm.id IS NULL
        LIMIT ?
    """,
        (limit,),
    ).fetchall()

    stats = {"processed": 0, "commitments_found": 0, "errors": 0}

    for comm in comms:
        try:
            commitments = extract_with_llm(comm["body_text"], comm["subject"])

            for c in commitments:
                hash_input = f"{comm['id']}:{c['text']}"
                commitment_id = (
                    f"llm_{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO commitments
                    (id, source_type, source_id, text, type, owner, target_date, confidence, status, created_at)
                    VALUES (?, 'email', ?, ?, ?, ?, ?, ?, 'open', datetime('now'))
                """,
                    (
                        commitment_id,
                        comm["id"],
                        c.get("text", "")[:500],
                        c.get("type", "unknown"),
                        c.get("owner"),
                        c.get("target_date"),
                        c.get("confidence", 0.5),
                    ),
                )
                stats["commitments_found"] += 1

            stats["processed"] += 1

        except Exception as e:
            stats["errors"] += 1
            logger.info(f"Error processing {comm['id']}: {e}")
    conn.commit()
    conn.close()

    return stats


def run_extraction_batch():
    """Run a batch extraction pass."""
    logger.info("Running LLM commitment extraction...")
    stats = process_unextracted_communications(limit=50)
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Commitments found: {stats['commitments_found']}")
    logger.info(f"Errors: {stats['errors']}")
    return stats


if __name__ == "__main__":
    run_extraction_batch()
