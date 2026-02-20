"""High-level capture functions for conversation-based item creation.

This is the main interface I (A) use to track items from conversations.
"""

import re
from datetime import date, timedelta

from .items import create_item, get_item
from .resolve import resolve_all, resolve_client


def parse_due_date(text: str) -> str | None:
    """
    Parse natural language due date.

    Examples:
        "tomorrow" -> tomorrow's date
        "monday" -> next Monday
        "feb 5" -> 2026-02-05
        "in 3 days" -> 3 days from now

    Returns ISO date string or None.
    """
    text_lower = text.lower().strip()
    today = date.today()

    # Relative dates
    if text_lower == "today":
        return today.isoformat()
    if text_lower == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if text_lower == "next week":
        return (today + timedelta(days=7)).isoformat()

    # "in X days"
    match = re.match(r"in (\d+) days?", text_lower)
    if match:
        days = int(match.group(1))
        return (today + timedelta(days=days)).isoformat()

    # Day names (next occurrence)
    days_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for day_name, day_num in days_map.items():
        if day_name in text_lower:
            current_day = today.weekday()
            days_ahead = day_num - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

    # Month day (e.g., "feb 5", "february 5")
    months = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }
    for month_name, month_num in months.items():
        match = re.search(rf"{month_name}\s+(\d{{1,2}})", text_lower)
        if match:
            day = int(match.group(1))
            year = today.year
            # If the date has passed this year, use next year
            try:
                target = date(year, month_num, day)
                if target < today:
                    target = date(year + 1, month_num, day)
                return target.isoformat()
            except ValueError:
                pass

    # ISO format passthrough
    if re.match(r"\d{4}-\d{2}-\d{2}", text_lower):
        return text_lower[:10]

    return None


def capture_item(
    what: str,
    due: str = None,
    owner: str = "me",
    client: str = None,
    person: str = None,
    project: str = None,
    stakes: str = "",
    history: str = "",
    source: str = "conversation",
    require_context: bool = False,
) -> tuple[str, str]:
    """
    Capture an item from conversation with automatic entity resolution.

    Args:
        what: What needs to happen
        due: Due date (natural language or ISO)
        owner: Who's responsible (default: "me")
        client: Client name/hint for resolution
        person: Person name/hint for resolution (counterparty - should be EXTERNAL contact)
        project: Project name/hint for resolution
        stakes: Why this matters
        history: What led to this
        source: Source type (conversation, email, meeting, etc.)
        require_context: If True, return error instead of creating with empty context

    Returns:
        Tuple of (item_id, confirmation_message)
        If require_context=True and no context resolved, item_id will be None
    """
    # Parse due date if provided
    due_iso = None
    if due:
        due_iso = parse_due_date(due)
        if not due_iso:
            # Try as-is (might be ISO format)
            due_iso = due if re.match(r"\d{4}-\d{2}-\d{2}", due) else None

    # Resolve entities
    context = resolve_all(
        client_hint=client,
        person_hint=person,
        project_hint=project,
    )

    # If require_context and nothing resolved, return error
    if require_context and not context.has_context():
        missing = []
        if client and not context.client:
            missing.append(f"client '{client}'")
        if person and not context.person:
            missing.append(f"person '{person}'")
        if project and not context.project:
            missing.append(f"project '{project}'")

        if missing:
            return (
                None,
                f"Could not resolve: {', '.join(missing)}. Please provide more details or create the entity first.",
            )
        return (
            None,
            "No context provided. Please specify at least a client, person, or project.",
        )

    # Check if person is internal team (shouldn't be counterparty for client work)
    person_warning = None
    if context.person and context.person.type == "internal" and context.client:
        # Internal team member as counterparty for client work - flag this
        person_warning = (
            f"Note: {context.person.name} is internal team, not a contact at {context.client.name}"
        )

    # Resolve owner to Person if it's a name
    owner_id = None
    if owner and owner.lower() != "me":
        from .entities import find_person

        owner_person = find_person(name=owner)
        if owner_person and owner_person.type == "internal":
            owner_id = owner_person.id

    # Create item
    item_id = create_item(
        what=what,
        owner=owner,
        owner_id=owner_id,
        due=due_iso,
        counterparty=context.person.name if context.person else person,
        counterparty_id=context.person.id if context.person else None,
        client_id=context.client.id if context.client else None,
        project_id=context.project.id if context.project else None,
        stakes=stakes,
        history=history,
        source_type=source,
    )

    # Update last_interaction for related entities
    from .entities import update_client_interaction, update_person_interaction

    if context.client:
        update_client_interaction(context.client.id)
    if context.person:
        update_person_interaction(context.person.id)

    # Build confirmation message
    parts = [f"Tracked: **{what}**"]

    if due_iso:
        parts.append(f"Due: {due_iso}")

    if context.has_context():
        context_parts = []
        if context.person:
            if context.person.type == "external":
                context_parts.append(
                    f"{context.person.name} at {context.person.company or 'client'}"
                )
            else:
                context_parts.append(f"{context.person.name} (internal)")
        if context.client:
            context_parts.append(f"[{context.client.tier}] {context.client.name}")
        if context.project:
            context_parts.append(context.project.name)
        parts.append("Context: " + " → ".join(context_parts))

    if person_warning:
        parts.append(f"⚠️ {person_warning}")

    if stakes:
        parts.append(f"Stakes: {stakes}")

    confirmation = "\n".join(parts)

    return item_id, confirmation


def quick_capture(text: str) -> tuple[str, str]:
    """
    Quick capture from a single line of text.
    Tries to extract what, due, and person from natural language.

    Examples:
        "Send proposal to Dana by Friday"
        "Follow up with GMG re: invoice tomorrow"
        "Review contract for SSS"

    Returns:
        Tuple of (item_id, confirmation_message)
    """
    # Extract due date patterns
    due = None
    due_patterns = [
        (r"\bby (\w+)\b", 1),
        (
            r"\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            1,
        ),
        (r"\bin (\d+ days?)\b", 0),
        (r"\b(next week)\b", 1),
    ]

    for pattern, group in due_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            due = match.group(group) if group else match.group(0)
            break

    # Extract person (after "to", "with", "from")
    person = None
    person_match = re.search(r"\b(?:to|with|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)
    if person_match:
        person = person_match.group(1)

    # Extract client (look for known patterns)
    client = None
    client_patterns = [
        "SSS",
        "GMG",
        "Gargash",
        "Five Guys",
        "SIXT",
        "ASICS",
        "Red Bull",
        "Chalhoub",
    ]
    for c in client_patterns:
        if c.lower() in text.lower():
            client = c
            break

    # Also check "for X" or "re: X" patterns
    if not client:
        for_match = re.search(
            r"\b(?:for|re:?)\s+([A-Z][A-Za-z\s]+?)(?:\s+(?:by|tomorrow|today|next|\.|$))",
            text,
        )
        if for_match:
            potential_client = for_match.group(1).strip()
            # Try to resolve
            result = resolve_client(potential_client)
            if result and result.confidence > 0.5:
                client = potential_client

    # Clean up "what" - remove the due date phrase
    what = text
    if due:
        what = re.sub(r"\s*by\s+\w+\s*", " ", what, flags=re.IGNORECASE)
        what = re.sub(r"\s*(tomorrow|today|next week)\s*", " ", what, flags=re.IGNORECASE)
    what = re.sub(r"\s+", " ", what).strip()

    return capture_item(
        what=what,
        due=due,
        person=person,
        client=client,
    )


def get_item_with_context(item_id: str) -> str:
    """Get full display of an item with refreshed context."""
    item = get_item(item_id)
    if not item:
        return f"Item {item_id} not found"

    return item.full_context_display()
