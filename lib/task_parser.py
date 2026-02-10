"""
Task Title Parser - Extracts client/project info from task titles.

Handles patterns like:
- "ClientName: Month: Task description"
- "ClientName: Task description"
- "[EMAIL→ACTION] Subject"
- "Brand (Sub-brand): Task"
"""

import logging
import re

from .state_store import get_store

logger = logging.getLogger(__name__)


# Known client aliases and mappings
CLIENT_ALIASES = {
    # GMG brands
    "geant": "GMG Consumer LLC",
    "aswaaq": "GMG Consumer LLC",
    "monoprix": "GMG Consumer LLC",
    "gmg": "GMG Consumer LLC",
    # Gargash brands
    "mercedes-benz": "Gargash Enterprises L.L.C",
    "mercedes": "Gargash Enterprises L.L.C",
    "mb": "Gargash Enterprises L.L.C",
    "mbbc": "Gargash Enterprises L.L.C",
    "daimler": "Gargash Enterprises L.L.C",
    # Pharmacies
    "binsina": "BinSina Pharmacy",
    "supercare": "Supercare Pharmacy",
    # Others
    "sixt": "SIXT",
    "five guys": "Five Guys",
    "ankai": "Ankai",
    "sss": "Sun & Sand Sports",
    "sun sand": "Sun & Sand Sports",
    "sun & sand": "Sun & Sand Sports",
}

# Known retainer mappings (prefix -> project ID)
RETAINER_MAP = {
    "geant": "ret-geant",
    "aswaaq": "ret-aswaaq",
    "monoprix": "ret-monoprix",
    "mercedes-benz": "ret-mb",
    "mbbc": "ret-mbbc",
    "daimler": "ret-mbcv",
    "supercare": "ret-supercare",
    "binsina": "ret-binsina",
    "five guys": "ret-fiveguys",
    "sixt": "ret-sixt",
    "ankai": "ret-ankai",
}

# Patterns to skip (system/internal prefixes)
SKIP_PREFIXES = [
    r"^\[EMAIL→",
    r"^\[APPROVAL",
    r"^Re:",
    r"^Fwd:",
    r"^FW:",
]


def parse_task_title(title: str) -> dict:
    """
    Parse task title to extract client/project info.

    Returns:
        {
            'client_name': str or None,
            'client_id': str or None,
            'project_id': str or None,
            'month': str or None,
            'clean_title': str
        }
    """
    result = {
        "client_name": None,
        "client_id": None,
        "project_id": None,
        "month": None,
        "clean_title": title,
    }

    # Skip system prefixes
    for pattern in SKIP_PREFIXES:
        if re.match(pattern, title, re.IGNORECASE):
            return result

    # Try to parse "Client: Month: Task" or "Client: Task" pattern
    if ":" in title:
        parts = title.split(":")
        prefix = parts[0].strip().lower()

        # Check if prefix is a known client/brand
        if prefix in CLIENT_ALIASES:
            result["client_name"] = CLIENT_ALIASES[prefix]

        if prefix in RETAINER_MAP:
            result["project_id"] = RETAINER_MAP[prefix]

        # Check for month in second part
        if len(parts) >= 2:
            second = parts[1].strip().lower()
            months = [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
                "jan",
                "feb",
                "mar",
                "apr",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
            ]
            for month in months:
                if month in second:
                    result["month"] = second.strip()
                    # Clean title is everything after the month part
                    if len(parts) >= 3:
                        result["clean_title"] = ":".join(parts[2:]).strip()
                    break
            else:
                # No month found, clean title is everything after prefix
                result["clean_title"] = ":".join(parts[1:]).strip()

    return result


def link_task_to_client(task_id: str, store=None) -> str | None:
    """
    Attempt to link a task to a client based on its title.

    Returns client_id if linked, None otherwise.
    """
    if store is None:
        store = get_store()

    task = store.get("tasks", task_id)
    if not task:
        return None

    if task.get("client_id"):
        return task["client_id"]  # Already linked

    parsed = parse_task_title(task["title"])

    if parsed["client_name"]:
        # Find client by name
        clients = store.query(
            "SELECT id FROM clients WHERE name = ? LIMIT 1", [parsed["client_name"]]
        )
        if clients:
            client_id = clients[0]["id"]
            updates = {"client_id": client_id}

            if parsed["project_id"]:
                updates["project"] = parsed["project_id"]

            store.update("tasks", task_id, updates)
            return client_id

    return None


def bulk_link_tasks(store=None) -> dict:
    """
    Bulk link all unlinked tasks to clients.

    Returns summary of linked tasks.
    """
    if store is None:
        store = get_store()

    # Get unlinked tasks
    unlinked = store.query("""
        SELECT id, title FROM tasks
        WHERE client_id IS NULL AND title LIKE '%:%'
    """)

    linked = 0
    by_client = {}

    for task in unlinked:
        parsed = parse_task_title(task["title"])

        if parsed["client_name"]:
            # Find client
            clients = store.query(
                "SELECT id, name FROM clients WHERE name = ? LIMIT 1",
                [parsed["client_name"]],
            )
            if clients:
                client = clients[0]
                updates = {"client_id": client["id"]}

                if parsed["project_id"]:
                    updates["project"] = parsed["project_id"]

                store.update("tasks", task["id"], updates)
                linked += 1

                if client["name"] not in by_client:
                    by_client[client["name"]] = 0
                by_client[client["name"]] += 1

    return {"total_unlinked": len(unlinked), "linked": linked, "by_client": by_client}


if __name__ == "__main__":
    # Test parsing
    test_titles = [
        "Geant: January: Premium Hydration",
        "Aswaaq: Feb: ramadan desserts",
        "BinSina: February Calendar: Ramadan",
        "Mercedes-Benz: March shoot",
        "[EMAIL→REVIEW] SSS Ramadan Campaign",
        "Regular task without client",
    ]

    for title in test_titles:
        result = parse_task_title(title)
        logger.info(f"\n{title}")
        logger.info(
            f"  → Client: {result['client_name']}, Project: {result['project_id']}, Month: {result['month']}"
        )
