#!/usr/bin/env python3
"""
Xero Operational Intelligence collector.

Surfaces:
- Overdue receivables (AR)
- Outstanding invoices
- Aged receivables summary
"""

import sys
from pathlib import Path
from datetime import datetime, date

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from engine.xero_client import (
    list_invoices, get_aged_receivables, xero_get
)


def get_outstanding_invoices() -> list:
    """Get all outstanding (unpaid) invoices."""
    try:
        invoices = list_invoices(status="AUTHORISED")
        outstanding = []
        
        for inv in invoices:
            if inv.get("Type") != "ACCREC":  # Only receivables
                continue
                
            amount_due = float(inv.get("AmountDue", 0))
            if amount_due <= 0:
                continue
            
            due_date = inv.get("DueDateString", "")
            contact = inv.get("Contact", {}).get("Name", "Unknown")
            inv_number = inv.get("InvoiceNumber", "")
            
            # Check if overdue
            is_overdue = False
            days_overdue = 0
            if due_date:
                try:
                    due_dt = datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S")
                    if due_dt.date() < date.today():
                        is_overdue = True
                        days_overdue = (date.today() - due_dt.date()).days
                except:
                    pass
            
            outstanding.append({
                "number": inv_number,
                "contact": contact,
                "amount_due": amount_due,
                "currency": inv.get("CurrencyCode", "AED"),
                "due_date": due_date[:10] if due_date else None,
                "is_overdue": is_overdue,
                "days_overdue": days_overdue,
            })
        
        # Sort by overdue first, then by amount
        outstanding.sort(key=lambda x: (-x["days_overdue"], -x["amount_due"]))
        return outstanding
        
    except Exception as e:
        print(f"Error fetching invoices: {e}")
        return []


def get_ar_summary() -> dict:
    """Get accounts receivable summary."""
    outstanding = get_outstanding_invoices()
    
    total_ar = sum(inv["amount_due"] for inv in outstanding)
    overdue = [inv for inv in outstanding if inv["is_overdue"]]
    total_overdue = sum(inv["amount_due"] for inv in overdue)
    
    return {
        "total_outstanding": len(outstanding),
        "total_ar": total_ar,
        "overdue_count": len(overdue),
        "overdue_amount": total_overdue,
        "invoices": outstanding,
        "overdue_invoices": overdue,
    }


def format_currency(amount: float, currency: str = "AED") -> str:
    """Format currency amount."""
    if currency == "AED":
        return f"AED {amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def generate_xero_report() -> dict:
    """Generate Xero operational report."""
    print("Fetching Xero AR data...")
    summary = get_ar_summary()
    return summary


def format_report(report: dict) -> str:
    """Format Xero report as markdown."""
    lines = [
        "## 💰 Accounts Receivable",
        "",
    ]
    
    total_ar = report.get("total_ar", 0)
    overdue_amount = report.get("overdue_amount", 0)
    overdue_count = report.get("overdue_count", 0)
    
    lines.append(f"**Total AR:** {format_currency(total_ar)}")
    if overdue_amount > 0:
        lines.append(f"**⚠️ Overdue:** {format_currency(overdue_amount)} ({overdue_count} invoices)")
    lines.append("")
    
    # Show overdue invoices
    overdue = report.get("overdue_invoices", [])
    if overdue:
        lines.append("### Overdue Invoices")
        for inv in overdue[:5]:
            days = inv["days_overdue"]
            lines.append(
                f"- {inv['contact']}: {format_currency(inv['amount_due'])} "
                f"({days}d overdue) — #{inv['number']}"
            )
        if len(overdue) > 5:
            lines.append(f"  ... +{len(overdue) - 5} more")
        lines.append("")
    
    # Show upcoming (not overdue)
    upcoming = [inv for inv in report.get("invoices", []) if not inv["is_overdue"]]
    if upcoming:
        lines.append(f"### Upcoming ({len(upcoming)} invoices)")
        for inv in upcoming[:3]:
            lines.append(
                f"- {inv['contact']}: {format_currency(inv['amount_due'])} "
                f"(due {inv['due_date']})"
            )
        if len(upcoming) > 3:
            lines.append(f"  ... +{len(upcoming) - 3} more")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_xero_report()
    print("\n" + "=" * 50)
    print(format_report(report))
    
    print("\n--- Summary ---")
    print(f"Total AR: {format_currency(report.get('total_ar', 0))}")
    print(f"Overdue: {format_currency(report.get('overdue_amount', 0))} ({report.get('overdue_count', 0)} invoices)")
