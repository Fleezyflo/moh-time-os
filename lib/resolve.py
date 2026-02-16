"""Entity resolution for conversation-based capture.

Resolves natural language references to entities:
- "Dana" → Person (Dana Oraibi at SSS)
- "SSS" or "Sun Sand Sports" → Client
- "Ramadan campaign" → Project
"""

from dataclasses import dataclass
from typing import Any

from .entities import (
    Client,
    Person,
    Project,
    find_client,
    find_person,
    find_project,
    list_clients,
    list_people,
    list_projects,
)


@dataclass
class ResolvedEntity:
    """Result of entity resolution."""

    entity_type: str  # 'client', 'person', 'project'
    entity: Any  # The actual entity object
    confidence: float  # 0-1
    match_reason: str  # Why this matched


@dataclass
class ResolutionContext:
    """Context for entity resolution."""

    client: Client | None = None
    project: Project | None = None
    person: Person | None = None

    def has_context(self) -> bool:
        return bool(self.client or self.project or self.person)


def resolve_client(query: str, context: ResolutionContext = None) -> ResolvedEntity | None:
    """
    Resolve a client reference.

    Args:
        query: Natural language reference (e.g., "SSS", "Sun Sand Sports", "GMG")
        context: Optional context to help disambiguation

    Returns:
        ResolvedEntity if found, None otherwise
    """
    if not query or len(query) < 2:
        return None

    query_lower = query.lower().strip()

    # Try exact match first
    client = find_client(name=query)
    if client:
        return ResolvedEntity(
            entity_type="client",
            entity=client,
            confidence=1.0,
            match_reason="exact_match",
        )

    # Try common abbreviations/aliases
    aliases = {
        "sss": "Sun Sand Sports LLC",
        "sun sand": "Sun Sand Sports LLC",
        "sun & sand": "Sun Sand Sports LLC",
        "gmg": "GMG Consumer LLC",
        "gargash": "Gargash Enterprises",
        "redbull": "Red Bull",
        "red bull": "Red Bull",
        "chalhoub": "Chalhoub",
        "five guys": "Five Guys",
        "sixt": "SIXT",
        "asics": "ASICS",
        "super care": "Super Care",
        "al joud": "Al Joud",
    }

    if query_lower in aliases:
        client = find_client(name=aliases[query_lower])
        if client:
            return ResolvedEntity(
                entity_type="client",
                entity=client,
                confidence=0.9,
                match_reason="alias_match",
            )

    # Fuzzy search through all clients
    clients = list_clients(limit=500)
    best_match = None
    best_score = 0

    for c in clients:
        name_lower = c.name.lower()

        # Check if query is substring
        if query_lower in name_lower:
            score = len(query_lower) / len(name_lower)
            if score > best_score:
                best_score = score
                best_match = c

        # Check if any word matches
        words = name_lower.split()
        for word in words:
            if word.startswith(query_lower) or query_lower.startswith(word):
                score = min(len(query_lower), len(word)) / max(len(query_lower), len(word))
                if score > best_score and score > 0.5:
                    best_score = score
                    best_match = c

    if best_match and best_score > 0.3:
        return ResolvedEntity(
            entity_type="client",
            entity=best_match,
            confidence=best_score,
            match_reason="fuzzy_match",
        )

    return None


def resolve_person(
    query: str, context: ResolutionContext = None, prefer_external: bool = False
) -> ResolvedEntity | None:
    """
    Resolve a person reference.

    Args:
        query: Natural language reference (e.g., "Dana", "Ramy", "Ahmed")
        context: Optional context (e.g., client) to help disambiguation
        prefer_external: If True, prefer external contacts over internal team

    Returns:
        ResolvedEntity if found, None otherwise
    """
    if not query or len(query) < 2:
        return None

    query_lower = query.lower().strip()

    # Try email match first
    if "@" in query:
        person = find_person(email=query)
        if person:
            return ResolvedEntity(
                entity_type="person",
                entity=person,
                confidence=1.0,
                match_reason="email_match",
            )

    # If we have client context and prefer_external, search client contacts first
    if prefer_external and context and context.client:
        from .contacts import list_client_contacts

        client_contacts = list_client_contacts(context.client.id)
        for p in client_contacts:
            if query_lower in p.name.lower():
                return ResolvedEntity(
                    entity_type="person",
                    entity=p,
                    confidence=1.0,
                    match_reason="client_contact_match",
                )

    # Search all people
    people = list_people(limit=500)
    matches = []

    for p in people:
        name_lower = p.name.lower()
        first_name = name_lower.split()[0] if name_lower.split() else ""

        # First name match
        if first_name == query_lower:
            score = 0.9
            # Boost external if prefer_external
            if (
                prefer_external
                and p.type == "external"
                or context
                and context.client
                and p.client_id == context.client.id
            ):
                score = 1.0
            matches.append((p, score, "first_name_match"))

        # Partial name match
        elif query_lower in name_lower:
            score = len(query_lower) / len(name_lower)
            if prefer_external and p.type == "external":
                score += 0.1
            matches.append((p, score, "partial_match"))

    if matches:
        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)
        best = matches[0]

        # Flag if internal team found when external was expected
        is_internal = best[0].type == "internal"
        match_reason = best[2]
        if is_internal and prefer_external:
            match_reason = f"{best[2]}_internal_only"  # Signal that only internal found

        # If multiple matches with same score, flag as ambiguous
        if len(matches) > 1 and matches[0][1] == matches[1][1]:
            return ResolvedEntity(
                entity_type="person",
                entity=best[0],
                confidence=best[1] * 0.7,
                match_reason=f"{match_reason}_ambiguous",
            )

        return ResolvedEntity(
            entity_type="person",
            entity=best[0],
            confidence=best[1],
            match_reason=match_reason,
        )

    return None


def resolve_external_contact(query: str, client_context: Client = None) -> ResolvedEntity | None:
    """
    Resolve specifically to an external contact.

    Returns None if only internal team members match.
    """
    from .contacts import find_external_contact, list_client_contacts

    # If we have client context, search that client's contacts first
    if client_context:
        contacts = list_client_contacts(client_context.id)
        query_lower = query.lower()
        for c in contacts:
            if query_lower in c.name.lower():
                return ResolvedEntity(
                    entity_type="person",
                    entity=c,
                    confidence=1.0,
                    match_reason="client_contact_match",
                )

    # Search all external contacts
    contact = find_external_contact(name=query)
    if contact:
        return ResolvedEntity(
            entity_type="person",
            entity=contact,
            confidence=0.9,
            match_reason="external_contact_match",
        )

    return None


def resolve_project(query: str, context: ResolutionContext = None) -> ResolvedEntity | None:
    """
    Resolve a project reference.

    Args:
        query: Natural language reference (e.g., "Ramadan campaign", "GMG Aswaaq")
        context: Optional context (e.g., client) to help disambiguation

    Returns:
        ResolvedEntity if found, None otherwise
    """
    if not query or len(query) < 3:
        return None

    query_lower = query.lower().strip()

    # Try exact match
    project = find_project(name=query)
    if project:
        return ResolvedEntity(
            entity_type="project",
            entity=project,
            confidence=1.0,
            match_reason="exact_match",
        )

    # If we have client context, search within that client's projects
    if context and context.client:
        projects = list_projects(client_id=context.client.id, limit=100)
        for p in projects:
            if query_lower in p.name.lower():
                return ResolvedEntity(
                    entity_type="project",
                    entity=p,
                    confidence=0.9,
                    match_reason="client_context_match",
                )

    # Fuzzy search all projects
    projects = list_projects(limit=500)
    best_match = None
    best_score = 0

    for p in projects:
        name_lower = p.name.lower()

        if query_lower in name_lower:
            score = len(query_lower) / len(name_lower)
            if score > best_score:
                best_score = score
                best_match = p

    if best_match and best_score > 0.3:
        return ResolvedEntity(
            entity_type="project",
            entity=best_match,
            confidence=best_score,
            match_reason="fuzzy_match",
        )

    return None


def resolve_all(
    client_hint: str = None,
    person_hint: str = None,
    project_hint: str = None,
) -> ResolutionContext:
    """
    Resolve multiple entity references at once.
    Uses resolved entities as context for subsequent resolutions.

    Args:
        client_hint: Client name/reference
        person_hint: Person name/reference
        project_hint: Project name/reference

    Returns:
        ResolutionContext with resolved entities
    """
    context = ResolutionContext()

    # Resolve client first (provides context for others)
    if client_hint:
        result = resolve_client(client_hint)
        if result and result.confidence > 0.5:
            context.client = result.entity

    # Resolve person with client context
    if person_hint:
        result = resolve_person(person_hint, context)
        if result and result.confidence > 0.5:
            context.person = result.entity
            # If person has a client, use that as context
            if not context.client and context.person.client_id:
                from .entities import get_client

                context.client = get_client(context.person.client_id)

    # Resolve project with client context
    if project_hint:
        result = resolve_project(project_hint, context)
        if result and result.confidence > 0.5:
            context.project = result.entity
            # If project has a client, use that as context
            if not context.client and context.project.client_id:
                from .entities import get_client

                context.client = get_client(context.project.client_id)

    return context


def describe_resolution(context: ResolutionContext) -> str:
    """Generate human-readable description of resolved context."""
    parts = []

    if context.person:
        parts.append(f"**Person:** {context.person.full_context()}")

    if context.client:
        parts.append(f"**Client:** {context.client.full_context()}")

    if context.project:
        parts.append(f"**Project:** {context.project.full_context()}")

    if not parts:
        return "No entities resolved."

    return "\n".join(parts)
