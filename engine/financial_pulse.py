"""
Financial Pulse — MVP

One question: "Who owes us money and should I care?"

No database, no sync scheduling, no health scores.
Just: call Xero, group by client, sort by age, flag problems.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from engine.xero_client import list_invoices


@dataclass
class OutstandingInvoice:
    client_name: str
    invoice_number: str
    amount_due: float
    currency: str
    due_date: str
    days_overdue: int  # negative = not yet due
    invoice_date: str
    xero_id: str


# ClientReceivables is defined below with severity logic


def parse_date(date_str: str | None) -> datetime | None:
    """Parse Xero date format."""
    if not date_str:
        return None
    # Xero returns dates like "/Date(1234567890000)/" or ISO format
    if "/Date(" in date_str:
        ms = int(date_str.split("(")[1].split(")")[0].split("+")[0].split("-")[0])
        return datetime.fromtimestamp(ms / 1000, tz=UTC)
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_outstanding_invoices() -> list[OutstandingInvoice]:
    """Fetch outstanding invoices from Xero."""

    # Get invoices that are AUTHORISED (sent but not paid)
    invoices = list_invoices(status="AUTHORISED")

    today = datetime.now(UTC).date()
    outstanding = []

    for inv in invoices:
        amount_due = float(inv.get("AmountDue", 0))

        # Skip if nothing owed
        if amount_due <= 0:
            continue

        # Parse dates
        due_date = parse_date(inv.get("DueDateString") or inv.get("DueDate"))
        invoice_date = parse_date(inv.get("DateString") or inv.get("Date"))

        if due_date:
            days_overdue = (today - due_date.date()).days
            due_date_str = due_date.date().isoformat()
        else:
            days_overdue = 0
            due_date_str = "unknown"

        if invoice_date:
            invoice_date_str = invoice_date.date().isoformat()
        else:
            invoice_date_str = "unknown"

        # Get client name
        contact = inv.get("Contact", {})
        client_name = contact.get("Name", "Unknown Client")

        outstanding.append(
            OutstandingInvoice(
                client_name=client_name,
                invoice_number=inv.get("InvoiceNumber", ""),
                amount_due=amount_due,
                currency=inv.get("CurrencyCode", "AED"),
                due_date=due_date_str,
                days_overdue=days_overdue,
                invoice_date=invoice_date_str,
                xero_id=inv.get("InvoiceID", ""),
            )
        )

    return outstanding


@dataclass
class ClientReceivables:
    client_name: str
    total_outstanding: float
    invoices: list[OutstandingInvoice]
    oldest_overdue_days: int
    severity: str  # critical, warning, watch, current
    attention_reason: str | None
    is_internal: bool


# Known internal/employee patterns (reimbursements, not real AR)
INTERNAL_PATTERNS = [
    "joshua daniells",
    "ramy elbendary",
    "youssef fakhreddine",
    "maher al chatty",
    "dana nabah",
    "molham",
    "ayham",
    "krystie",
    "aubrey",
    "raafat",
    "emirates nbd",  # bank, not client
]


def is_internal_entity(name: str) -> bool:
    """Check if this looks like an internal entity, not a client."""
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in INTERNAL_PATTERNS)


def calculate_severity(
    days_overdue: int, amount: float, is_internal: bool
) -> tuple[str, str | None]:
    """
    Calculate severity tier and reason.

    Returns (severity, reason)
    - critical: 90+ days OR large amount 60+ days
    - warning: 30-90 days AND meaningful amount
    - watch: 14-30 days AND large amount
    - current: on track
    """

    # Internal items are always low priority
    if is_internal:
        if days_overdue > 60:
            return "watch", f"Internal: {days_overdue} days"
        return "current", None

    # Critical: very old or large+old
    if days_overdue > 90:
        return "critical", f"{days_overdue} days overdue"
    if days_overdue > 60 and amount > 50000:
        return "critical", f"{amount:,.0f} AED, {days_overdue} days overdue"

    # Warning: meaningfully overdue with meaningful amount
    if days_overdue > 30 and amount > 10000:
        return "warning", f"{days_overdue} days overdue"
    if days_overdue > 60 and amount > 5000:
        return "warning", f"{days_overdue} days overdue"

    # Watch: slightly late but significant
    if days_overdue > 14 and amount > 20000:
        return "watch", f"{amount:,.0f} AED, {days_overdue} days"

    # Current: on track
    return "current", None


def group_by_client(invoices: list[OutstandingInvoice]) -> list[ClientReceivables]:
    """Group invoices by client and compute summary with severity."""

    clients: dict[str, list[OutstandingInvoice]] = {}

    for inv in invoices:
        if inv.client_name not in clients:
            clients[inv.client_name] = []
        clients[inv.client_name].append(inv)

    result = []

    for client_name, client_invoices in clients.items():
        total = sum(inv.amount_due for inv in client_invoices)
        oldest_overdue = max(inv.days_overdue for inv in client_invoices)
        is_internal = is_internal_entity(client_name)

        severity, reason = calculate_severity(oldest_overdue, total, is_internal)

        result.append(
            ClientReceivables(
                client_name=client_name,
                total_outstanding=total,
                invoices=sorted(client_invoices, key=lambda x: -x.days_overdue),
                oldest_overdue_days=oldest_overdue,
                severity=severity,
                attention_reason=reason,
                is_internal=is_internal,
            )
        )

    # Sort by severity, then by amount (biggest first within severity)
    severity_order = {"critical": 0, "warning": 1, "watch": 2, "current": 3}
    result.sort(key=lambda x: (severity_order.get(x.severity, 9), -x.total_outstanding))

    return result


def format_days(days: int) -> str:
    """Format days overdue/until due."""
    if days > 0:
        return f"{days} days overdue"
    if days < 0:
        return f"{-days} days until due"
    return "due today"


def render_pulse(clients: list[ClientReceivables]) -> str:
    """Render the financial pulse as plain text."""

    lines = []
    today = datetime.now(UTC).strftime("%b %d, %Y")

    lines.append(f"RECEIVABLES — {today}")
    lines.append("")

    # Split by severity
    critical = [c for c in clients if c.severity == "critical"]
    warning = [c for c in clients if c.severity == "warning"]

    # Quick summary
    critical_total = sum(c.total_outstanding for c in critical)
    warning_total = sum(c.total_outstanding for c in warning)

    if critical:
        lines.append(
            f"⚡ {len(critical)} critical ({critical_total:,.0f} AED) • {len(warning)} warning ({warning_total:,.0f} AED)"
        )
    elif warning:
        lines.append(f"⚡ {len(warning)} items need attention ({warning_total:,.0f} AED)")
    else:
        lines.append("⚡ Collections on track")
    lines.append("")

    # Additional severity splits
    watch = [c for c in clients if c.severity == "watch"]
    [c for c in clients if c.severity == "current"]

    # Exclude internal from totals shown
    external_clients = [c for c in clients if not c.is_internal]
    internal_clients = [c for c in clients if c.is_internal]

    total_outstanding = sum(c.total_outstanding for c in clients)
    external_total = sum(c.total_outstanding for c in external_clients)
    internal_total = sum(c.total_outstanding for c in internal_clients)

    # Critical section
    if critical:
        lines.append("🔴 CRITICAL (60+ days, large amounts):")
        for client in critical:
            lines.append(f"   {client.client_name}")
            lines.append(f"      {client.total_outstanding:,.0f} AED — {client.attention_reason}")
        lines.append("")

    # Warning section
    if warning:
        lines.append("🟡 WARNING (30+ days):")
        for client in warning:
            lines.append(
                f"   • {client.client_name} — {client.total_outstanding:,.0f} AED, {client.attention_reason}"
            )
        lines.append("")

    # Watch section (brief)
    if watch:
        watch_external = [c for c in watch if not c.is_internal]
        if watch_external:
            lines.append("👀 WATCH:")
            for client in watch_external[:5]:
                lines.append(f"   • {client.client_name} — {client.total_outstanding:,.0f} AED")
            if len(watch_external) > 5:
                lines.append(f"   (+{len(watch_external) - 5} more)")
            lines.append("")

    # Summary if nothing critical
    if not critical and not warning:
        lines.append("✓ No critical items")
        lines.append("")

    # Totals
    lines.append("─" * 45)
    lines.append(f"TOTAL OUTSTANDING:  {total_outstanding:>12,.0f} AED")
    if internal_total > 0:
        lines.append(f"  ├─ External:      {external_total:>12,.0f} AED")
        lines.append(f"  └─ Internal:      {internal_total:>12,.0f} AED (reimbursements etc)")
    lines.append("")

    # Aging breakdown (external only)
    current_bucket = sum(
        c.total_outstanding for c in external_clients if c.oldest_overdue_days <= 0
    )
    overdue_30 = sum(
        c.total_outstanding for c in external_clients if 0 < c.oldest_overdue_days <= 30
    )
    overdue_60 = sum(
        c.total_outstanding for c in external_clients if 30 < c.oldest_overdue_days <= 60
    )
    overdue_90 = sum(c.total_outstanding for c in external_clients if c.oldest_overdue_days > 60)

    # Calculate health indicator
    if external_total > 0:
        healthy_pct = (current_bucket + overdue_30) / external_total * 100
        health_indicator = (
            "✓ Healthy" if healthy_pct >= 70 else "⚠️ At Risk" if healthy_pct >= 50 else "🔴 Poor"
        )
    else:
        healthy_pct = 100
        health_indicator = "✓ Clean"

    lines.append(
        f"AGING (external only):           {health_indicator} ({healthy_pct:.0f}% < 30 days)"
    )
    lines.append(f"  Current:      {current_bucket:>12,.0f} AED")
    lines.append(f"  1-30 days:    {overdue_30:>12,.0f} AED")
    lines.append(f"  31-60 days:   {overdue_60:>12,.0f} AED")
    lines.append(f"  60+ days:     {overdue_90:>12,.0f} AED")

    # Call out if 60+ is large
    if overdue_90 > 0 and external_total > 0:
        pct_bad = overdue_90 / external_total * 100
        if pct_bad > 30:
            lines.append(f"  ⚠️  {pct_bad:.0f}% of AR is 60+ days — review needed")

    return "\n".join(lines)


def render_client_detail(client: ClientReceivables) -> str:
    """Render detail for a single client."""

    severity_icons = {"critical": "🔴", "warning": "🟡", "watch": "👀", "current": "✓"}

    lines = []
    lines.append(f"CLIENT: {client.client_name} {severity_icons.get(client.severity, '')}")
    lines.append("=" * 50)
    lines.append(f"Total Outstanding: {client.total_outstanding:,.0f} AED")
    lines.append(f"Oldest Overdue: {format_days(client.oldest_overdue_days)}")
    lines.append(f"Severity: {client.severity.upper()}")
    if client.attention_reason:
        lines.append(f"Reason: {client.attention_reason}")
    if client.is_internal:
        lines.append("(Internal/reimbursement)")
    lines.append("")
    lines.append("INVOICES:")

    for inv in client.invoices:
        if inv.days_overdue > 60:
            status = "🔴"
        elif inv.days_overdue > 30:
            status = "🟡"
        else:
            status = "  "
        lines.append(
            f"{status} {inv.invoice_number:15} {inv.amount_due:>12,.0f} AED  {format_days(inv.days_overdue):>20}"
        )

    return "\n".join(lines)


def financial_pulse(*, client_filter: str | None = None, verbose: bool = False) -> dict[str, Any]:
    """
    Main entry point for financial pulse.

    Returns structured data and optionally prints formatted output.
    """

    print("Fetching invoices from Xero...")
    invoices = get_outstanding_invoices()
    print(f"Found {len(invoices)} outstanding invoices")

    clients = group_by_client(invoices)

    if client_filter:
        clients = [c for c in clients if client_filter.lower() in c.client_name.lower()]

    output = render_pulse(clients)
    print("\n" + output)

    if verbose and clients:
        print("\n" + "=" * 50)
        print("DETAIL BY CLIENT:")
        print("=" * 50)
        for client in clients:
            print("\n" + render_client_detail(client))

    # Return structured data for programmatic use
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "total_outstanding": sum(c.total_outstanding for c in clients),
        "external_outstanding": sum(c.total_outstanding for c in clients if not c.is_internal),
        "critical": [
            {
                "client": c.client_name,
                "amount": c.total_outstanding,
                "reason": c.attention_reason,
                "oldest_overdue_days": c.oldest_overdue_days,
            }
            for c in clients
            if c.severity == "critical"
        ],
        "warning": [
            {
                "client": c.client_name,
                "amount": c.total_outstanding,
                "reason": c.attention_reason,
            }
            for c in clients
            if c.severity == "warning"
        ],
        "clients": [
            {
                "name": c.client_name,
                "outstanding": c.total_outstanding,
                "oldest_overdue_days": c.oldest_overdue_days,
                "severity": c.severity,
                "is_internal": c.is_internal,
                "invoice_count": len(c.invoices),
            }
            for c in clients
        ],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Financial Pulse — Who owes us money?")
    parser.add_argument("--client", "-c", help="Filter by client name")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show invoice detail")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON instead of text")

    args = parser.parse_args()

    result = financial_pulse(client_filter=args.client, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2))
