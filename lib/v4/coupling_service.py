"""
Time OS V4 - Coupling Service (Intersection Engine)

Couplings identify non-obvious connections between entities.
They show "why" entities are related via shared signals/evidence.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')


class CouplingService:
    """
    Service for discovering and managing entity couplings.
    
    Couplings reveal intersections:
    - Which clients share the same risks?
    - Which projects are entangled via shared people/deadlines?
    - What issues cut across multiple entities?
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_tables()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _generate_id(self, prefix: str = 'cpl') -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
    
    def _ensure_tables(self):
        """Ensure coupling tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS couplings (
                    coupling_id TEXT PRIMARY KEY,
                    anchor_ref_type TEXT NOT NULL,  -- issue, proposal, signal
                    anchor_ref_id TEXT NOT NULL,
                    entity_refs TEXT NOT NULL,  -- JSON array of {type, id}
                    coupling_type TEXT NOT NULL,  -- shared_signals, shared_people, shared_timeline, shared_risk
                    strength REAL NOT NULL CHECK (strength >= 0 AND strength <= 1),
                    why TEXT NOT NULL,  -- JSON: signal_ids + link evidence
                    investigation_path TEXT NOT NULL,  -- JSON: ordered entity refs
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_couplings_anchor ON couplings(anchor_ref_type, anchor_ref_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_couplings_type ON couplings(coupling_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_couplings_strength ON couplings(strength DESC)")
            
            conn.commit()
        finally:
            conn.close()
    
    # ===========================================
    # Coupling Discovery
    # ===========================================
    
    def discover_couplings(self) -> Dict[str, Any]:
        """
        Discover couplings between entities based on shared characteristics.
        
        Coupling types:
        - shared_signals: Entities with same signal types
        - shared_people: Entities with same people involved
        - shared_timeline: Entities with overlapping deadlines
        - shared_risk: Entities with related risk signals
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        stats = {'created': 0, 'types': {}}
        
        try:
            # Find entities sharing same signal types
            cursor.execute("""
                SELECT s1.signal_type, s1.entity_ref_type, s1.entity_ref_id,
                       s2.entity_ref_type, s2.entity_ref_id, COUNT(*) as shared_count
                FROM signals s1
                JOIN signals s2 ON s1.signal_type = s2.signal_type
                    AND (s1.entity_ref_type != s2.entity_ref_type 
                         OR s1.entity_ref_id != s2.entity_ref_id)
                WHERE s1.status = 'active' AND s2.status = 'active'
                AND s1.entity_ref_id < s2.entity_ref_id  -- avoid duplicates
                GROUP BY s1.signal_type, s1.entity_ref_type, s1.entity_ref_id,
                         s2.entity_ref_type, s2.entity_ref_id
                HAVING COUNT(*) >= 1
                LIMIT 100
            """)
            
            for row in cursor.fetchall():
                signal_type, type1, id1, type2, id2, count = row
                
                coupling_id = self._generate_id('cpl')
                strength = min(count * 0.2, 1.0)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO couplings
                    (coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                     coupling_type, strength, why, investigation_path, confidence,
                     created_at, updated_at)
                    VALUES (?, 'signal_type', ?, ?, 'shared_signals', ?, ?, ?, ?,
                            datetime('now'), datetime('now'))
                """, (
                    coupling_id, signal_type,
                    json.dumps([{'type': type1, 'id': id1}, {'type': type2, 'id': id2}]),
                    strength,
                    json.dumps({'signal_type': signal_type, 'shared_count': count}),
                    json.dumps([type1, id1, type2, id2]),
                    0.8
                ))
                stats['created'] += 1
                stats['types']['shared_signals'] = stats['types'].get('shared_signals', 0) + 1
            
            # Find clients with multiple shared risk categories
            cursor.execute("""
                SELECT s.entity_ref_id, GROUP_CONCAT(DISTINCT d.category) as categories,
                       COUNT(DISTINCT s.signal_type) as signal_count
                FROM signals s
                JOIN signal_definitions d ON s.signal_type = d.signal_type
                WHERE s.entity_ref_type = 'client' AND s.status = 'active'
                AND d.category IN ('risk', 'health', 'deadline')
                GROUP BY s.entity_ref_id
                HAVING COUNT(DISTINCT d.category) >= 2
            """)
            
            high_risk_clients = []
            for row in cursor.fetchall():
                client_id, categories, signal_count = row
                high_risk_clients.append({
                    'id': client_id,
                    'categories': categories,
                    'signal_count': signal_count
                })
            
            # Create couplings for high-risk client clusters
            if len(high_risk_clients) >= 2:
                coupling_id = self._generate_id('cpl')
                cursor.execute("""
                    INSERT INTO couplings
                    (coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                     coupling_type, strength, why, investigation_path, confidence,
                     created_at, updated_at)
                    VALUES (?, 'risk_cluster', 'multi_category', ?, 'shared_risk', ?, ?, ?, ?,
                            datetime('now'), datetime('now'))
                """, (
                    coupling_id,
                    json.dumps([{'type': 'client', 'id': c['id']} for c in high_risk_clients[:10]]),
                    0.9,
                    json.dumps({'clients': high_risk_clients[:10]}),
                    json.dumps([c['id'] for c in high_risk_clients[:10]]),
                    0.85
                ))
                stats['created'] += 1
                stats['types']['shared_risk'] = 1
            
            conn.commit()
            return stats
            
        finally:
            conn.close()
    
    def get_couplings_for_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """Get all couplings involving an entity."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Search in entity_refs JSON
            cursor.execute("""
                SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                       coupling_type, strength, why, investigation_path, confidence
                FROM couplings
                WHERE entity_refs LIKE ?
                ORDER BY strength DESC
            """, (f'%"{entity_id}"%',))
            
            return [{
                'coupling_id': row[0],
                'anchor_ref_type': row[1],
                'anchor_ref_id': row[2],
                'entity_refs': json.loads(row[3]),
                'coupling_type': row[4],
                'strength': row[5],
                'why': json.loads(row[6]),
                'investigation_path': json.loads(row[7]),
                'confidence': row[8]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_strongest_couplings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the strongest couplings across the system."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                       coupling_type, strength, why, confidence
                FROM couplings
                ORDER BY strength DESC
                LIMIT ?
            """, (limit,))
            
            return [{
                'coupling_id': row[0],
                'anchor_ref_type': row[1],
                'anchor_ref_id': row[2],
                'entity_refs': json.loads(row[3]),
                'coupling_type': row[4],
                'strength': row[5],
                'why': json.loads(row[6]),
                'confidence': row[7]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get coupling statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM couplings")
            total = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT coupling_type, COUNT(*) FROM couplings
                GROUP BY coupling_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("SELECT AVG(strength), MAX(strength) FROM couplings")
            row = cursor.fetchone()
            
            return {
                'total_couplings': total,
                'by_type': by_type,
                'avg_strength': row[0],
                'max_strength': row[1]
            }
        finally:
            conn.close()


# Singleton
_coupling_service = None

def get_coupling_service() -> CouplingService:
    global _coupling_service
    if _coupling_service is None:
        _coupling_service = CouplingService()
    return _coupling_service
