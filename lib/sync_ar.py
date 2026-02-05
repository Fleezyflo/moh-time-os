"""Sync AR data from Xero and update client tiers."""

import sys
import os
from datetime import datetime, date
from collections import defaultdict
from typing import Dict, Any, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .entities import find_client, update_client, list_clients
from .store import now_iso


def get_ar_by_contact() -> Dict[str, Dict[str, Any]]:
    """
    Get AR data from Xero invoices.
    Returns dict of contact_name -> {total, current, 30d, 60d, 90d, oldest_days}
    """
    from engine.xero_client import list_invoices
    
    invoices = list_invoices(status='AUTHORISED')
    today = date.today()
    
    ar_data = defaultdict(lambda: {
        'total': 0, 
        'current': 0, 
        '30d': 0, 
        '60d': 0, 
        '90d': 0,
        'oldest_days': 0,
        'invoice_count': 0
    })
    
    for inv in invoices:
        contact = inv.get('Contact', {}).get('Name', 'Unknown')
        amount = float(inv.get('AmountDue', 0) or 0)
        
        if amount <= 0:
            continue
        
        # Parse due date (format: 2025-11-30T00:00:00)
        due_str = inv.get('DueDateString', '')
        days_overdue = 0
        
        if due_str:
            try:
                due_date = datetime.fromisoformat(due_str.replace('T00:00:00', '')).date()
                days_overdue = (today - due_date).days
            except:
                pass
        
        ar_data[contact]['total'] += amount
        ar_data[contact]['invoice_count'] += 1
        
        if days_overdue > ar_data[contact]['oldest_days']:
            ar_data[contact]['oldest_days'] = days_overdue
        
        if days_overdue <= 0:
            ar_data[contact]['current'] += amount
        elif days_overdue <= 30:
            ar_data[contact]['30d'] += amount
        elif days_overdue <= 60:
            ar_data[contact]['60d'] += amount
        else:
            ar_data[contact]['90d'] += amount
    
    return dict(ar_data)


def infer_tier(ar_total: float, ar_90d: float) -> str:
    """
    Infer client tier from AR data.
    A: >200K total OR >50K 90+ days (big or problematic)
    B: >50K total OR >20K 90+ days
    C: everything else
    """
    if ar_total >= 200_000 or ar_90d >= 50_000:
        return 'A'
    elif ar_total >= 50_000 or ar_90d >= 20_000:
        return 'B'
    else:
        return 'C'


def infer_ar_aging(oldest_days: int) -> str:
    """Infer AR aging label from oldest invoice."""
    if oldest_days <= 0:
        return 'Current'
    elif oldest_days <= 30:
        return '30 days'
    elif oldest_days <= 60:
        return '60 days'
    else:
        return '60+ days'


def infer_health(ar_aging: str, ar_90d: float, ar_total: float) -> str:
    """
    Infer relationship health from AR.
    """
    if ar_aging == 'Current':
        return 'good'
    elif ar_aging == '30 days':
        return 'good'  # Normal payment terms
    elif ar_aging == '60 days':
        if ar_90d > 0:
            return 'fair'
        return 'good'
    else:  # 60+ days
        pct_90d = ar_90d / ar_total if ar_total > 0 else 0
        if pct_90d > 0.5:
            return 'poor'
        elif ar_90d > 50_000:
            return 'poor'
        else:
            return 'fair'


def infer_payment_pattern(ar_data: Dict) -> str:
    """Infer payment pattern from AR distribution."""
    total = ar_data['total']
    if total == 0:
        return 'Unknown'
    
    pct_current = ar_data['current'] / total
    pct_90d = ar_data['90d'] / total
    
    if pct_current > 0.8:
        return 'Reliable'
    elif pct_90d > 0.3:
        return 'Problematic'
    else:
        return 'Slow'


def sync_ar_to_clients() -> Dict[str, Any]:
    """
    Sync AR data from Xero to client entities.
    Updates: ar_outstanding, ar_aging, tier, health, payment_pattern
    """
    result = {
        'updated': 0,
        'not_found': 0,
        'no_ar': 0,
        'errors': [],
        'tier_changes': [],
    }
    
    try:
        ar_data = get_ar_by_contact()
    except Exception as e:
        result['errors'].append(f"Failed to get AR data: {e}")
        return result
    
    for contact_name, ar in ar_data.items():
        try:
            # Find matching client
            client = find_client(name=contact_name)
            if not client:
                result['not_found'] += 1
                continue
            
            # Calculate derived values
            tier = infer_tier(ar['total'], ar['90d'])
            ar_aging = infer_ar_aging(ar['oldest_days'])
            health = infer_health(ar_aging, ar['90d'], ar['total'])
            payment_pattern = infer_payment_pattern(ar)
            
            # Track tier changes
            if client.tier != tier:
                result['tier_changes'].append({
                    'client': client.name,
                    'from': client.tier,
                    'to': tier,
                    'ar_total': ar['total']
                })
            
            # Update client
            update_client(
                client.id,
                ar_outstanding=ar['total'],
                ar_aging=ar_aging,
                tier=tier,
                health=health,
                payment_pattern=payment_pattern,
            )
            
            result['updated'] += 1
            
        except Exception as e:
            result['errors'].append(f"{contact_name}: {e}")
    
    # Count clients with no AR (set to Current, keep tier C)
    all_clients = list_clients()
    ar_contact_names = set(ar_data.keys())
    
    for client in all_clients:
        if client.name not in ar_contact_names and client.ar_outstanding == 0:
            result['no_ar'] += 1
    
    return result


def print_ar_report():
    """Print AR report for debugging."""
    ar_data = get_ar_by_contact()
    
    print("AR Report from Xero")
    print("=" * 100)
    print(f"{'Contact':<40} {'Total':>12} {'Current':>10} {'30d':>10} {'60d':>10} {'90d+':>10} {'Tier':>6}")
    print("-" * 100)
    
    sorted_ar = sorted(ar_data.items(), key=lambda x: x[1]['total'], reverse=True)
    
    for name, data in sorted_ar[:20]:
        tier = infer_tier(data['total'], data['90d'])
        print(f"{name[:40]:<40} {data['total']:>12,.0f} {data['current']:>10,.0f} {data['30d']:>10,.0f} {data['60d']:>10,.0f} {data['90d']:>10,.0f} {tier:>6}")
    
    print("-" * 100)
    print(f"Total contacts with AR: {len(ar_data)}")
    print(f"Total AR: {sum(d['total'] for d in ar_data.values()):,.0f} AED")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--sync':
        print("Syncing AR data to clients...")
        result = sync_ar_to_clients()
        print(f"Updated: {result['updated']}")
        print(f"Not found: {result['not_found']}")
        print(f"No AR: {result['no_ar']}")
        
        if result['tier_changes']:
            print("\nTier changes:")
            for change in result['tier_changes']:
                print(f"  {change['client']}: {change['from']} → {change['to']} ({change['ar_total']:,.0f} AED)")
        
        if result['errors']:
            print(f"\nErrors: {len(result['errors'])}")
    else:
        print_ar_report()
