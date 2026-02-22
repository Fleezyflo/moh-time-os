"""
Enrollment Detector - Detects potential new retainers/projects from signals.

Signals:
- Task title prefixes (repeated patterns like "ClientName: ...")
- Email thread clusters (repeated sender domains/subjects)
- Calendar meeting series
- Xero invoices (50% deposits indicate new projects)
"""

import logging
import os
from collections import Counter
from datetime import datetime, timedelta

from .state_store import get_store

logger = logging.getLogger(__name__)

_INTERNAL_DOMAINS = set(os.environ.get("MOH_INTERNAL_DOMAINS", "hrmny.co,hrmny.ae").split(","))


# Thresholds from spec
MIN_DISTINCT_TASKS = 3
MIN_DISTINCT_THREADS = 3
TIME_WINDOW_DAYS = 30


def detect_task_prefixes(store, test_mode: bool = False) -> list[dict]:
    """
    Detect repeated task title prefixes that might indicate new clients/retainers.

    Args:
        store: Database store
        test_mode: If True, show ALL patterns including already-enrolled ones
    """

    # Get recent tasks (or all if test mode)
    if test_mode:
        tasks = store.query("""
            SELECT title, project, client_id FROM tasks
            WHERE status = 'pending' AND title LIKE '%:%'
        """)
    else:
        cutoff = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).isoformat()
        tasks = store.query(
            """
            SELECT title, project, client_id FROM tasks
            WHERE created_at >= ? AND status = 'pending'
            AND title LIKE '%:%'
        """,
            [cutoff],
        )

    # Extract prefixes (text before first colon)
    prefix_tasks = {}
    for t in tasks:
        title = t["title"]
        if ":" in title:
            prefix = title.split(":")[0].strip()
            # Skip known system prefixes
            if prefix.startswith("[") or prefix in ("Re", "Fwd", "FW", "Follow up"):
                continue
            if len(prefix) < 3 or len(prefix) > 30:
                continue
            if prefix not in prefix_tasks:
                prefix_tasks[prefix] = []
            prefix_tasks[prefix].append(t)

    # Find prefixes that aren't already enrolled
    enrolled_names = set()
    enrolled = store.query("SELECT name FROM projects WHERE enrollment_status = 'enrolled'")
    for p in enrolled:
        enrolled_names.add(p["name"].lower().strip())
        # Also add the prefix without "Monthly"
        enrolled_names.add(p["name"].replace(" Monthly", "").lower().strip())

    # Also get client names
    clients = store.query("SELECT name FROM clients")
    for c in clients:
        enrolled_names.add(c["name"].lower().strip())

    candidates = []
    for prefix, tasks_list in prefix_tasks.items():
        prefix_lower = prefix.lower().strip()
        is_enrolled = prefix_lower in enrolled_names

        # In test mode, show everything; otherwise skip enrolled
        if not test_mode and is_enrolled:
            continue

        # Check if meets threshold
        if len(tasks_list) >= MIN_DISTINCT_TASKS:
            unlinked = [t for t in tasks_list if not t["project"] or not t["client_id"]]

            # In test mode, always add; otherwise require unlinked
            if test_mode or len(unlinked) >= MIN_DISTINCT_TASKS:
                candidates.append(
                    {
                        "name": prefix,
                        "type": "potential_retainer",
                        "is_enrolled": is_enrolled,
                        "evidence": {
                            "task_count": len(tasks_list),
                            "unlinked_count": len(unlinked),
                            "linked_count": len(tasks_list) - len(unlinked),
                            "sample_titles": [t["title"][:60] for t in tasks_list[:3]],
                        },
                        "confidence": min(0.9, 0.5 + (len(tasks_list) * 0.1)),
                    }
                )

    return candidates


def detect_email_clusters(store) -> list[dict]:
    """Detect email thread clusters that might indicate new projects."""

    cutoff = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).isoformat()
    emails = store.query(
        """
        SELECT subject, from_email, from_domain, thread_id FROM communications
        WHERE created_at >= ?
    """,
        [cutoff],
    )

    # Group by domain
    domain_threads = {}
    for e in emails:
        domain = e.get("from_domain") or ""
        if not domain or domain in ({"gmail.com", "google.com"} | _INTERNAL_DOMAINS):
            continue
        if domain not in domain_threads:
            domain_threads[domain] = set()
        if e.get("thread_id"):
            domain_threads[domain].add(e["thread_id"])

    candidates = []
    for domain, threads in domain_threads.items():
        if len(threads) >= MIN_DISTINCT_THREADS:
            # Extract potential client name from domain
            name = domain.split(".")[0].title()

            candidates.append(
                {
                    "name": name,
                    "type": "potential_project",
                    "evidence": {
                        "domain": domain,
                        "thread_count": len(threads),
                        "source": "email",
                    },
                    "confidence": min(0.8, 0.4 + (len(threads) * 0.1)),
                }
            )

    return candidates


def detect_calendar_series(store) -> list[dict]:
    """Detect recurring meeting series that might indicate new projects."""

    cutoff = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).isoformat()
    events = store.query(
        """
        SELECT title, attendees FROM events
        WHERE start_time >= ?
    """,
        [cutoff],
    )

    # Group by title prefix
    title_counts = Counter()
    for e in events:
        title = e["title"]
        # Look for patterns like "[ClientName] Meeting"
        if title.startswith("[") and "]" in title:
            prefix = title[1 : title.index("]")]
            title_counts[prefix] += 1

    candidates = []
    for prefix, count in title_counts.items():
        if count >= 3:  # At least 3 meetings
            candidates.append(
                {
                    "name": prefix,
                    "type": "potential_project",
                    "evidence": {"meeting_count": count, "source": "calendar"},
                    "confidence": min(0.7, 0.3 + (count * 0.1)),
                }
            )

    return candidates


def detect_xero_deposits(store) -> list[dict]:
    """
    Detect 50% invoice deposits in Xero that might indicate new projects.

    A 50% deposit typically means a new project is starting.
    """
    candidates = []

    try:
        from collectors.xero_ops import get_outstanding_invoices

        invoices = get_outstanding_invoices()

        # Group invoices by contact
        by_contact = {}
        for inv in invoices:
            contact = inv["contact"]
            if contact not in by_contact:
                by_contact[contact] = []
            by_contact[contact].append(inv)

        # Look for patterns indicating new projects:
        # - Invoice description contains "deposit", "50%", "phase 1"
        # - Recent invoice (within 30 days) from a contact
        # - Amount suggests partial payment

        # Get enrolled project names to exclude
        enrolled_names = set()
        enrolled = store.query("SELECT name FROM projects WHERE enrollment_status = 'enrolled'")
        for p in enrolled:
            enrolled_names.add(p["name"].lower().strip())

        for contact, contact_invoices in by_contact.items():
            # Skip if contact looks like an enrolled project/client
            contact_lower = contact.lower()
            if any(
                enrolled in contact_lower or contact_lower in enrolled
                for enrolled in enrolled_names
            ):
                continue

            # Check for recent invoices (might indicate new project)
            recent = [inv for inv in contact_invoices if inv.get("days_overdue", 999) < 30]

            if recent:
                # Check invoice numbers/patterns for "deposit" indicators
                for inv in recent:
                    inv_num = inv.get("number", "").lower()
                    amount = inv.get("amount_due", 0)

                    # Heuristics for deposit detection
                    is_deposit = (
                        "deposit" in inv_num
                        or "50%" in inv_num
                        or "phase 1" in inv_num
                        or "milestone 1" in inv_num
                    )

                    if is_deposit or (amount > 10000 and len(recent) == 1):
                        candidates.append(
                            {
                                "name": contact,
                                "type": "potential_project",
                                "source": "xero_invoice",
                                "evidence": {
                                    "invoice_number": inv.get("number"),
                                    "amount": amount,
                                    "is_deposit_pattern": is_deposit,
                                    "invoice_count": len(contact_invoices),
                                },
                                "confidence": 0.7 if is_deposit else 0.5,
                            }
                        )
                        break  # One candidate per contact

    except Exception as e:
        logger.info(f"Xero deposit detection error: {e}")
    return candidates


def run_detection(store=None, test_mode: bool = False) -> dict:
    """
    Run all detection methods and return candidates.

    Args:
        store: Database store
        test_mode: If True, show ALL patterns including already-enrolled ones
    """
    if store is None:
        store = get_store()

    candidates = []

    # Task prefix detection
    task_candidates = detect_task_prefixes(store, test_mode=test_mode)
    candidates.extend(task_candidates)

    # Email cluster detection
    email_candidates = detect_email_clusters(store)
    candidates.extend(email_candidates)

    # Calendar series detection
    calendar_candidates = detect_calendar_series(store)
    candidates.extend(calendar_candidates)

    # Xero deposit detection (new projects)
    xero_candidates = detect_xero_deposits(store)
    candidates.extend(xero_candidates)

    # Deduplicate by name
    seen = set()
    unique = []
    for c in candidates:
        name_lower = c["name"].lower()
        if name_lower not in seen:
            seen.add(name_lower)
            unique.append(c)

    # Sort by confidence, then by enrolled status (unenrolled first)
    unique.sort(key=lambda x: (x.get("is_enrolled", False), -x["confidence"]))

    return {
        "candidates": unique,
        "total": len(unique),
        "new_candidates": len([c for c in unique if not c.get("is_enrolled")]),
        "enrolled_patterns": len([c for c in unique if c.get("is_enrolled")]),
        "test_mode": test_mode,
        "detected_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import sys

    test_mode = "--test" in sys.argv

    result = run_detection(test_mode=test_mode)
    logger.info(
        f"Found {result['total']} patterns ({result['new_candidates']} new, {result['enrolled_patterns']} enrolled):"
    )
    logger.info(f"Test mode: {result['test_mode']}")
    # (newline for readability)

    for c in result["candidates"]:
        status = "✓ ENROLLED" if c.get("is_enrolled") else "⚡ NEW"
        logger.info(f"  {status} {c['name']} ({c['type']}): {c['confidence']:.0%}")
        logger.info(f"       Evidence: {c['evidence']}")
