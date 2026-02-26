"""
Inbox Enricher — Populates drill-down context for inbox items.

Adds semantic enrichment to inbox items:
- entities: Extracted people, organizations, projects, dates mentioned
- rationale: Why this item needs attention (AI-generated)
- suggested_actions: Possible actions the user can take
- thread_context: Summary of thread history and status

Runs at ingestion time (when inbox items are created) and stores
the enriched evidence in inbox_items_v29.evidence JSON.
"""

import json
import logging
import os
import re
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

# Check for Anthropic API
try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Enrichment prompt for Claude
ENRICHMENT_PROMPT = """Analyze this email/communication and extract structured context.

Communication:
---
From: {sender}
Subject: {subject}
Body: {body}
---

Extract and return JSON with these fields:

1. "entities": Array of extracted entities with type and value:
   - people: names mentioned
   - organizations: companies/clients mentioned
   - projects: projects/engagements mentioned
   - dates: dates/deadlines mentioned
   Example: [{{"type": "person", "value": "John Smith"}}, {{"type": "date", "value": "next Friday"}}]

2. "rationale": One sentence explaining why this needs attention. Be specific.
   Example: "Client escalation with frustration keywords and pending deadline."

3. "suggested_actions": Array of 1-3 specific actions the user could take.
   Example: ["Reply to acknowledge receipt", "Schedule follow-up call", "Loop in account manager"]

4. "thread_context": One sentence summary of the thread status/history if apparent.
   Example: "Follow-up to previous meeting, awaiting deliverable confirmation."

Return ONLY valid JSON, no explanation:"""


def enrich_with_llm(sender: str, subject: str, body: str) -> dict[str, Any]:
    """
    Enrich communication with LLM-extracted context.

    Returns dict with entities, rationale, suggested_actions, thread_context.
    Returns empty dict if API not available or fails.
    """
    if not HAS_ANTHROPIC:
        logger.debug("Anthropic not available, skipping LLM enrichment")
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set, skipping LLM enrichment")
        return {}

    # Truncate body to avoid token limits
    body_truncated = body[:3000] if body else ""

    prompt = ENRICHMENT_PROMPT.format(
        sender=sender or "Unknown",
        subject=subject or "(No subject)",
        body=body_truncated,
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()

        # Parse JSON response
        if result_text.startswith("{"):
            result = json.loads(result_text)
            if isinstance(result, dict):
                return result

        # Try to extract JSON from response
        match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result

        return {}

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM enrichment response: {e}")
        return {}
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.warning(f"LLM enrichment error: {e}")
        return {}


def enrich_from_heuristics(
    sender: str,
    subject: str,
    body: str,
    priority: int | None,
    requires_response: bool,
) -> dict[str, Any]:
    """
    Fallback enrichment using heuristics when LLM is not available.

    Extracts basic context without AI.
    """
    enrichment: dict[str, Any] = {
        "entities": [],
        "rationale": None,
        "suggested_actions": [],
        "thread_context": None,
    }

    # Extract entities via regex patterns
    entities = []

    # Extract email addresses as people
    email_pattern = r"[\w.-]+@[\w.-]+"
    emails = re.findall(email_pattern, body or "")
    for email in emails[:5]:  # Limit to 5
        entities.append({"type": "person", "value": email})

    # Extract dates
    date_patterns = [
        r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:next|this) (?:week|month|Friday|Monday)\b",
        r"\b(?:tomorrow|today|tonight|asap)\b",
    ]
    combined_text = (subject or "") + " " + (body or "")
    for pattern in date_patterns:
        matches = re.findall(pattern, combined_text, re.IGNORECASE)
        for match in matches[:3]:
            entities.append({"type": "date", "value": match})

    enrichment["entities"] = entities[:10]  # Limit total entities

    # Generate rationale based on priority and flags
    rationale_parts = []
    if priority and priority >= 90:
        rationale_parts.append("High priority email")
    elif priority and priority >= 80:
        rationale_parts.append("Important email")

    if requires_response:
        rationale_parts.append("requires response")

    # Check for urgency keywords
    urgency_keywords = [
        "urgent",
        "asap",
        "immediately",
        "deadline",
        "overdue",
        "critical",
    ]
    lower_subject = (subject or "").lower()
    lower_body = (body or "").lower()
    for keyword in urgency_keywords:
        if keyword in lower_subject or keyword in lower_body:
            rationale_parts.append(f"contains '{keyword}'")
            break

    if rationale_parts:
        enrichment["rationale"] = "; ".join(rationale_parts) + "."
    else:
        enrichment["rationale"] = "Flagged for review based on priority scoring."

    # Generate suggested actions
    actions = []
    if requires_response:
        actions.append("Reply to acknowledge receipt")
    if priority and priority >= 80:
        actions.append("Review and prioritize response")
    if "meeting" in lower_subject or "call" in lower_subject:
        actions.append("Check calendar availability")
    if "invoice" in lower_subject or "payment" in lower_subject:
        actions.append("Review in finance system")
    if not actions:
        actions = ["Review and decide on action", "Mark as read if no action needed"]

    enrichment["suggested_actions"] = actions[:3]

    # Thread context
    if "re:" in lower_subject:
        enrichment["thread_context"] = "Reply in existing conversation thread."
    elif "fwd:" in lower_subject:
        enrichment["thread_context"] = "Forwarded message requiring review."
    else:
        enrichment["thread_context"] = "New conversation."

    return enrichment


def enrich_inbox_item(
    conn: sqlite3.Connection,
    inbox_item_id: str,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Enrich a single inbox item with drill-down context.

    Fetches the underlying communication, generates enrichment,
    and updates the inbox item's evidence JSON.

    Returns the enrichment data that was added.
    """
    from .time_utils import now_iso

    # Get inbox item
    cursor = conn.execute(
        "SELECT * FROM inbox_items_v29 WHERE id = ?",
        (inbox_item_id,),
    )
    item = cursor.fetchone()
    if not item:
        logger.warning(f"Inbox item not found: {inbox_item_id}")
        return {}

    item_dict = dict(item)
    signal_id = item_dict.get("underlying_signal_id")

    # Get communication data
    comm = None
    if signal_id:
        cursor = conn.execute(
            """
            SELECT from_email, subject, snippet, body_text, priority, requires_response,
                   thread_id, source_id, source, created_at
            FROM communications WHERE id = ?
            """,
            (signal_id,),
        )
        comm = cursor.fetchone()

    if not comm:
        logger.debug(f"No communication found for inbox item: {inbox_item_id}")
        return {}

    sender = comm[0]
    subject = comm[1]
    snippet_raw = comm[2]
    body_text = comm[3]
    body = body_text or snippet_raw  # Prefer body_text, fall back to snippet
    priority = comm[4]
    requires_response = bool(comm[5])
    thread_id = comm[6]
    source_id = comm[7]
    source = comm[8]
    received_at = comm[9]

    # Generate enrichment
    if use_llm:
        enrichment = enrich_with_llm(sender, subject, body)
        if not enrichment:
            # Fallback to heuristics if LLM fails
            enrichment = enrich_from_heuristics(sender, subject, body, priority, requires_response)
    else:
        enrichment = enrich_from_heuristics(sender, subject, body, priority, requires_response)

    # Parse existing evidence with strict error handling
    evidence_raw = item_dict.get("evidence")
    meta_trust: dict[str, Any] = {"data_integrity": True, "errors": []}
    try:
        evidence: dict[str, Any] = json.loads(evidence_raw) if evidence_raw else {}
    except json.JSONDecodeError as e:
        logger.error(
            f"JSON parse error for inbox item {inbox_item_id} evidence: raw_length={len(evidence_raw) if evidence_raw else 0}"
        )
        evidence = {}
        meta_trust["data_integrity"] = False
        errors = meta_trust.get("errors")
        if isinstance(errors, list):
            errors.append(f"evidence parse failed: {str(e)[:100]}")
        meta_trust["debug"] = {"evidence_raw_length": len(evidence_raw) if evidence_raw else 0}

    # Merge enrichment into payload
    if "payload" not in evidence:
        evidence["payload"] = {}

    # Derive best snippet for persistence
    derived_snippet = ""
    if body_text and len(body_text.strip()) >= 20:
        import re as re_clean

        clean_body = re_clean.sub(r"<[^>]*>", "", body_text, flags=re_clean.DOTALL)
        clean_body = re_clean.sub(r"\s+", " ", clean_body).strip()
        derived_snippet = clean_body[:500]
    elif snippet_raw and snippet_raw != subject:
        derived_snippet = snippet_raw[:500]
    elif subject:
        derived_snippet = f"Re: {subject}"[:500]

    # Build Gmail URL if source is gmail
    evidence_url = None
    if source == "gmail" and source_id:
        evidence_url = f"https://mail.google.com/mail/u/0/#inbox/{source_id}"

    # Persist core payload fields (safety net if not set at write-time)
    evidence["payload"]["sender"] = evidence["payload"].get("sender") or sender
    evidence["payload"]["subject"] = evidence["payload"].get("subject") or subject
    evidence["payload"]["snippet"] = evidence["payload"].get("snippet") or derived_snippet
    evidence["payload"]["thread_id"] = evidence["payload"].get("thread_id") or thread_id
    evidence["payload"]["received_at"] = evidence["payload"].get("received_at") or received_at
    evidence["payload"]["flagged_reason"] = (
        evidence["payload"].get("flagged_reason") or f"Priority {priority} communication"
    )

    # Set URL at root level
    evidence["url"] = evidence.get("url") or evidence_url

    # Add enrichment fields
    evidence["payload"]["entities"] = enrichment.get("entities", [])
    evidence["payload"]["rationale"] = enrichment.get("rationale")
    evidence["payload"]["suggested_actions"] = enrichment.get("suggested_actions", [])
    evidence["payload"]["thread_context"] = enrichment.get("thread_context")
    evidence["payload"]["enriched_at"] = now_iso()

    # Include meta.trust if there were errors
    if not meta_trust["data_integrity"]:
        evidence["meta"] = evidence.get("meta", {})
        evidence["meta"]["trust"] = meta_trust

    # Update inbox item
    conn.execute(
        """
        UPDATE inbox_items_v29
        SET evidence = ?, updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(evidence), now_iso(), inbox_item_id),
    )

    logger.info(f"Enriched inbox item {inbox_item_id} with drill-down context")
    return enrichment


def enrich_pending_items(
    conn: sqlite3.Connection,
    limit: int = 50,
    use_llm: bool = True,
) -> dict[str, int]:
    """
    Enrich inbox items that haven't been enriched yet.

    Returns stats on enrichment.
    """
    # Find items without enrichment
    cursor = conn.execute(
        """
        SELECT id FROM inbox_items_v29
        WHERE state = 'proposed'
        AND (
            evidence IS NULL
            OR json_extract(evidence, '$.payload.enriched_at') IS NULL
        )
        LIMIT ?
        """,
        (limit,),
    )

    items = cursor.fetchall()
    stats = {"processed": 0, "enriched": 0, "skipped": 0}

    for row in items:
        item_id = row[0]
        try:
            result = enrich_inbox_item(conn, item_id, use_llm=use_llm)
            if result:
                stats["enriched"] += 1
            else:
                stats["skipped"] += 1
            stats["processed"] += 1
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error enriching {item_id}: {e}")
            stats["skipped"] += 1

    return stats


def run_enrichment_batch(use_llm: bool = True, limit: int = 50) -> dict[str, int]:
    """
    Run a batch enrichment pass.

    Called by scheduled job or manually.
    """
    from lib import paths

    conn = sqlite3.connect(str(paths.db_path()))
    conn.row_factory = sqlite3.Row

    try:
        stats = enrich_pending_items(conn, limit=limit, use_llm=use_llm)
        conn.commit()
        logger.info(f"Enrichment batch complete: {stats}")
        return stats
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats = run_enrichment_batch(use_llm=True)
    print(f"Enriched: {stats['enriched']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Total processed: {stats['processed']}")
