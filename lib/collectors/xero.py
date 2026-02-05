"""
Xero Collector - Syncs client AR data from Xero.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.state_store import get_store


class XeroCollector:
    """Collector that syncs client AR data from Xero."""
    
    def __init__(self, config: dict, store=None):
        self.config = config
        self.store = store or get_store()
    
    def should_sync(self) -> bool:
        """Always sync when called."""
        return True
    
    def sync(self) -> Dict:
        """Sync AR data from Xero to clients table AND invoices table."""
        try:
            from collectors.xero_ops import get_outstanding_invoices
            
            invoices = get_outstanding_invoices()
            now = datetime.now().isoformat()
            
            # Clear old Xero invoices and insert fresh
            self.store.query("DELETE FROM invoices WHERE source = 'xero'")
            
            # Group by contact for client AR rollup
            by_contact = {}
            invoices_stored = 0
            
            for inv in invoices:
                contact = inv['contact']
                if contact not in by_contact:
                    by_contact[contact] = {
                        'total_ar': 0,
                        'overdue_ar': 0,
                        'max_days_overdue': 0,
                        'invoice_count': 0,
                        'client_id': None
                    }
                by_contact[contact]['total_ar'] += inv['amount_due']
                by_contact[contact]['invoice_count'] += 1
                if inv['is_overdue']:
                    by_contact[contact]['overdue_ar'] += inv['amount_due']
                    if inv['days_overdue'] > by_contact[contact]['max_days_overdue']:
                        by_contact[contact]['max_days_overdue'] = inv['days_overdue']
            
            # Find client IDs first
            for contact_name in by_contact.keys():
                clients = self.store.query("""
                    SELECT id, name FROM clients 
                    WHERE LOWER(name) LIKE LOWER(?) 
                    OR LOWER(?) LIKE '%' || LOWER(name) || '%'
                    LIMIT 1
                """, [f'%{contact_name}%', contact_name])
                if clients:
                    by_contact[contact_name]['client_id'] = clients[0]['id']
            
            # Store individual invoices
            for inv in invoices:
                contact = inv['contact']
                client_id = by_contact.get(contact, {}).get('client_id')
                
                status = 'overdue' if inv['is_overdue'] else 'sent'
                
                # Determine aging bucket
                days_over = inv['days_overdue'] if inv['is_overdue'] else 0
                if days_over >= 90:
                    aging = '90+'
                elif days_over >= 61:
                    aging = '61-90'
                elif days_over >= 31:
                    aging = '31-60'
                elif days_over >= 1:
                    aging = '1-30'
                else:
                    aging = 'current'
                
                self.store.insert('invoices', {
                    'id': f"xero_{inv['number'].replace(' ', '_').replace('/', '-')}",
                    'source': 'xero',
                    'external_id': inv['number'],
                    'client_id': client_id,
                    'client_name': contact,
                    'amount': inv['amount_due'],
                    'currency': inv.get('currency', 'AED'),
                    'issue_date': inv['due_date'],  # Using due_date as proxy if issue_date not available
                    'due_date': inv['due_date'],
                    'status': status,
                    'aging_bucket': aging,
                    'created_at': now,
                    'updated_at': now
                })
                invoices_stored += 1
            
            # Update clients with AR rollup
            updated = 0
            for contact_name, ar_data in by_contact.items():
                client_id = ar_data.get('client_id')
                if client_id:
                    days = ar_data['max_days_overdue']
                    if days >= 90:
                        bucket = '90+'
                    elif days >= 60:
                        bucket = '60'
                    elif days >= 30:
                        bucket = '30'
                    else:
                        bucket = 'current'
                    
                    self.store.update('clients', client_id, {
                        'financial_ar_outstanding': ar_data['total_ar'],
                        'financial_ar_aging': bucket,
                        'updated_at': now
                    })
                    updated += 1
            
            return {
                'clients_updated': updated,
                'invoices_stored': invoices_stored,
                'contacts_found': len(by_contact),
                'total_ar': sum(c['total_ar'] for c in by_contact.values()),
                'timestamp': now
            }
            
        except Exception as e:
            return {'error': str(e), 'synced': 0}


def sync():
    """Run Xero sync."""
    collector = XeroCollector({})
    return collector.sync()


if __name__ == '__main__':
    result = sync()
    print(f"Xero sync: {result}")
