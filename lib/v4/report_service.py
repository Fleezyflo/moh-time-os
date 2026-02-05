"""
Time OS V4 - Report Service

Generates immutable report snapshots from templates.
Reports are evidence-backed and reproducible.
"""

import sqlite3
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os

from .signal_service import get_signal_service
from .proposal_service import get_proposal_service
from .issue_service import get_issue_service

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')


class ReportService:
    """Service for generating and storing report snapshots."""
    
    TEMPLATE_TYPES = {
        'client_weekly': {
            'sections': ['summary', 'active_projects', 'open_issues', 'signals', 'ar_status'],
            'default_period_days': 7
        },
        'client_monthly': {
            'sections': ['executive_summary', 'project_status', 'financial_summary', 'risk_assessment', 'recommendations'],
            'default_period_days': 30
        },
        'engagement_status': {
            'sections': ['progress', 'deliverables', 'blockers', 'next_steps'],
            'default_period_days': 7
        },
        'exec_pack': {
            'sections': ['portfolio_health', 'critical_risks', 'ar_aging', 'resource_utilization', 'key_decisions'],
            'default_period_days': 7
        }
    }
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.signal_svc = get_signal_service()
        self.proposal_svc = get_proposal_service()
        self.issue_svc = get_issue_service()
        self._ensure_templates()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _generate_id(self, prefix: str = 'rpt') -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
    
    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _ensure_templates(self):
        """Ensure default templates exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            for template_type, config in self.TEMPLATE_TYPES.items():
                cursor.execute(
                    "SELECT template_id FROM report_templates WHERE template_type = ?",
                    (template_type,)
                )
                if not cursor.fetchone():
                    template_id = self._generate_id('tpl')
                    cursor.execute("""
                        INSERT INTO report_templates (template_id, template_type, sections, default_scopes)
                        VALUES (?, ?, ?, ?)
                    """, (
                        template_id, template_type,
                        json.dumps(config['sections']),
                        json.dumps({'period_days': config['default_period_days']})
                    ))
            conn.commit()
        finally:
            conn.close()
    
    def generate_client_report(
        self,
        client_id: str,
        template_type: str = 'client_weekly',
        period_days: int = None
    ) -> Dict[str, Any]:
        """Generate a client report snapshot."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Get template
            cursor.execute(
                "SELECT template_id, sections FROM report_templates WHERE template_type = ?",
                (template_type,)
            )
            row = cursor.fetchone()
            if not row:
                return {'status': 'error', 'error': f'Template {template_type} not found'}
            
            template_id, sections_json = row
            sections = json.loads(sections_json)
            period_days = period_days or self.TEMPLATE_TYPES[template_type]['default_period_days']
            
            # Get client info
            cursor.execute("SELECT name, tier, relationship_health FROM clients WHERE id = ?", (client_id,))
            client_row = cursor.fetchone()
            if not client_row:
                return {'status': 'error', 'error': 'Client not found'}
            
            client_name, tier, health = client_row
            
            # Build report content
            period_end = datetime.now()
            period_start = period_end - timedelta(days=period_days)
            
            content = {
                'client_id': client_id,
                'client_name': client_name,
                'tier': tier,
                'health': health,
                'period': {'start': period_start.isoformat(), 'end': period_end.isoformat()},
                'sections': {}
            }
            
            evidence_ids = []
            
            # Summary section
            if 'summary' in sections or 'executive_summary' in sections:
                signals = self.signal_svc.find_signals(
                    entity_ref_type='client', entity_ref_id=client_id, status='active'
                )
                content['sections']['summary'] = {
                    'total_signals': len(signals),
                    'by_severity': {},
                    'key_signals': signals[:5]
                }
                for sig in signals:
                    sev = sig['severity']
                    content['sections']['summary']['by_severity'][sev] = \
                        content['sections']['summary']['by_severity'].get(sev, 0) + 1
            
            # Active projects
            if 'active_projects' in sections or 'project_status' in sections:
                cursor.execute("""
                    SELECT id, name, status, health FROM projects
                    WHERE client_id = ? AND status = 'active'
                """, (client_id,))
                projects = [{'id': r[0], 'name': r[1], 'status': r[2], 'health': r[3]} 
                           for r in cursor.fetchall()]
                content['sections']['projects'] = projects
            
            # Open issues
            if 'open_issues' in sections:
                cursor.execute("""
                    SELECT issue_id, headline, state, priority FROM issues
                    WHERE primary_ref_type = 'client' AND primary_ref_id = ?
                    AND state NOT IN ('resolved', 'handed_over')
                """, (client_id,))
                issues = [{'id': r[0], 'headline': r[1], 'state': r[2], 'priority': r[3]}
                         for r in cursor.fetchall()]
                content['sections']['issues'] = issues
            
            # AR status
            if 'ar_status' in sections or 'financial_summary' in sections:
                cursor.execute("""
                    SELECT financial_ar_total, financial_ar_overdue, financial_ar_aging_bucket,
                           financial_last_invoice_date, financial_last_payment_date
                    FROM clients WHERE id = ?
                """, (client_id,))
                ar_row = cursor.fetchone()
                if ar_row:
                    content['sections']['financials'] = {
                        'ar_total': ar_row[0],
                        'ar_overdue': ar_row[1],
                        'aging_bucket': ar_row[2],
                        'last_invoice': ar_row[3],
                        'last_payment': ar_row[4]
                    }
            
            # Create snapshot
            snapshot_id = self._generate_id('snap')
            content_json = json.dumps(content, default=str)
            immutable_hash = self._hash_content(content_json)
            
            cursor.execute("""
                INSERT INTO report_snapshots
                (snapshot_id, template_id, scope_ref_type, scope_ref_id,
                 period_start, period_end, content, evidence_excerpt_ids, immutable_hash)
                VALUES (?, ?, 'client', ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id, template_id, client_id,
                period_start.isoformat(), period_end.isoformat(),
                content_json, json.dumps(evidence_ids), immutable_hash
            ))
            
            conn.commit()
            
            return {
                'status': 'generated',
                'snapshot_id': snapshot_id,
                'client_name': client_name,
                'period_days': period_days,
                'sections': list(content['sections'].keys()),
                'hash': immutable_hash
            }
            
        finally:
            conn.close()
    
    def generate_exec_pack(self, period_days: int = 7) -> Dict[str, Any]:
        """Generate executive pack report."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            period_end = datetime.now()
            period_start = period_end - timedelta(days=period_days)
            
            content = {
                'type': 'exec_pack',
                'period': {'start': period_start.isoformat(), 'end': period_end.isoformat()},
                'sections': {}
            }
            
            # Portfolio health
            cursor.execute("""
                SELECT relationship_health, COUNT(*) FROM clients
                WHERE tier IN ('A', 'B')
                GROUP BY relationship_health
            """)
            content['sections']['portfolio_health'] = {
                'by_health': {r[0] or 'unknown': r[1] for r in cursor.fetchall()}
            }
            
            # Critical risks
            signals = self.signal_svc.find_signals(severity='critical', status='active', limit=10)
            content['sections']['critical_risks'] = {
                'count': len(signals),
                'top_risks': [{'type': s['signal_type'], 'entity': f"{s['entity_ref_type']}/{s['entity_ref_id'][:8]}"} 
                             for s in signals]
            }
            
            # AR aging
            cursor.execute("""
                SELECT SUM(financial_ar_total), SUM(financial_ar_overdue)
                FROM clients
            """)
            ar_row = cursor.fetchone()
            content['sections']['ar_summary'] = {
                'total_ar': ar_row[0] or 0,
                'total_overdue': ar_row[1] or 0
            }
            
            # Open proposals/issues counts
            proposals = self.proposal_svc.get_all_open_proposals(limit=100)
            issues = self.issue_svc.get_open_issues(limit=100)
            content['sections']['workload'] = {
                'open_proposals': len(proposals),
                'open_issues': len(issues)
            }
            
            # Create snapshot
            cursor.execute(
                "SELECT template_id FROM report_templates WHERE template_type = 'exec_pack'"
            )
            template_row = cursor.fetchone()
            template_id = template_row[0] if template_row else 'tpl_exec'
            
            snapshot_id = self._generate_id('snap')
            content_json = json.dumps(content, default=str)
            immutable_hash = self._hash_content(content_json)
            
            cursor.execute("""
                INSERT INTO report_snapshots
                (snapshot_id, template_id, scope_ref_type, scope_ref_id,
                 period_start, period_end, content, evidence_excerpt_ids, immutable_hash)
                VALUES (?, ?, 'portfolio', 'all', ?, ?, ?, '[]', ?)
            """, (
                snapshot_id, template_id,
                period_start.isoformat(), period_end.isoformat(),
                content_json, immutable_hash
            ))
            
            conn.commit()
            
            return {
                'status': 'generated',
                'snapshot_id': snapshot_id,
                'content': content,
                'hash': immutable_hash
            }
            
        finally:
            conn.close()
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a report snapshot."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT snapshot_id, template_id, scope_ref_type, scope_ref_id,
                       period_start, period_end, generated_at, content, immutable_hash
                FROM report_snapshots WHERE snapshot_id = ?
            """, (snapshot_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'snapshot_id': row[0],
                'template_id': row[1],
                'scope_ref_type': row[2],
                'scope_ref_id': row[3],
                'period_start': row[4],
                'period_end': row[5],
                'generated_at': row[6],
                'content': json.loads(row[7]),
                'immutable_hash': row[8]
            }
        finally:
            conn.close()
    
    def list_snapshots(self, scope_type: str = None, scope_id: str = None, limit: int = 20) -> List[Dict]:
        """List report snapshots."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT snapshot_id, template_id, scope_ref_type, scope_ref_id,
                       period_start, period_end, generated_at, immutable_hash
                FROM report_snapshots WHERE 1=1
            """
            params = []
            
            if scope_type:
                query += " AND scope_ref_type = ?"
                params.append(scope_type)
            if scope_id:
                query += " AND scope_ref_id = ?"
                params.append(scope_id)
            
            query += " ORDER BY generated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            return [{
                'snapshot_id': r[0],
                'template_id': r[1],
                'scope_ref_type': r[2],
                'scope_ref_id': r[3],
                'period_start': r[4],
                'period_end': r[5],
                'generated_at': r[6],
                'hash': r[7]
            } for r in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get report statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM report_templates")
            templates = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM report_snapshots")
            snapshots = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT scope_ref_type, COUNT(*) FROM report_snapshots
                GROUP BY scope_ref_type
            """)
            by_scope = {r[0]: r[1] for r in cursor.fetchall()}
            
            return {
                'templates': templates,
                'snapshots': snapshots,
                'by_scope': by_scope
            }
        finally:
            conn.close()


_report_service = None

def get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
