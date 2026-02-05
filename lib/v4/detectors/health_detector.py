"""
Time OS V4 - Health Detector

Detects client/project health signals:
- Relationship health changes
- Communication gaps
- AR aging concerns
- Project health degradation
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import os

from .base import BaseDetector
from ..artifact_service import get_artifact_service

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'moh_time_os.db')


class HealthDetector(BaseDetector):
    """
    Detects health-related signals for clients and projects.
    
    Signal types produced:
    - client_health_declining: Client relationship health is declining
    - communication_gap: No recent communication with client
    - ar_aging_risk: Accounts receivable aging beyond threshold
    - project_health_at_risk: Project showing signs of trouble
    """
    
    detector_id = 'health_detector'
    version = '1.0.0'
    description = 'Detects client and project health signals'
    signal_types = ['client_health_declining', 'communication_gap', 'ar_aging_risk', 'project_health_at_risk']
    
    # Thresholds
    COMMUNICATION_GAP_DAYS = 14  # Alert if no contact in N days
    AR_AGING_DAYS = 30  # Alert if AR overdue by N days
    AR_AMOUNT_THRESHOLD = 5000  # Minimum amount to trigger signal
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'communication_gap_days': self.COMMUNICATION_GAP_DAYS,
            'ar_aging_days': self.AR_AGING_DAYS,
            'ar_amount_threshold': self.AR_AMOUNT_THRESHOLD
        }
    
    def detect(self, scope: Dict) -> List[Dict[str, Any]]:
        """Run health detection."""
        signals = []
        artifact_svc = get_artifact_service()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            today = datetime.now().date()
            
            # Detect declining client health
            cursor.execute("""
                SELECT id, name, tier, relationship_health, relationship_trend,
                       relationship_last_interaction, financial_ar_overdue
                FROM clients
                WHERE relationship_trend = 'declining'
                OR relationship_health IN ('poor', 'critical')
            """)
            
            for row in cursor.fetchall():
                client_id, name, tier, health, trend, last_interaction, ar_overdue = row
                
                severity = 'critical' if health == 'critical' else 'high' if health == 'poor' else 'medium'
                
                # Create evidence excerpts for this client
                evidence_excerpts = []
                
                # Create a synthetic artifact for client health data
                art_result = artifact_svc.create_artifact(
                    source='system',
                    source_id=f'client_health_{client_id}_{today.isoformat()}',
                    artifact_type='client_update',
                    occurred_at=datetime.now().isoformat(),
                    payload={
                        'client_id': client_id,
                        'name': name,
                        'health': health,
                        'trend': trend,
                        'ar_overdue': ar_overdue
                    }
                )
                artifact_id = art_result['artifact_id']
                
                # Create proof excerpts
                exc1 = artifact_svc.create_excerpt(
                    artifact_id, f"Client '{name}' health: {health}, trend: {trend}",
                    anchor_type='computed', anchor_start='health', anchor_end='health'
                )
                evidence_excerpts.append(exc1['excerpt_id'])
                
                exc2 = artifact_svc.create_excerpt(
                    artifact_id, f"Tier: {tier or 'Unclassified'}",
                    anchor_type='computed', anchor_start='tier', anchor_end='tier'
                )
                evidence_excerpts.append(exc2['excerpt_id'])
                
                if ar_overdue and ar_overdue > 0:
                    exc3 = artifact_svc.create_excerpt(
                        artifact_id, f"AR Overdue: ${ar_overdue:,.0f}",
                        anchor_type='computed', anchor_start='ar', anchor_end='ar'
                    )
                    evidence_excerpts.append(exc3['excerpt_id'])
                
                if last_interaction:
                    exc4 = artifact_svc.create_excerpt(
                        artifact_id, f"Last interaction: {last_interaction[:10] if last_interaction else 'Unknown'}",
                        anchor_type='computed', anchor_start='interaction', anchor_end='interaction'
                    )
                    evidence_excerpts.append(exc4['excerpt_id'])
                
                signal = self.create_signal(
                    signal_type='client_health_declining',
                    entity_ref_type='client',
                    entity_ref_id=client_id,
                    value={
                        'client_name': name,
                        'tier': tier,
                        'current_health': health,
                        'trend': trend,
                        'last_interaction': last_interaction,
                        'ar_overdue': ar_overdue
                    },
                    severity=severity,
                    interpretation_confidence=0.85,
                    linkage_confidence_floor=0.95,
                    evidence_excerpt_ids=evidence_excerpts,
                    evidence_artifact_ids=[artifact_id]
                )
                signals.append(signal)
            
            # Detect communication gaps
            gap_cutoff = (today - timedelta(days=self.COMMUNICATION_GAP_DAYS)).isoformat()
            
            cursor.execute("""
                SELECT id, name, tier, relationship_last_interaction
                FROM clients
                WHERE tier IN ('A', 'B')
                AND (relationship_last_interaction IS NULL 
                     OR relationship_last_interaction < ?)
            """, (gap_cutoff,))
            
            for row in cursor.fetchall():
                client_id, name, tier, last_interaction = row
                
                if last_interaction:
                    days_since = (today - datetime.fromisoformat(last_interaction[:10]).date()).days
                else:
                    days_since = 999
                
                severity = 'high' if tier == 'A' else 'medium'
                
                signal = self.create_signal(
                    signal_type='communication_gap',
                    entity_ref_type='client',
                    entity_ref_id=client_id,
                    value={
                        'client_name': name,
                        'tier': tier,
                        'days_since_contact': days_since,
                        'last_interaction': last_interaction,
                        'threshold_days': self.COMMUNICATION_GAP_DAYS
                    },
                    severity=severity,
                    interpretation_confidence=0.9,
                    linkage_confidence_floor=0.95
                )
                signals.append(signal)
            
            # Detect AR aging risks
            cursor.execute("""
                SELECT id, name, tier, financial_ar_overdue, financial_ar_aging_bucket,
                       financial_last_invoice_date, financial_last_payment_date
                FROM clients
                WHERE financial_ar_overdue > ?
            """, (self.AR_AMOUNT_THRESHOLD,))
            
            for row in cursor.fetchall():
                client_id, name, tier, ar_overdue, aging_bucket, last_invoice, last_payment = row
                
                severity = 'critical' if ar_overdue > 50000 else 'high' if ar_overdue > 20000 else 'medium'
                
                signal = self.create_signal(
                    signal_type='ar_aging_risk',
                    entity_ref_type='client',
                    entity_ref_id=client_id,
                    value={
                        'client_name': name,
                        'tier': tier,
                        'ar_overdue': ar_overdue,
                        'aging_bucket': aging_bucket,
                        'last_invoice': last_invoice,
                        'last_payment': last_payment
                    },
                    severity=severity,
                    interpretation_confidence=0.95,
                    linkage_confidence_floor=0.95
                )
                signals.append(signal)
            
            # Detect at-risk projects
            cursor.execute("""
                SELECT p.id, p.name, p.client_id, c.name as client_name,
                       p.health, p.status, p.target_end_date
                FROM projects p
                LEFT JOIN clients c ON p.client_id = c.id
                WHERE p.health IN ('at_risk', 'off_track')
                AND p.status = 'active'
            """)
            
            for row in cursor.fetchall():
                project_id, name, client_id, client_name, health, status, target_end = row
                
                severity = 'high' if health == 'off_track' else 'medium'
                
                signal = self.create_signal(
                    signal_type='project_health_at_risk',
                    entity_ref_type='project',
                    entity_ref_id=project_id,
                    value={
                        'project_name': name,
                        'client_id': client_id,
                        'client_name': client_name,
                        'health': health,
                        'target_end_date': target_end
                    },
                    severity=severity,
                    interpretation_confidence=0.85,
                    linkage_confidence_floor=0.9
                )
                signals.append(signal)
            
            return signals
            
        finally:
            conn.close()
