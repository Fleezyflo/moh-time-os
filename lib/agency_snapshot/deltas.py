"""
Delta Detection - Track changes between snapshots.

Per Page 0 §4 Zone B2: "Since last refresh" delta strip (max 5).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sqlite3


class DeltaTracker:
    """
    Tracks changes between snapshots.
    
    Detects:
    - Projects turning Red/Yellow
    - AR bucket shifts
    - Capacity gap changes
    - Client health drift
    - New commitment breaches
    """
    
    SNAPSHOT_HISTORY_PATH = Path(__file__).parent.parent.parent / "output" / "snapshot_history"
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path(__file__).parent.parent.parent / "data" / "state.db"
        self.SNAPSHOT_HISTORY_PATH.mkdir(parents=True, exist_ok=True)
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _query_all(self, sql: str, params: tuple = ()) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    
    def get_previous_snapshot(self) -> Optional[Dict]:
        """Load the most recent previous snapshot."""
        history_files = sorted(self.SNAPSHOT_HISTORY_PATH.glob("snapshot_*.json"), reverse=True)
        
        # Skip the most recent (current), get the one before
        if len(history_files) >= 2:
            try:
                with open(history_files[1]) as f:
                    return json.load(f)
            except:
                pass
        
        return None
    
    def save_snapshot_to_history(self, snapshot: Dict):
        """Save current snapshot to history for future comparison."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.SNAPSHOT_HISTORY_PATH / f"snapshot_{timestamp}.json"
        
        with open(path, 'w') as f:
            json.dump(snapshot, f)
        
        # Keep only last 10 snapshots
        history_files = sorted(self.SNAPSHOT_HISTORY_PATH.glob("snapshot_*.json"), reverse=True)
        for old_file in history_files[10:]:
            old_file.unlink()
    
    def compute_deltas(self, current: Dict, previous: Optional[Dict] = None) -> List[Dict]:
        """
        Compute deltas between current and previous snapshot.
        
        Returns list of delta dicts with: text, impact, entity_refs
        """
        if previous is None:
            previous = self.get_previous_snapshot()
        
        if previous is None:
            # No previous snapshot - check for significant current state
            return self._compute_initial_deltas(current)
        
        deltas = []
        
        # Compare project statuses
        deltas.extend(self._compare_projects(current, previous))
        
        # Compare AR buckets
        deltas.extend(self._compare_ar(current, previous))
        
        # Compare capacity
        deltas.extend(self._compare_capacity(current, previous))
        
        # Compare client health
        deltas.extend(self._compare_clients(current, previous))
        
        # Check for new commitment breaches
        deltas.extend(self._check_new_commitments(current, previous))
        
        # Sort by impact descending
        deltas.sort(key=lambda d: -d.get('impact', 0))
        
        return deltas[:5]  # Max 5
    
    def _compute_initial_deltas(self, current: Dict) -> List[Dict]:
        """Compute deltas when no previous snapshot exists."""
        deltas = []
        
        tiles = current.get('tiles', {})
        
        # Report current state as initial deltas
        delivery = tiles.get('delivery', {})
        if delivery.get('red_count', 0) > 0:
            deltas.append({
                'text': f"{delivery['red_count']} projects currently Red",
                'impact': 0.8,
                'entity_refs': [],
            })
        
        clients = tiles.get('clients', {})
        if clients.get('at_risk_count', 0) > 0:
            deltas.append({
                'text': f"{clients['at_risk_count']} clients at risk",
                'impact': 0.7,
                'entity_refs': [],
            })
        
        cash = tiles.get('cash', {})
        if cash.get('severe_ar', 0) > 0:
            deltas.append({
                'text': f"AED {cash['severe_ar']:,.0f} in severe AR (61+ days)",
                'impact': 0.6,
                'entity_refs': [],
            })
        
        return deltas
    
    def _compare_projects(self, current: Dict, previous: Dict) -> List[Dict]:
        """Compare project statuses."""
        deltas = []
        
        curr_projects = {p['project_id']: p for p in current.get('heatstrip_projects', [])}
        prev_projects = {p['project_id']: p for p in previous.get('heatstrip_projects', [])}
        
        # Find projects that turned Red
        new_red = []
        new_yellow = []
        
        for pid, curr in curr_projects.items():
            prev = prev_projects.get(pid)
            if prev:
                if curr['status'] == 'RED' and prev['status'] != 'RED':
                    new_red.append(curr['name'])
                elif curr['status'] == 'YELLOW' and prev['status'] == 'GREEN':
                    new_yellow.append(curr['name'])
        
        if new_red:
            deltas.append({
                'text': f"+{len(new_red)} project(s) turned Red: {', '.join(new_red[:2])}{'...' if len(new_red) > 2 else ''}",
                'impact': 0.9,
                'entity_refs': new_red,
            })
        
        if new_yellow:
            deltas.append({
                'text': f"+{len(new_yellow)} project(s) turned Yellow",
                'impact': 0.6,
                'entity_refs': new_yellow,
            })
        
        return deltas
    
    def _compare_ar(self, current: Dict, previous: Dict) -> List[Dict]:
        """Compare AR bucket changes."""
        deltas = []
        
        curr_cash = current.get('tiles', {}).get('cash', {})
        prev_cash = previous.get('tiles', {}).get('cash', {})
        
        curr_severe = curr_cash.get('severe_ar', 0)
        prev_severe = prev_cash.get('severe_ar', 0)
        
        if curr_severe > prev_severe:
            diff = curr_severe - prev_severe
            deltas.append({
                'text': f"+AED {diff:,.0f} moved into severe AR (61+ days)",
                'impact': 0.7,
                'entity_refs': [],
            })
        
        return deltas
    
    def _compare_capacity(self, current: Dict, previous: Dict) -> List[Dict]:
        """Compare capacity constraints."""
        deltas = []
        
        curr_constraints = current.get('constraints', [])
        prev_constraints = previous.get('constraints', [])
        
        # Build lookup
        prev_gaps = {c['id']: c.get('capacity_gap_hours', 0) for c in prev_constraints}
        
        for curr in curr_constraints:
            cid = curr['id']
            curr_gap = curr.get('capacity_gap_hours', 0)
            prev_gap = prev_gaps.get(cid, 0)
            
            if curr_gap > prev_gap + 4:  # Significant increase
                diff = curr_gap - prev_gap
                deltas.append({
                    'text': f"Capacity gap increased by {diff:.0f}h ({curr['name']})",
                    'impact': 0.5,
                    'entity_refs': [cid],
                })
                break  # Only report biggest
        
        return deltas
    
    def _compare_clients(self, current: Dict, previous: Dict) -> List[Dict]:
        """Compare client health."""
        deltas = []
        
        curr_count = current.get('tiles', {}).get('clients', {}).get('at_risk_count', 0)
        prev_count = previous.get('tiles', {}).get('clients', {}).get('at_risk_count', 0)
        
        if curr_count > prev_count:
            deltas.append({
                'text': f"+{curr_count - prev_count} client(s) now at risk",
                'impact': 0.6,
                'entity_refs': [],
            })
        
        return deltas
    
    def _check_new_commitments(self, current: Dict, previous: Dict) -> List[Dict]:
        """Check for new commitment breaches."""
        deltas = []
        
        # Query for recent commitment breaches
        breaches = self._query_all("""
            SELECT COUNT(*) as count FROM commitments
            WHERE status NOT IN ('fulfilled', 'closed') 
            AND deadline IS NOT NULL
            AND deadline < datetime('now')
            AND created_at >= datetime('now', '-1 hour')
        """)
        
        if breaches and breaches[0].get('count', 0) > 0:
            count = breaches[0]['count']
            deltas.append({
                'text': f"{count} new commitment breach(es) detected",
                'impact': 0.65,
                'entity_refs': [],
            })
        
        return deltas
