"""External contact management.

External contacts are PEOPLE at CLIENT COMPANIES, not internal team.

Examples:
- Dana Oraibi, Head of Marketing at Sun & Sand Sports
- Ahmed, Finance Manager at GMG
- Sarah, Account Manager at Gargash

NOT:
- Company names (Azai Studios, BRANDFOLIO)
- Internal team (@hrmny.co emails)
"""

import logging
import os
from typing import Any

_INTERNAL_DOMAINS = os.environ.get("MOH_INTERNAL_DOMAINS", "hrmny.co,hrmny.ae").split(",")

from .entities import (  # noqa: E402 — after env setup
    Person,
    create_person,
    find_client,
    find_person,
    get_client,
    get_person,
    list_people,
    update_client,
)

logger = logging.getLogger(__name__)


def create_external_contact(
    name: str,
    client_name: str,
    role: str = None,
    email: str = None,
    phone: str = None,
    notes: str = None,
) -> str | None:
    """
    Create an external contact linked to a client.

    Args:
        name: Contact's name (e.g., "Dana Oraibi")
        client_name: Client company name (e.g., "Sun & Sand Sports")
        role: Role at the company (e.g., "Head of Marketing")
        email: Contact's email
        phone: Contact's phone
        notes: Relationship notes

    Returns:
        Person ID if created, None if client not found
    """
    # Find the client
    client = find_client(name=client_name)
    if not client:
        return None

    # Create the person
    person_id = create_person(
        name=name,
        email=email,
        phone=phone,
        type="external",
        company=client.name,
        client_id=client.id,
        role=role,
        relationship_notes=notes or "",
    )

    # Add to client.contacts
    contacts = client.contacts or []
    contacts.append(
        {
            "person_id": person_id,
            "role": role or "Contact",
        }
    )
    update_client(client.id, contacts=contacts)

    return person_id


def list_client_contacts(client_id: str) -> list[Person]:
    """List all contacts for a client."""
    return list_people(client_id=client_id, type="external")


def list_client_contacts_by_name(client_name: str) -> list[Person]:
    """List all contacts for a client by name."""
    client = find_client(name=client_name)
    if not client:
        return []
    return list_client_contacts(client.id)


def find_external_contact(
    name: str = None,
    email: str = None,
    client_name: str = None,
) -> Person | None:
    """
    Find an external contact.

    If client_name is provided, only search within that client's contacts.
    """
    if email:
        person = find_person(email=email)
        if person and person.type == "external":
            return person

    if name:
        # If client specified, search within client
        if client_name:
            contacts = list_client_contacts_by_name(client_name)
            name_lower = name.lower()
            for c in contacts:
                if name_lower in c.name.lower():
                    return c
        else:
            # Search all external contacts
            person = find_person(name=name)
            if person and person.type == "external":
                return person

    return None


def is_internal_team(name: str = None, email: str = None) -> bool:
    """Check if a name/email refers to internal team."""
    if email and any(f"@{d}" in email.lower() for d in _INTERNAL_DOMAINS):
        return True

    if name:
        person = find_person(name=name)
        if person and person.type == "internal":
            return True

    return False


def get_contact_context(person_id: str) -> dict[str, Any]:
    """Get full context for a contact including client info."""
    person = get_person(person_id)
    if not person:
        return {}

    context = {
        "name": person.name,
        "role": person.role,
        "email": person.email,
        "type": person.type,
    }

    if person.type == "external" and person.client_id:
        client = get_client(person.client_id)
        if client:
            context["client"] = {
                "name": client.name,
                "tier": client.tier,
                "health": client.health,
                "ar_outstanding": client.ar_outstanding,
            }
            context["company"] = client.name
    elif person.type == "internal":
        context["company"] = "hrmny"

    return context


def format_contact(person: Person, include_client: bool = True) -> str:
    """Format contact for display."""
    parts = [person.name]

    if person.role:
        parts.append(f"({person.role})")

    if include_client:
        if person.type == "external" and person.client_id:
            client = get_client(person.client_id)
            if client:
                parts.append(f"at {client.name}")
        elif person.type == "internal":
            parts.append("@ hrmny")

    return " ".join(parts)


def contact_summary() -> dict[str, Any]:
    """Get summary of contacts."""
    internal = list_people(type="internal", limit=500)
    external = list_people(type="external", limit=500)

    # Count contacts by client
    by_client = {}
    for p in external:
        if p.client_id:
            client = get_client(p.client_id)
            client_name = client.name if client else "Unknown"
            by_client[client_name] = by_client.get(client_name, 0) + 1

    return {
        "internal_count": len(internal),
        "external_count": len(external),
        "by_client": by_client,
    }


if __name__ == "__main__":
    summary = contact_summary()
    logger.info("Contacts Summary:")
    logger.info(f"  Internal team: {summary['internal_count']}")
    logger.info(f"  External contacts: {summary['external_count']}")
    if summary["by_client"]:
        logger.info("\n  By client:")
        for client, count in sorted(summary["by_client"].items()):
            logger.info(f"    {client}: {count}")
