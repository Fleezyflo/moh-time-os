"""
AR Calculator - Accounts Receivable metrics

Per MASTER_SPEC.md §10:
- AR Definition: status IN ('sent', 'overdue') AND paid_date IS NULL
- Valid AR: AR AND due_date IS NOT NULL AND client_id IS NOT NULL
- Invalid AR: queued for resolution, excluded from calculations
- Aging buckets: current, 1-30, 31-60, 61-90, 90+
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "state.db"


class ARCalculator:
    """Calculates AR metrics using only valid AR invoices."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_ar_summary(self) -> Dict[str, Any]:
        """Get overall AR summary."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            # Total AR (valid only)
            cursor.execute("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COUNT(DISTINCT client_id) as client_count
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND due_date IS NOT NULL
                AND client_id IS NOT NULL
            """)
            valid = dict(cursor.fetchone())
            
            # Invalid AR (missing due_date or client_id)
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND (due_date IS NULL OR client_id IS NULL)
            """)
            invalid = dict(cursor.fetchone())
            
            # By aging bucket
            cursor.execute("""
                SELECT 
                    aging_bucket,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND due_date IS NOT NULL
                AND client_id IS NOT NULL
                GROUP BY aging_bucket
                ORDER BY CASE aging_bucket
                    WHEN 'current' THEN 1
                    WHEN '1-30' THEN 2
                    WHEN '31-60' THEN 3
                    WHEN '61-90' THEN 4
                    WHEN '90+' THEN 5
                    ELSE 6
                END
            """)
            by_bucket = {row['aging_bucket']: {'count': row['count'], 'total': row['total']} 
                        for row in cursor.fetchall()}
            
            return {
                'valid_ar': valid,
                'invalid_ar': invalid,
                'by_bucket': by_bucket,
                'total_ar': valid['total'] + invalid['total'],
                'valid_pct': (valid['total'] / (valid['total'] + invalid['total']) * 100) 
                             if (valid['total'] + invalid['total']) > 0 else 100.0
            }
        finally:
            conn.close()
    
    def get_client_ar(self, client_id: str) -> Dict[str, Any]:
        """Get AR metrics for a specific client."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END) as current_amt,
                    SUM(CASE WHEN aging_bucket IN ('1-30', '31-60') THEN amount ELSE 0 END) as moderate_amt,
                    SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe_amt,
                    SUM(amount) as total,
                    COUNT(*) as count
                FROM invoices
                WHERE client_id = ? 
                AND status IN ('sent', 'overdue') 
                AND paid_date IS NULL
                AND due_date IS NOT NULL
            """, [client_id])
            
            row = cursor.fetchone()
            if not row or not row['total']:
                return {
                    'client_id': client_id,
                    'total': 0,
                    'count': 0,
                    'health_score': 100,
                    'buckets': {}
                }
            
            result = dict(row)
            
            # Calculate AR health score per spec
            # 100% current = 100 score, 100% moderate = 50 score, 100% severe = 0 score
            if result['total'] > 0:
                current_pct = (result['current_amt'] or 0) / result['total']
                moderate_pct = (result['moderate_amt'] or 0) / result['total']
                result['health_score'] = 100 * current_pct + 50 * moderate_pct
            else:
                result['health_score'] = 100
            
            result['client_id'] = client_id
            return result
        finally:
            conn.close()
    
    def get_at_risk_clients(self, threshold_days: int = 60) -> List[Dict]:
        """Get clients with significant aging AR."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    client_id,
                    SUM(amount) as total,
                    SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe_amt,
                    COUNT(*) as count
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND due_date IS NOT NULL
                AND client_id IS NOT NULL
                AND aging_bucket IN ('61-90', '90+')
                GROUP BY client_id
                HAVING severe_amt > 0
                ORDER BY severe_amt DESC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class FinanceTruth:
    """Finance Truth module - orchestrates AR calculations."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ar_calculator = ARCalculator(db_path)
    
    def run(self) -> Dict[str, Any]:
        """Run finance truth calculation."""
        summary = self.ar_calculator.get_ar_summary()
        at_risk = self.ar_calculator.get_at_risk_clients()
        
        return {
            'ar_summary': summary,
            'at_risk_clients': at_risk,
            'at_risk_count': len(at_risk),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_client_health_factor(self, client_id: str) -> float:
        """Get AR health factor for client (0-100)."""
        ar = self.ar_calculator.get_client_ar(client_id)
        return ar.get('health_score', 100)


def run_finance_truth() -> Dict[str, Any]:
    """Convenience function to run finance truth."""
    finance = FinanceTruth()
    return finance.run()


if __name__ == "__main__":
    print("Running Finance Truth...")
    result = run_finance_truth()
    
    print(f"\nAR Summary:")
    summary = result['ar_summary']
    print(f"  Valid AR: ${summary['valid_ar']['total']:,.2f} ({summary['valid_ar']['count']} invoices)")
    print(f"  Invalid AR: ${summary['invalid_ar']['total']:,.2f} ({summary['invalid_ar']['count']} invoices)")
    print(f"  Valid %: {summary['valid_pct']:.1f}%")
    
    if summary['by_bucket']:
        print(f"\n  By Aging Bucket:")
        for bucket, data in summary['by_bucket'].items():
            print(f"    {bucket}: ${data['total']:,.2f} ({data['count']} invoices)")
    
    print(f"\nAt-Risk Clients: {result['at_risk_count']}")
    for client in result['at_risk_clients'][:5]:
        print(f"  {client['client_id']}: ${client['severe_amt']:,.2f} severe")
