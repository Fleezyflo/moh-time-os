"""
Time OS V4 - Proposal Service

Proposals are the unit of executive attention.
They bundle related signals into actionable briefings with proof.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os

from .signal_service import get_signal_service

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')


class ProposalService:
    """
    Service for managing proposals - bundled signals for executive review.
    
    Proposals are surfaced only when they have sufficient evidence (≥3 excerpts).
    They can be tagged to create monitored Issues.
    """
    
    # Minimum evidence required to surface a proposal
    MIN_PROOF_EXCERPTS = 3
    MIN_SIGNALS = 1
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.signal_svc = get_signal_service()
        self._ensure_tables()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _generate_id(self, prefix: str = 'prop') -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
    
    def _ensure_tables(self):
        """Ensure proposal tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proposals_v4 (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_type TEXT NOT NULL,  -- risk, opportunity, request, decision_needed, anomaly, compliance
                    primary_ref_type TEXT NOT NULL,
                    primary_ref_id TEXT NOT NULL,
                    scope_refs TEXT NOT NULL,  -- JSON array of {type, id}
                    headline TEXT NOT NULL,
                    summary TEXT,
                    impact TEXT NOT NULL,  -- JSON: time/cash/reputation + deadlines
                    top_hypotheses TEXT NOT NULL,  -- JSON array
                    signal_ids TEXT NOT NULL,  -- JSON array
                    proof_excerpt_ids TEXT NOT NULL,  -- JSON array
                    missing_confirmations TEXT,  -- JSON array
                    score REAL NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    trend TEXT NOT NULL DEFAULT 'flat',  -- worsening, improving, flat
                    supersedes_proposal_id TEXT,
                    ui_exposure_level TEXT DEFAULT 'none',  -- none, briefable, surfaced
                    status TEXT NOT NULL DEFAULT 'open',  -- open, snoozed, dismissed, accepted
                    snoozed_until TEXT,
                    dismissed_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_v4_status ON proposals_v4(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_v4_type ON proposals_v4(proposal_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_v4_score ON proposals_v4(score DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_v4_primary ON proposals_v4(primary_ref_type, primary_ref_id)")
            
            conn.commit()
        finally:
            conn.close()
    
    # ===========================================
    # Proposal Generation
    # ===========================================
    
    def generate_proposals_from_signals(self) -> Dict[str, Any]:
        """
        Generate proposals by bundling related active signals.
        
        Bundling strategy:
        1. Group signals by entity (client, project, etc.)
        2. Within entity, group by category (risk, health, deadline)
        3. Create/update proposals with combined evidence
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        stats = {'created': 0, 'updated': 0, 'skipped': 0}
        
        try:
            # Get active signals grouped by entity
            cursor.execute("""
                SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                       s.value, s.severity, s.interpretation_confidence,
                       s.evidence_excerpt_ids, s.evidence_artifact_ids,
                       d.category, d.priority_weight
                FROM signals s
                LEFT JOIN signal_definitions d ON s.signal_type = d.signal_type
                WHERE s.status = 'active'
                ORDER BY s.entity_ref_type, s.entity_ref_id, d.category
            """)
            
            # Group signals by entity + category
            groups = {}
            for row in cursor.fetchall():
                (signal_id, signal_type, entity_type, entity_id, value_json,
                 severity, confidence, excerpt_ids_json, artifact_ids_json,
                 category, priority_weight) = row
                
                key = (entity_type, entity_id, category or 'general')
                if key not in groups:
                    groups[key] = []
                
                groups[key].append({
                    'signal_id': signal_id,
                    'signal_type': signal_type,
                    'value': json.loads(value_json),
                    'severity': severity,
                    'confidence': confidence,
                    'excerpt_ids': json.loads(excerpt_ids_json or '[]'),
                    'artifact_ids': json.loads(artifact_ids_json or '[]'),
                    'category': category,
                    'priority_weight': priority_weight or 1.0
                })
            
            # Create/update proposals for each group
            for (entity_type, entity_id, category), signals in groups.items():
                if len(signals) < self.MIN_SIGNALS:
                    stats['skipped'] += 1
                    continue
                
                # Compute proposal attributes
                all_excerpts = []
                all_artifacts = []
                all_signal_ids = []
                max_severity = 'low'
                severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
                total_weight = 0
                
                for sig in signals:
                    all_signal_ids.append(sig['signal_id'])
                    # Get excerpt_ids from signal value or direct field
                    sig_excerpts = sig.get('excerpt_ids', [])
                    if not sig_excerpts:
                        # Try to get from database
                        cursor.execute(
                            "SELECT evidence_excerpt_ids FROM signals WHERE signal_id = ?",
                            (sig['signal_id'],)
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            sig_excerpts = json.loads(row[0])
                    all_excerpts.extend(sig_excerpts)
                    
                    sig_artifacts = sig.get('artifact_ids', [])
                    if not sig_artifacts:
                        cursor.execute(
                            "SELECT evidence_artifact_ids FROM signals WHERE signal_id = ?",
                            (sig['signal_id'],)
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            sig_artifacts = json.loads(row[0])
                    all_artifacts.extend(sig_artifacts)
                    
                    if severity_order.get(sig['severity'], 0) > severity_order.get(max_severity, 0):
                        max_severity = sig['severity']
                    total_weight += sig['priority_weight']
                
                # Dedupe
                all_excerpts = list(set(all_excerpts))
                all_artifacts = list(set(all_artifacts))
                
                # Generate headline
                headline = self._generate_headline(entity_type, entity_id, category, signals)
                
                # Compute score
                score = self._compute_score(signals, max_severity, total_weight)
                
                # Map category to proposal type
                type_map = {
                    'risk': 'risk',
                    'deadline': 'risk',
                    'health': 'risk',
                    'commitment': 'request',
                    'protocol': 'compliance',
                    'opportunity': 'opportunity'
                }
                proposal_type = type_map.get(category, 'anomaly')
                
                # Check if proposal already exists for this entity+category
                cursor.execute("""
                    SELECT proposal_id, occurrence_count, score
                    FROM proposals_v4
                    WHERE primary_ref_type = ? AND primary_ref_id = ?
                    AND proposal_type = ? AND status = 'open'
                """, (entity_type, entity_id, proposal_type))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing proposal
                    old_id, old_count, old_score = existing
                    trend = 'worsening' if score > old_score else 'improving' if score < old_score else 'flat'
                    
                    # Recalculate exposure level
                    if len(all_excerpts) >= self.MIN_PROOF_EXCERPTS:
                        exposure = 'surfaced'
                    elif len(all_excerpts) >= 1:
                        exposure = 'briefable'
                    else:
                        exposure = 'none'
                    
                    cursor.execute("""
                        UPDATE proposals_v4
                        SET signal_ids = ?, proof_excerpt_ids = ?, score = ?,
                            occurrence_count = ?, trend = ?, last_seen_at = datetime('now'),
                            updated_at = datetime('now'), headline = ?, ui_exposure_level = ?
                        WHERE proposal_id = ?
                    """, (
                        json.dumps(all_signal_ids), json.dumps(all_excerpts),
                        score, old_count + 1, trend, headline, exposure, old_id
                    ))
                    stats['updated'] += 1
                else:
                    # Create new proposal
                    proposal_id = self._generate_id('prop')
                    
                    # Determine exposure level and status based on proof density
                    # SPEC RULE: Proposals without ≥3 proofs get status='insufficient_evidence'
                    if len(all_excerpts) >= self.MIN_PROOF_EXCERPTS:
                        exposure = 'surfaced'  # Meets full proof requirements
                        initial_status = 'open'
                    elif len(all_excerpts) >= 1:
                        exposure = 'briefable'  # Has some evidence
                        initial_status = 'insufficient_evidence'
                    else:
                        exposure = 'none'  # No evidence yet
                        initial_status = 'insufficient_evidence'
                    
                    impact = {
                        'severity': max_severity,
                        'signal_count': len(signals),
                        'entity_type': entity_type
                    }
                    
                    hypotheses = [
                        {
                            'signal_type': sig['signal_type'],
                            'summary': self._signal_to_hypothesis(sig)
                        }
                        for sig in signals[:5]  # Top 5 signals as hypotheses
                    ]
                    
                    cursor.execute("""
                        INSERT INTO proposals_v4
                        (proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                         scope_refs, headline, impact, top_hypotheses, signal_ids,
                         proof_excerpt_ids, score, first_seen_at, last_seen_at,
                         ui_exposure_level, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                                datetime('now'), ?, ?, datetime('now'), datetime('now'))
                    """, (
                        proposal_id, proposal_type, entity_type, entity_id,
                        json.dumps([{'type': entity_type, 'id': entity_id}]),
                        headline, json.dumps(impact), json.dumps(hypotheses),
                        json.dumps(all_signal_ids), json.dumps(all_excerpts),
                        score, exposure, initial_status
                    ))
                    stats['created'] += 1
            
            conn.commit()
            return stats
            
        finally:
            conn.close()
    
    def _generate_headline(self, entity_type: str, entity_id: str, category: str, signals: List) -> str:
        """Generate a headline for a proposal."""
        # Get entity name
        conn = self._get_conn()
        cursor = conn.cursor()
        
        entity_name = entity_id
        try:
            if entity_type == 'client':
                cursor.execute("SELECT name FROM clients WHERE id = ?", (entity_id,))
            elif entity_type == 'project':
                cursor.execute("SELECT name FROM projects WHERE id = ?", (entity_id,))
            
            row = cursor.fetchone()
            if row:
                entity_name = row[0]
        finally:
            conn.close()
        
        # Build headline based on category
        signal_types = [s['signal_type'] for s in signals]
        
        if 'deadline_overdue' in signal_types:
            return f"⚠️ {entity_name}: Overdue deadlines require attention"
        elif 'deadline_approaching' in signal_types:
            return f"📅 {entity_name}: Deadlines approaching"
        elif 'client_health_declining' in signal_types:
            return f"🔻 {entity_name}: Relationship health declining"
        elif 'ar_aging_risk' in signal_types:
            return f"💰 {entity_name}: AR aging concerns"
        elif 'communication_gap' in signal_types:
            return f"📭 {entity_name}: Communication gap detected"
        elif 'commitment' in category:
            return f"🤝 {entity_name}: Commitment tracking required"
        elif category == 'protocol':
            return f"⚡ {entity_name}: Process violations detected"
        else:
            return f"📋 {entity_name}: {len(signals)} signal(s) require review"
    
    def _signal_to_hypothesis(self, sig: Dict) -> str:
        """Convert a signal to a hypothesis statement."""
        value = sig.get('value', {})
        signal_type = sig.get('signal_type', '')
        
        if signal_type == 'deadline_overdue':
            return f"Task '{value.get('title', 'Unknown')}' is {value.get('days_overdue', '?')} days overdue"
        elif signal_type == 'deadline_approaching':
            return f"Task '{value.get('title', 'Unknown')}' due in {value.get('days_until', '?')} days"
        elif signal_type == 'ar_aging_risk':
            return f"${value.get('ar_overdue', 0):,.0f} overdue in {value.get('aging_bucket', 'unknown')} bucket"
        elif signal_type == 'communication_gap':
            return f"No contact in {value.get('days_since_contact', '?')} days"
        elif signal_type == 'client_health_declining':
            return f"Health: {value.get('current_health', '?')}, Trend: {value.get('trend', '?')}"
        else:
            return f"{signal_type}: {str(value)[:100]}"
    
    def _compute_score(self, signals: List, max_severity: str, total_weight: float) -> float:
        """Compute proposal priority score."""
        severity_scores = {'low': 1, 'medium': 2, 'high': 4, 'critical': 8}
        base = severity_scores.get(max_severity, 1)
        
        # Factor in signal count and weights
        signal_factor = min(len(signals) * 0.5, 3)  # Cap at 3x
        weight_factor = min(total_weight / len(signals), 2)  # Cap at 2x
        
        return base * signal_factor * weight_factor
    
    # ===========================================
    # Proposal Retrieval
    # ===========================================
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get a proposal by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       scope_refs, headline, summary, impact, top_hypotheses,
                       signal_ids, proof_excerpt_ids, score, first_seen_at,
                       last_seen_at, occurrence_count, trend, status, ui_exposure_level
                FROM proposals_v4 WHERE proposal_id = ?
            """, (proposal_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'proposal_id': row[0],
                'proposal_type': row[1],
                'primary_ref_type': row[2],
                'primary_ref_id': row[3],
                'scope_refs': json.loads(row[4]),
                'headline': row[5],
                'summary': row[6],
                'impact': json.loads(row[7]),
                'top_hypotheses': json.loads(row[8]),
                'signal_ids': json.loads(row[9]),
                'proof_excerpt_ids': json.loads(row[10]),
                'score': row[11],
                'first_seen_at': row[12],
                'last_seen_at': row[13],
                'occurrence_count': row[14],
                'trend': row[15],
                'status': row[16],
                'ui_exposure_level': row[17]
            }
        finally:
            conn.close()
    
    def get_surfaceable_proposals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get proposals that meet surfacing criteria."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       headline, impact, score, occurrence_count, trend, status,
                       ui_exposure_level, first_seen_at, last_seen_at
                FROM proposals_v4
                WHERE status = 'open'
                AND ui_exposure_level IN ('briefable', 'surfaced')
                ORDER BY score DESC, last_seen_at DESC
                LIMIT ?
            """, (limit,))
            
            return [{
                'proposal_id': row[0],
                'proposal_type': row[1],
                'primary_ref_type': row[2],
                'primary_ref_id': row[3],
                'headline': row[4],
                'impact': json.loads(row[5]),
                'score': row[6],
                'occurrence_count': row[7],
                'trend': row[8],
                'status': row[9],
                'ui_exposure_level': row[10],
                'first_seen_at': row[11],
                'last_seen_at': row[12]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_all_open_proposals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all open proposals (including those not yet surfaceable)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                       headline, impact, score, occurrence_count, trend, status,
                       ui_exposure_level
                FROM proposals_v4
                WHERE status = 'open'
                ORDER BY score DESC
                LIMIT ?
            """, (limit,))
            
            return [{
                'proposal_id': row[0],
                'proposal_type': row[1],
                'primary_ref_type': row[2],
                'primary_ref_id': row[3],
                'headline': row[4],
                'impact': json.loads(row[5]),
                'score': row[6],
                'occurrence_count': row[7],
                'trend': row[8],
                'status': row[9],
                'ui_exposure_level': row[10]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ===========================================
    # Proposal Actions
    # ===========================================
    
    def snooze_proposal(self, proposal_id: str, until: str) -> Dict[str, Any]:
        """Snooze a proposal until a specified time."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE proposals_v4
                SET status = 'snoozed', snoozed_until = ?, updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """, (until, proposal_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Proposal not found or not open'}
            
            conn.commit()
            return {'status': 'snoozed', 'proposal_id': proposal_id, 'until': until}
        finally:
            conn.close()
    
    def dismiss_proposal(self, proposal_id: str, reason: str) -> Dict[str, Any]:
        """Dismiss a proposal."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE proposals_v4
                SET status = 'dismissed', dismissed_reason = ?, updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """, (reason, proposal_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Proposal not found or not open'}
            
            conn.commit()
            return {'status': 'dismissed', 'proposal_id': proposal_id}
        finally:
            conn.close()
    
    def accept_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Accept a proposal (marks it for Issue creation)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE proposals_v4
                SET status = 'accepted', updated_at = datetime('now')
                WHERE proposal_id = ? AND status = 'open'
            """, (proposal_id,))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Proposal not found or not open'}
            
            conn.commit()
            return {'status': 'accepted', 'proposal_id': proposal_id}
        finally:
            conn.close()
    
    # ===========================================
    # Statistics
    # ===========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proposal statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            cursor.execute("SELECT status, COUNT(*) FROM proposals_v4 GROUP BY status")
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT proposal_type, COUNT(*) FROM proposals_v4
                WHERE status = 'open'
                GROUP BY proposal_type
            """)
            stats['open_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT ui_exposure_level, COUNT(*) FROM proposals_v4
                WHERE status = 'open'
                GROUP BY ui_exposure_level
            """)
            stats['open_by_exposure'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT AVG(score), MAX(score), MIN(score) FROM proposals_v4
                WHERE status = 'open'
            """)
            row = cursor.fetchone()
            stats['score_stats'] = {
                'avg': row[0],
                'max': row[1],
                'min': row[2]
            }
            
            return stats
        finally:
            conn.close()


# Singleton
_proposal_service = None

def get_proposal_service() -> ProposalService:
    global _proposal_service
    if _proposal_service is None:
        _proposal_service = ProposalService()
    return _proposal_service
