"""Sync data from Xero and Asana into MOH Time OS v2."""

import logging
import os
from typing import Any

from .entities import (
    find_client,
    list_clients,
    upsert_client,
    upsert_person,
    upsert_project,
)
from .store import now_iso

logger = logging.getLogger(__name__)


def infer_tier(ar_outstanding: float, annual_value: float = 0) -> str:
    """
    Infer client tier from AR outstanding and annual value.
    A: >200K outstanding or >500K annual
    B: >50K outstanding or >100K annual
    C: everything else
    """
    if ar_outstanding >= 200_000 or annual_value >= 500_000:
        return "A"
    if ar_outstanding >= 50_000 or annual_value >= 100_000:
        return "B"
    return "C"


def infer_ar_aging(days_overdue: int) -> str:
    """Infer AR aging category from days overdue."""
    if days_overdue <= 0:
        return "Current"
    if days_overdue <= 30:
        return "30 days"
    if days_overdue <= 60:
        return "60 days"
    return "60+ days"


def infer_health(ar_aging: str, payment_pattern: str = "Unknown") -> str:
    """Infer relationship health from AR aging and payment pattern."""
    if ar_aging == "Current":
        return "good"
    if ar_aging == "30 days":
        return "fair"
    if ar_aging == "60 days":
        return "poor"
    return "critical"


def sync_xero_clients_from_cache() -> dict[str, Any]:
    """
    Sync clients from cached Xero data.
    Returns summary of sync operation.
    """
    import json

    cache_path = os.path.join(os.path.dirname(__file__), "..", "config", "xero_contacts.json")

    result = {
        "synced": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    try:
        with open(cache_path) as f:
            data = json.load(f)

        customers = data.get("customers", [])

        for contact in customers:
            try:
                name = contact.get("name", "Unknown")

                # Skip if no name or internal
                if not name or name == "Unknown":
                    continue
                if "@hrmny.co" in name.lower():
                    continue  # Skip internal contacts

                # Infer tier from name (will be updated with AR later)
                tier = "C"  # Default

                # Check if exists
                existing = find_client(name=name)

                # Upsert client
                upsert_client(
                    name=name,
                    tier=tier,
                    health="good",
                    type="agency_client",
                )

                result["synced"] += 1
                if existing:
                    result["updated"] += 1
                else:
                    result["created"] += 1

            except (KeyError, TypeError) as e:
                # Data format issue with this contact - skip and continue
                error_msg = f"{contact.get('name', 'Unknown')}: {e}"
                logger.debug(f"Skipping contact due to data issue: {error_msg}")
                result["errors"].append(error_msg)
            except Exception as e:
                # Unexpected error - log with stack trace but continue batch
                error_msg = f"{contact.get('name', 'Unknown')}: {e}"
                logger.warning(f"Failed to sync contact: {error_msg}", exc_info=True)
                result["errors"].append(error_msg)

    except FileNotFoundError:
        error_msg = f"Xero cache file not found: {cache_path}"
        logger.warning(error_msg)
        result["errors"].append(error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Xero cache file corrupt: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Xero cache sync failed: {e}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)

    return result


def sync_xero_clients() -> dict[str, Any]:
    """
    Sync clients from Xero API (with fallback to cache).
    Returns summary of sync operation.
    """
    try:
        from engine.xero_client import list_contacts

        contacts = list_contacts(is_customer=True)
    except ImportError as e:
        # Xero client not available - use cache
        logger.info(f"Xero client not available, using cached data: {e}")
        return sync_xero_clients_from_cache()
    except Exception as e:
        # API failed - fallback to cached data
        logger.warning(f"Xero API failed, falling back to cached data: {e}")
        return sync_xero_clients_from_cache()

    result = {
        "synced": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    for contact in contacts:
        try:
            xero_id = contact.get("ContactID", "")
            name = contact.get("Name", "Unknown")

            # Skip if no name or internal
            if not name or name == "Unknown":
                continue
            if "@hrmny.co" in name.lower():
                continue

            # Infer tier (default C, will update with AR later)
            tier = "C"

            # Get contact info
            if "EmailAddress" in contact:
                contact["EmailAddress"]

            # Check if exists
            existing = find_client(xero_id=xero_id)

            # Upsert client
            upsert_client(
                name=name,
                tier=tier,
                xero_contact_id=xero_id,
                health="good",
                type="agency_client",
            )

            result["synced"] += 1
            if existing:
                result["updated"] += 1
            else:
                result["created"] += 1

        except (KeyError, TypeError) as e:
            # Data format issue with this contact - skip and continue
            error_msg = f"{contact.get('Name', 'Unknown')}: {e}"
            logger.debug(f"Skipping contact due to data issue: {error_msg}")
            result["errors"].append(error_msg)
        except Exception as e:
            # Unexpected error - log with stack trace but continue batch
            error_msg = f"{contact.get('Name', 'Unknown')}: {e}"
            logger.warning(f"Failed to sync contact from API: {error_msg}", exc_info=True)
            result["errors"].append(error_msg)

    return result


def sync_asana_projects(workspace_name: str = "hrmny.co") -> dict[str, Any]:
    """
    Sync projects from Asana.
    Returns summary of sync operation.
    """
    from engine.asana_client import list_projects, list_workspaces

    result = {
        "synced": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
        "unlinked": 0,  # Projects without a matching client
    }

    try:
        # Find workspace
        workspaces = list_workspaces()
        workspace = None
        for ws in workspaces:
            if workspace_name.lower() in ws.get("name", "").lower():
                workspace = ws
                break

        if not workspace:
            result["errors"].append(f"Workspace '{workspace_name}' not found")
            return result

        # Get all projects with status fields
        projects = list_projects(
            workspace["gid"],
            opt_fields="name,archived,completed,due_on,start_on,current_status",
        )

        # Get all clients for matching
        clients = list_clients()
        client_name_map = {}
        client_words_map = {}  # map significant words to client ids

        for c in clients:
            name_lower = c.name.lower()
            # Store full name
            client_name_map[name_lower] = c.id

            # Store significant words (>3 chars, not common words)
            skip_words = {
                "llc",
                "fze",
                "l.l.c",
                "l.l.c.",
                "fzco",
                "and",
                "the",
                "for",
                "with",
            }
            words = [
                w.strip(".,()") for w in name_lower.split() if len(w) > 3 and w not in skip_words
            ]
            for word in words:
                if word not in client_words_map:
                    client_words_map[word] = []
                client_words_map[word].append((c.id, c.name))

        for proj in projects:
            try:
                asana_id = proj.get("gid", "")
                name = proj.get("name", "Unknown")

                # Skip templates and internal
                if any(skip in name.lower() for skip in ["template", "internal", "test"]):
                    continue

                # Try to match to a client
                client_id = None
                name_lower = name.lower()

                # First try full name match
                for client_name, cid in client_name_map.items():
                    if client_name in name_lower:
                        client_id = cid
                        break

                # Then try word matching
                if not client_id:
                    proj_words = [w.strip(".,()") for w in name_lower.split() if len(w) > 3]
                    best_match = None
                    best_score = 0

                    for word in proj_words:
                        if word in client_words_map:
                            for cid, _cname in client_words_map[word]:
                                # Score by how unique the word is
                                score = 1.0 / len(client_words_map[word])
                                if score > best_score:
                                    best_score = score
                                    best_match = cid

                    # Only accept if reasonable confidence
                    if best_score >= 0.3:
                        client_id = best_match

                if not client_id:
                    result["unlinked"] += 1
                    # Still create project without client link

                # Infer status/health from Asana project fields
                archived = proj.get("archived", False)
                completed = proj.get("completed", False)
                due_on = proj.get("due_on")
                current_status = proj.get("current_status")

                if completed:
                    status = "completed"
                    health = "on_track"
                elif archived:
                    status = "archived"
                    health = "on_track"
                else:
                    status = "active"
                    # Check if overdue
                    if due_on:
                        from datetime import date

                        try:
                            due_date = date.fromisoformat(due_on)
                            health = "late" if due_date < date.today() else "on_track"
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Could not parse due_on '{due_on}': {e}")
                            health = "on_track"
                    else:
                        health = "on_track"

                    # Use current_status if available
                    if current_status:
                        status_color = current_status.get("color", "")
                        if status_color == "red" or status_color == "yellow":
                            health = "at_risk"
                        elif status_color == "green":
                            health = "on_track"

                # Upsert project
                upsert_project(
                    name=name,
                    client_id=client_id,
                    asana_project_id=asana_id,
                    status=status,
                    health=health,
                )

                result["synced"] += 1
                result["created"] += 1  # Simplified - always counts as created

            except (KeyError, TypeError) as e:
                # Data format issue with this project - skip and continue
                error_msg = f"{proj.get('name', 'Unknown')}: {e}"
                logger.debug(f"Skipping project due to data issue: {error_msg}")
                result["errors"].append(error_msg)
            except Exception as e:
                # Unexpected error - log with stack trace but continue batch
                error_msg = f"{proj.get('name', 'Unknown')}: {e}"
                logger.warning(f"Failed to sync project: {error_msg}", exc_info=True)
                result["errors"].append(error_msg)

    except ImportError as e:
        error_msg = f"Asana client not available: {e}"
        logger.warning(error_msg)
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Asana sync failed: {e}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)

    return result


def sync_team_from_kb() -> dict[str, Any]:
    """
    Sync team members from knowledge base.
    Returns summary of sync operation.
    """
    import json

    kb_path = os.path.join(os.path.dirname(__file__), "..", "config", "knowledge_base.json")

    result = {
        "synced": 0,
        "active": 0,
        "inactive": 0,
        "errors": [],
    }

    try:
        with open(kb_path) as f:
            kb = json.load(f)

        team = kb.get("team", [])

        for member in team:
            try:
                name = member.get("name", "")
                if not name:
                    continue

                email = member.get("email", "")
                role = member.get("title", "")
                department = member.get("department", "")
                active = member.get("active", False)

                upsert_person(
                    name=name,
                    email=email,
                    type="internal",
                    company="hrmny",
                    role=role,
                    department=department,
                    relationship_notes=f"{'Active' if active else 'Inactive'} team member",
                )

                result["synced"] += 1
                if active:
                    result["active"] += 1
                else:
                    result["inactive"] += 1

            except (KeyError, TypeError) as e:
                error_msg = f"{member.get('name', '?')}: {e}"
                logger.debug(f"Skipping team member due to data issue: {error_msg}")
                result["errors"].append(error_msg)
            except Exception as e:
                error_msg = f"{member.get('name', '?')}: {e}"
                logger.warning(f"Failed to sync team member: {error_msg}", exc_info=True)
                result["errors"].append(error_msg)

    except FileNotFoundError:
        error_msg = f"Knowledge base file not found: {kb_path}"
        logger.warning(error_msg)
        result["errors"].append(error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Knowledge base file corrupt: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Team sync failed: {e}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)

    return result


def sync_external_contacts_from_xero() -> dict[str, Any]:
    """
    Sync external contacts (suppliers with emails) from Xero cache.
    These become People linked to clients.
    """
    import json

    cache_path = os.path.join(os.path.dirname(__file__), "..", "config", "xero_contacts.json")

    result = {
        "synced": 0,
        "with_email": 0,
        "errors": [],
    }

    try:
        with open(cache_path) as f:
            data = json.load(f)

        # Get customers with emails (these are contacts at client companies)
        customers = data.get("customers", [])

        for contact in customers:
            try:
                name = contact.get("name", "")
                email = contact.get("email", "")

                # Skip if no email (can't create meaningful contact)
                if not email or "@hrmny.co" in email.lower():
                    continue

                # Skip if name looks like a company (has LLC, etc)
                if any(x in name.lower() for x in ["llc", "fze", "l.l.c", "ltd", "inc"]):
                    continue

                # Try to find the client this contact belongs to
                client = find_client(name=name)
                client_id = client.id if client else None

                upsert_person(
                    name=name,
                    email=email,
                    type="external",
                    client_id=client_id,
                    company=name if not client_id else None,
                )

                result["synced"] += 1
                result["with_email"] += 1

            except (KeyError, TypeError) as e:
                error_msg = f"{contact.get('name', '?')}: {e}"
                logger.debug(f"Skipping contact due to data issue: {error_msg}")
                result["errors"].append(error_msg)
            except Exception as e:
                error_msg = f"{contact.get('name', '?')}: {e}"
                logger.warning(f"Failed to sync external contact: {error_msg}", exc_info=True)
                result["errors"].append(error_msg)

    except FileNotFoundError:
        error_msg = f"Xero contacts cache not found: {cache_path}"
        logger.warning(error_msg)
        result["errors"].append(error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Xero contacts cache corrupt: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"External contacts sync failed: {e}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)

    return result


def sync_all() -> dict[str, Any]:
    """Run full sync from all sources."""
    from .backup import create_backup
    from .store import init_db

    # Ensure DB exists
    init_db()

    # Create backup before sync
    create_backup(label="pre_sync")

    results = {
        "timestamp": now_iso(),
        "xero": {},
        "asana": {},
        "team": {},
        "contacts": {},
    }

    # Sync Xero clients
    logger.info("Syncing clients from Xero...")
    results["xero"] = sync_xero_clients()
    logger.info(
        f"  Synced: {results['xero']['synced']}, Created: {results['xero']['created']}, "
        f"Updated: {results['xero']['updated']}"
    )
    if results["xero"]["errors"]:
        logger.info(f"  Errors: {len(results['xero']['errors'])}")
    # Sync Asana projects
    logger.info("Syncing projects from Asana...")
    results["asana"] = sync_asana_projects()
    logger.info(f"  Synced: {results['asana']['synced']}, Unlinked: {results['asana']['unlinked']}")
    if results["asana"]["errors"]:
        logger.info(f"  Errors: {len(results['asana']['errors'])}")
    # Sync team
    logger.info("Syncing team from knowledge base...")
    results["team"] = sync_team_from_kb()
    logger.info(f"  Synced: {results['team']['synced']} ({results['team']['active']} active)")
    if results["team"]["errors"]:
        logger.info(f"  Errors: {len(results['team']['errors'])}")
    # Sync external contacts
    logger.info("Syncing external contacts...")
    results["contacts"] = sync_external_contacts_from_xero()
    logger.info(f"  Synced: {results['contacts']['synced']} with emails")
    if results["contacts"]["errors"]:
        logger.info(f"  Errors: {len(results['contacts']['errors'])}")
    return results


if __name__ == "__main__":
    results = sync_all()
    logger.info("\nSync complete!")
    logger.info(f"Clients: {results['xero']['synced']}")
    logger.info(f"Projects: {results['asana']['synced']}")
    logger.info(f"Team: {results['team']['synced']}")
    logger.info(f"Contacts: {results['contacts']['synced']}")
