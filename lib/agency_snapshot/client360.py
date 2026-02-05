"""
Client 360 Engine - Per Page 2 LOCKED SPEC (v1)

Computes:
- Client health scores (5 subscores)
- Portfolio ranking
- Client room data with all modules
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import sqlite3

from .scoring import Mode, Horizon, Confidence, clamp01


DB_PATH = Path(__file__).parent.parent.parent / "data" / "state.db"


class ClientStatus(str, Enum):
    """Client status per §6."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    PARTIAL = "PARTIAL"


class ClientTopDriver(str, Enum):
    """Top driver labels per spec."""
    DELIVERY = "Delivery"
    CASH = "Cash"
    COMMS = "Comms"
    COMMITMENTS = "Commitments"
    CAPACITY = "Capacity"
    UNKNOWN = "Unknown"


@dataclass
class ClientScores:
    """All client subscores per §5."""
    health: float = 0.0
    delivery: float = 100.0
    finance: float = 100.0
    responsiveness: float = 100.0
    commitments: float = 100.0
    capacity: float = 100.0
    
    # Metadata for unknown/degraded scores
    finance_unknown: bool = False
    capacity_unknown: bool = False


@dataclass
class ClientConfidence:
    """Client confidence per §5.2."""
    level: Confidence = Confidence.HIGH
    why_low: List[str] = field(default_factory=list)


@dataclass
class KeyDriver:
    """Key driver for Client Room."""
    title: str
    evidence: List[Dict[str, str]]  # [{"type": "task", "id": "..."}]
    primary_action: Dict


@dataclass
class DeliveryExposureProject:
    """Project in delivery exposure list."""
    project_id: str
    name: str
    status: str
    time_to_slip_hours: Optional[float]
    slip_risk_score: float
    top_driver: str
    confidence: str


@dataclass
class ARLine:
    """AR line item."""
    invoice_id: str
    amount: float
    days_overdue: int
    bucket: str


@dataclass
class CommsThread:
    """Comms thread item."""
    thread_id: str
    subject: str
    age_hours: float
    expected_response_by: Optional[str]
    sla_breach: bool
    risk: str


@dataclass
class CommitmentItem:
    """Commitment item."""
    commitment_id: str
    text: str
    deadline: Optional[str]
    status: str
    risk: str


@dataclass
class ClientPortfolioItem:
    """Client item for portfolio list."""
    client_id: str
    name: str
    tier: str
    status: ClientStatus
    health_score: float
    top_driver: ClientTopDriver
    trend: Optional[str]  # up/down/flat
    confidence: Confidence
    why_low: List[str]


@dataclass 
class ClientRoomData:
    """Complete client room data."""
    client_id: str
    header: Dict
    summary_sentence: str
    scores: ClientScores
    confidence: ClientConfidence
    key_drivers: List[KeyDriver]
    delivery_exposure: Dict
    cash_exposure: Dict
    comms: Dict
    commitments: Dict
    capacity: Dict
    recent_change: List[Dict]
    actions: List[Dict]


class Client360Engine:
    """
    Computes client health and generates Client 360 snapshot data.
    
    Per Page 2 spec:
    - HealthScore = weighted blend of 5 subscores
    - Weights depend on mode
    - Confidence based on coverage + gates
    """
    
    # Hard caps per spec §2
    MAX_PORTFOLIO = 30
    MAX_KEY_DRIVERS = 5
    MAX_PROJECTS = 7
    MAX_COMMITMENTS = 7
    MAX_COMMS_THREADS = 7
    MAX_AR_LINES = 5
    MAX_RECENT_CHANGE = 5
    MAX_ACTIONS = 7
    
    # Health weights per Page 5 §4.2 (locked - mode-independent)
    HEALTH_WEIGHTS = {
        "delivery": 0.35,
        "comms": 0.25,
        "cash": 0.25,
        "relationship": 0.15,
    }
    
    # Driver priority for ranking tie-breaks per §9.1
    DRIVER_PRIORITY = {
        Mode.OPS_HEAD: [
            ClientTopDriver.DELIVERY,
            ClientTopDriver.COMMITMENTS,
            ClientTopDriver.COMMS,
            ClientTopDriver.CAPACITY,
            ClientTopDriver.CASH,
        ],
        Mode.CO_FOUNDER: [
            ClientTopDriver.CASH,
            ClientTopDriver.COMMITMENTS,
            ClientTopDriver.DELIVERY,
            ClientTopDriver.COMMS,
            ClientTopDriver.CAPACITY,
        ],
        Mode.ARTIST: [
            ClientTopDriver.CAPACITY,
            ClientTopDriver.DELIVERY,
            ClientTopDriver.COMMITMENTS,
            ClientTopDriver.COMMS,
            ClientTopDriver.CASH,
        ],
    }
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        mode: Mode = Mode.OPS_HEAD,
        horizon: Horizon = Horizon.TODAY,
    ):
        self.db_path = db_path
        self.mode = mode
        self.horizon = horizon
        self.now = datetime.now()
        self.today = date.today()
        
        # Trust state (to be set externally)
        self.data_integrity = True
        self.client_coverage_pct = 100.0
        self.finance_ar_coverage_pct = 100.0
    
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
    
    def _query_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def _query_scalar(self, sql: str, params: tuple = ()) -> Any:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    
    def _compute_client_trend(self, client_id: str, current_health: float) -> Optional[float]:
        """
        Compute client health trend based on recent activity.
        Returns: float (-50 to +50) where positive = improving, negative = worsening
        None if insufficient data.
        """
        # Count positive signals (completed tasks, paid invoices)
        positive_signals = self._query_scalar("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM tasks 
                WHERE project_id IN (SELECT id FROM projects WHERE client_id = ?)
                AND status = 'completed' AND updated_at >= datetime('now', '-7 days')
                UNION ALL
                SELECT 1 FROM invoices
                WHERE client_id = ? AND status = 'paid' AND paid_date >= date('now', '-7 days')
            )
        """, (client_id, client_id)) or 0
        
        # Count negative signals (overdue tasks, broken commitments)
        negative_signals = self._query_scalar("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM tasks 
                WHERE project_id IN (SELECT id FROM projects WHERE client_id = ?)
                AND status = 'active' AND due_date < date('now') AND due_date >= date('now', '-7 days')
                UNION ALL
                SELECT 1 FROM commitments
                WHERE client_id = ? AND status = 'broken' AND updated_at >= datetime('now', '-7 days')
            )
        """, (client_id, client_id)) or 0
        
        if positive_signals == 0 and negative_signals == 0:
            return None  # No trend data
        
        # Calculate trend: positive signals improve, negative signals worsen
        trend = (positive_signals * 5) - (negative_signals * 10)
        
        # Clamp to -50..+50
        return max(-50.0, min(50.0, float(trend)))
    
    # =========================================================================
    # SCORING METHODS (per §5)
    # =========================================================================
    
    def compute_delivery_score(self, client_id: str) -> float:
        """
        Compute DeliveryScore per §5.3.
        
        Use tasks where client_link_status='linked' and client_id matches.
        Roll up project slip risks to client level.
        """
        # Get projects for this client with their slip risk components
        projects = self._query_all("""
            SELECT 
                p.id as project_id,
                p.name,
                p.deadline,
                COUNT(t.id) as total_tasks,
                COUNT(CASE WHEN t.status NOT IN ('done', 'completed') THEN 1 END) as open_tasks,
                COUNT(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('done', 'completed') THEN 1 END) as overdue_tasks,
                SUM(CASE WHEN t.status NOT IN ('done', 'completed') THEN COALESCE(t.duration_min, 60) ELSE 0 END) / 60.0 as open_hours
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id AND t.client_link_status = 'linked'
            WHERE p.client_id = ? AND p.is_internal = 0
            GROUP BY p.id
        """, (client_id,))
        
        if not projects:
            # Check if there are any linked tasks without projects
            tasks = self._query_one("""
                SELECT COUNT(*) as count FROM tasks 
                WHERE client_id = ? AND client_link_status = 'linked'
                AND status NOT IN ('done', 'completed')
            """, (client_id,))
            
            if not tasks or tasks['count'] == 0:
                return 100.0  # No delivery exposure
            
            # Treat as synthetic workstream
            task_data = self._query_one("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN due_date < date('now') THEN 1 END) as overdue
                FROM tasks
                WHERE client_id = ? AND client_link_status = 'linked'
                AND status NOT IN ('done', 'completed')
            """, (client_id,))
            
            if task_data['total'] == 0:
                return 100.0
            
            overdue_ratio = (task_data['overdue'] or 0) / task_data['total']
            return 100.0 * (1.0 - overdue_ratio * 0.7)
        
        # Compute weighted average of project delivery scores
        total_weight = 0
        weighted_sum = 0
        
        for proj in projects:
            # Compute project slip_risk_score per Delivery Command spec
            deadline_pressure = 0.0
            if proj.get('deadline'):
                try:
                    deadline = datetime.strptime(proj['deadline'], '%Y-%m-%d').date()
                    days_to = (deadline - self.today).days
                    deadline_pressure = clamp01(1 - (days_to / 14))
                except:
                    pass
            
            # Remaining work ratio
            total = proj.get('total_tasks') or 1
            open_t = proj.get('open_tasks') or 0
            remaining_work_ratio = open_t / max(1, total)
            
            # Blocking severity (overdue tasks as proxy)
            overdue = proj.get('overdue_tasks') or 0
            blocking_severity = clamp01(overdue / max(1, open_t)) if open_t > 0 else 0
            
            # Capacity gap (simplified - assume 40h/week available)
            hours_needed = proj.get('open_hours') or 0
            capacity_gap_ratio = clamp01((hours_needed - 40) / max(1, hours_needed)) if hours_needed > 40 else 0
            
            # Slip risk formula per Page 1 §6.3
            slip_risk = (
                0.35 * deadline_pressure +
                0.25 * remaining_work_ratio +
                0.25 * capacity_gap_ratio +
                0.15 * blocking_severity
            )
            
            # Project delivery score = 100 * (1 - slip_risk)
            proj_score = 100.0 * (1.0 - slip_risk)
            
            # Weight by open tasks (exposure)
            weight = max(1, open_t)
            weighted_sum += proj_score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 100.0
        
        return weighted_sum / total_weight
    
    def compute_cash_health(self, client_id: str) -> Tuple[Optional[float], bool]:
        """
        Compute CashHealth per Page 5 §4.2.2 (locked).
        
        Formula:
        - If no valid AR: CashHealth = 100
        - Else: CashHealth = 100*(1 - severe_pct) - 50*moderate_pct
        - Clamp 0..100
        
        Returns (score, is_unknown).
        """
        # Valid AR definition per spec: status IN ('sent','overdue') AND paid_date IS NULL
        # AND due_date IS NOT NULL AND client_id IS NOT NULL
        ar_data = self._query_one("""
            SELECT 
                SUM(amount) as total,
                SUM(CASE WHEN aging_bucket IN ('1-30', '31-60') THEN amount ELSE 0 END) as moderate_amt,
                SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe_amt
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
        """, (client_id,))
        
        if not ar_data or not ar_data.get('total') or ar_data['total'] == 0:
            # No valid AR outstanding = CashHealth 100
            # Check if client has any invoices at all (for unknown flag)
            has_invoices = self._query_scalar("""
                SELECT COUNT(*) FROM invoices WHERE client_id = ?
            """, (client_id,))
            
            if has_invoices == 0:
                # No finance data at all - return None with unknown flag
                return (None, True)
            
            return (100.0, False)
        
        total = ar_data['total']
        moderate_pct = (ar_data.get('moderate_amt') or 0) / total
        severe_pct = (ar_data.get('severe_amt') or 0) / total
        
        # Formula per §4.2.2: CashHealth = 100*(1 - severe_pct) - 50*moderate_pct
        score = 100.0 * (1.0 - severe_pct) - 50.0 * moderate_pct
        return (max(0.0, min(100.0, score)), False)
    
    def compute_comms_health(self, client_id: str) -> Optional[float]:
        """
        Compute CommsHealth per Page 5 §4.2.3 (locked).
        
        Formula:
        - Baseline 100
        - -15 per overdue thread (cap -60)
        - -20 per VIP overdue thread (cap additional -40)
        - -10 if avg_age_hours > 24
        - Clamp 0..100
        
        Returns score or None if no linked comms.
        """
        # Get comms threads for this client with response status
        comms = self._query_one("""
            SELECT 
                COUNT(DISTINCT COALESCE(thread_id, id)) as total_threads,
                COUNT(DISTINCT CASE 
                    WHEN COALESCE(expected_response_by, response_deadline) IS NOT NULL 
                    AND COALESCE(expected_response_by, response_deadline) < datetime('now')
                    THEN COALESCE(thread_id, id)
                END) as overdue_threads,
                COUNT(DISTINCT CASE 
                    WHEN COALESCE(expected_response_by, response_deadline) IS NOT NULL 
                    AND COALESCE(expected_response_by, response_deadline) < datetime('now')
                    AND COALESCE(is_vip, 0) = 1
                    THEN COALESCE(thread_id, id)
                END) as vip_overdue_threads,
                AVG(CASE 
                    WHEN COALESCE(expected_response_by, response_deadline) IS NOT NULL 
                    AND COALESCE(expected_response_by, response_deadline) < datetime('now')
                    THEN (julianday('now') - julianday(received_at)) * 24
                END) as avg_age_hours
            FROM communications
            WHERE client_id = ?
        """, (client_id,))
        
        if not comms or not comms.get('total_threads') or comms['total_threads'] == 0:
            return None  # No comms linked to client
        
        overdue = comms.get('overdue_threads') or 0
        vip_overdue = comms.get('vip_overdue_threads') or 0
        avg_age = comms.get('avg_age_hours') or 0
        
        score = 100.0
        
        # -15 per overdue thread (cap -60)
        score -= min(60, 15 * overdue)
        
        # -20 per VIP overdue thread (cap additional -40)
        score -= min(40, 20 * vip_overdue)
        
        # -10 if avg_age_hours > 24
        if avg_age > 24:
            score -= 10
        
        return max(0.0, min(100.0, score))
    
    def compute_relationship_health(self, client_id: str) -> Optional[float]:
        """
        Compute RelationshipHealth per Page 5 §4.2.4 (locked).
        
        Formula:
        - Start at 100
        - -30 if any "relationship risk" thread_type HIGH in last 7 days
        - -20 if client health trend is down for 2 consecutive snapshots (needs delta store)
        - -20 if commitment breach exists with this client (broken promise/request)
        - Clamp 0..100
        
        Returns score or None if insufficient signals.
        """
        score = 100.0
        has_any_signal = False
        
        # Check for relationship risk comms (negative tone, escalation) in last 7 days
        # Using sentiment field if available, or keywords
        relationship_risk = self._query_scalar("""
            SELECT COUNT(*) FROM communications
            WHERE client_id = ?
            AND received_at >= datetime('now', '-7 days')
            AND (
                LOWER(COALESCE(sentiment, '')) LIKE '%negative%'
                OR LOWER(COALESCE(subject, '') || ' ' || COALESCE(snippet, '')) LIKE '%escalat%'
                OR LOWER(COALESCE(subject, '') || ' ' || COALESCE(snippet, '')) LIKE '%disappoint%'
                OR LOWER(COALESCE(subject, '') || ' ' || COALESCE(snippet, '')) LIKE '%unhappy%'
                OR LOWER(COALESCE(subject, '') || ' ' || COALESCE(snippet, '')) LIKE '%complaint%'
                OR LOWER(COALESCE(subject, '') || ' ' || COALESCE(snippet, '')) LIKE '%concerned%'
            )
        """, (client_id,))
        
        if relationship_risk and relationship_risk > 0:
            score -= 30
            has_any_signal = True
        
        # Check for broken commitments
        broken_commitments = self._query_scalar("""
            SELECT COUNT(*) FROM commitments
            WHERE client_id = ? AND status = 'broken'
        """, (client_id,))
        
        if broken_commitments and broken_commitments > 0:
            score -= 20
            has_any_signal = True
        
        # Check for health trend down based on recent negative signals
        # Count negative events in past 7 days as proxy for worsening trend
        recent_negative = self._query_scalar("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM tasks 
                WHERE project_id IN (SELECT id FROM projects WHERE client_id = ?)
                AND status = 'active' AND due_date < date('now') AND due_date >= date('now', '-7 days')
                UNION ALL
                SELECT 1 FROM communications
                WHERE client_id = ? AND action_needed = 1 AND created_at >= datetime('now', '-7 days')
            )
        """, (client_id, client_id))
        
        if recent_negative and recent_negative >= 3:
            score -= 10  # Worsening trend penalty
            has_any_signal = True
        
        if not has_any_signal:
            # Check if we have any comms or commitments data at all
            has_comms = self._query_scalar(
                "SELECT COUNT(*) FROM communications WHERE client_id = ?", (client_id,)
            )
            has_commits = self._query_scalar(
                "SELECT COUNT(*) FROM commitments WHERE client_id = ?", (client_id,)
            )
            has_data = (has_comms or 0) + (has_commits or 0)
            
            if not has_data or has_data == 0:
                return None  # No signals available
        
        return max(0.0, min(100.0, score))
    
    def get_commitment_counts(self, client_id: str) -> Dict[str, int]:
        """Get commitment counts for tiles."""
        result = self._query_one("""
            SELECT 
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
                COUNT(CASE WHEN status = 'open' AND deadline IS NOT NULL 
                      AND deadline < datetime('now', '+7 days') THEN 1 END) as at_risk,
                COUNT(CASE WHEN status = 'broken' THEN 1 END) as broken
            FROM commitments
            WHERE client_id = ?
        """, (client_id,))
        
        return {
            'open': result.get('open_count', 0) if result else 0,
            'at_risk': result.get('at_risk', 0) if result else 0,
            'broken': result.get('broken', 0) if result else 0,
        }
    
    def compute_capacity_score(self, client_id: str) -> Tuple[float, bool]:
        """
        Compute CapacityScore per §5.7.
        
        Returns (score, is_unknown).
        """
        # Get hours needed for client tasks within horizon
        horizon_days = {
            Horizon.NOW: 0.5,
            Horizon.TODAY: 1,
            Horizon.THIS_WEEK: 7,
        }.get(self.horizon, 1)
        
        tasks = self._query_one("""
            SELECT 
                SUM(COALESCE(duration_min, 60)) / 60.0 as hours_needed
            FROM tasks
            WHERE client_id = ?
            AND client_link_status = 'linked'
            AND status NOT IN ('done', 'completed')
            AND (due_date IS NULL OR due_date <= date('now', '+' || ? || ' days'))
        """, (client_id, horizon_days))
        
        hours_needed = tasks.get('hours_needed') or 0 if tasks else 0
        
        if hours_needed == 0:
            return (100.0, False)
        
        # Simplified: assume 40h/week available
        # In reality, would need lane/person capacity data
        hours_available = 40.0 * (horizon_days / 7)
        
        gap = max(0, hours_needed - hours_available)
        
        if gap == 0:
            return (100.0, False)
        
        gap_ratio = clamp01(gap / max(1, hours_needed))
        score = 100.0 * (1.0 - gap_ratio)
        
        return (score, False)
    
    def compute_health_score(self, client_id: str) -> Tuple[ClientScores, ClientConfidence]:
        """
        Compute full health score per Page 5 §4.2 (locked).
        
        Health = 0.35 * DeliveryHealth + 0.25 * CommsHealth + 0.25 * CashHealth + 0.15 * RelationshipHealth
        
        If a component lacks valid data, it is excluded and weights renormalized,
        but confidence must drop and why_low must state which components were excluded.
        """
        scores = ClientScores()
        why_low = []
        components_missing = []
        
        # Compute subscores
        delivery_health = self.compute_delivery_score(client_id)
        cash_health, cash_unknown = self.compute_cash_health(client_id)
        comms_health = self.compute_comms_health(client_id)
        relationship_health = self.compute_relationship_health(client_id)
        
        # Store in scores (using existing fields where possible)
        scores.delivery = delivery_health if delivery_health is not None else 100.0
        scores.finance = cash_health if cash_health is not None else 100.0
        scores.responsiveness = comms_health if comms_health is not None else 100.0
        # Use commitments field for relationship
        scores.commitments = relationship_health if relationship_health is not None else 100.0
        scores.finance_unknown = cash_unknown
        
        # Build weighted components for renormalization
        components = {}
        weights = self.HEALTH_WEIGHTS.copy()
        
        # DeliveryHealth
        if delivery_health is not None:
            components['delivery'] = delivery_health
        else:
            del weights['delivery']
            components_missing.append("No linked projects for client")
        
        # CashHealth
        if cash_health is not None:
            components['cash'] = cash_health
        else:
            del weights['cash']
            if cash_unknown:
                components_missing.append("Valid AR coverage incomplete")
            else:
                components_missing.append("No AR data for client")
        
        # CommsHealth
        if comms_health is not None:
            components['comms'] = comms_health
        else:
            del weights['comms']
            components_missing.append("No linked comm threads for client")
        
        # RelationshipHealth
        if relationship_health is not None:
            components['relationship'] = relationship_health
        else:
            del weights['relationship']
            # Don't add to missing if we just don't have signals
        
        # Renormalize weights and compute health
        if components:
            total_weight = sum(weights.values())
            if total_weight > 0:
                scores.health = sum(
                    (weights[k] / total_weight) * components[k]
                    for k in components.keys()
                )
            else:
                scores.health = 50.0  # Fallback
        else:
            scores.health = 50.0  # No data at all
            components_missing.append("No valid data for health calculation")
        
        # Determine confidence per §4.4 (locked)
        confidence_level = Confidence.HIGH
        
        # Check data integrity
        if not self.data_integrity:
            confidence_level = Confidence.LOW
            why_low.append("Data integrity check failed")
        
        # Check client coverage
        if self.client_coverage_pct < 80:
            if confidence_level == Confidence.HIGH:
                confidence_level = Confidence.MED
            why_low.append("Client coverage below 80%")
        
        # Check how many domains have valid data
        valid_domains = len(components)
        if valid_domains == 0:
            confidence_level = Confidence.LOW
            why_low.append("No valid domain data")
        elif valid_domains <= 2 and confidence_level == Confidence.HIGH:
            confidence_level = Confidence.MED
        
        # Two+ domains missing = LOW
        if len(components_missing) >= 2:
            confidence_level = Confidence.LOW
        
        # Add missing component reasons
        why_low.extend(components_missing[:3 - len(why_low)])
        
        confidence = ClientConfidence(level=confidence_level, why_low=why_low[:3])
        
        return scores, confidence
    
    def _get_client_chain_coverage(self, client_id: str) -> float:
        """Get task chain coverage for a specific client."""
        result = self._query_one("""
            SELECT 
                COUNT(CASE WHEN client_link_status = 'linked' THEN 1 END) as linked,
                COUNT(CASE WHEN client_link_status != 'n/a' THEN 1 END) as applicable
            FROM tasks
            WHERE client_id = ? OR project_id IN (SELECT id FROM projects WHERE client_id = ?)
        """, (client_id, client_id))
        
        if not result or not result.get('applicable') or result['applicable'] == 0:
            return 100.0  # No applicable tasks = 100%
        
        return 100.0 * result['linked'] / result['applicable']
    
    def determine_risk_band(self, client_id: str, scores: ClientScores) -> str:
        """
        Determine RiskBand per Page 5 §4.3 (locked).
        
        HIGH if Health < 60 OR any of:
          - DeliveryExposure has a RED project
          - Cash severe_pct >= 0.25
          - VIP overdue comm exists
          - broken commitment exists
        
        MED if Health 60-79 OR two+ domains are yellow
        
        LOW otherwise
        """
        # Check explicit HIGH triggers
        if scores.health < 60:
            return "HIGH"
        
        # Check for RED project
        red_project = self._query_scalar("""
            SELECT COUNT(*) FROM projects p
            WHERE p.client_id = ? AND p.is_internal = 0
            AND EXISTS (
                SELECT 1 FROM tasks t
                WHERE t.project_id = p.id
                AND t.due_date < date('now')
                AND t.status NOT IN ('done', 'completed')
                GROUP BY t.project_id
                HAVING COUNT(*) >= 3
            )
        """, (client_id,))
        if red_project and red_project > 0:
            return "HIGH"
        
        # Check Cash severe_pct >= 0.25
        ar_data = self._query_one("""
            SELECT 
                SUM(amount) as total,
                SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe
            FROM invoices
            WHERE client_id = ? AND status IN ('sent', 'overdue')
            AND paid_date IS NULL AND due_date IS NOT NULL
        """, (client_id,))
        if ar_data and ar_data.get('total') and ar_data['total'] > 0:
            severe_pct = (ar_data.get('severe') or 0) / ar_data['total']
            if severe_pct >= 0.25:
                return "HIGH"
        
        # Check VIP overdue comm
        vip_overdue = self._query_scalar("""
            SELECT COUNT(*) FROM communications
            WHERE client_id = ? AND COALESCE(is_vip, 0) = 1
            AND COALESCE(expected_response_by, response_deadline) < datetime('now')
        """, (client_id,))
        if vip_overdue and vip_overdue > 0:
            return "HIGH"
        
        # Check broken commitment
        broken = self._query_scalar("""
            SELECT COUNT(*) FROM commitments
            WHERE client_id = ? AND status = 'broken'
        """, (client_id,))
        if broken and broken > 0:
            return "HIGH"
        
        # Check MED conditions
        if 60 <= scores.health < 80:
            return "MED"
        
        # Check two+ domains yellow
        yellow_count = 0
        if scores.delivery < 70:
            yellow_count += 1
        if scores.finance < 70:
            yellow_count += 1
        if scores.responsiveness < 70:
            yellow_count += 1
        if scores.commitments < 70:
            yellow_count += 1
        
        if yellow_count >= 2:
            return "MED"
        
        return "LOW"
    
    def determine_status(self, scores: ClientScores) -> ClientStatus:
        """
        Determine client status pill (maps from risk band).
        """
        # This is now derived from health score directly
        if scores.health < 50:
            return ClientStatus.RED
        if scores.health < 70:
            return ClientStatus.YELLOW
        return ClientStatus.GREEN
    
    def determine_top_driver(self, scores: ClientScores) -> ClientTopDriver:
        """Determine top driver based on lowest subscore."""
        subscores = [
            (ClientTopDriver.DELIVERY, scores.delivery),
            (ClientTopDriver.CASH, scores.finance),
            (ClientTopDriver.COMMS, scores.responsiveness),
            (ClientTopDriver.COMMITMENTS, scores.commitments),
            (ClientTopDriver.CAPACITY, scores.capacity),
        ]
        
        # Find lowest
        lowest = min(subscores, key=lambda x: x[1])
        
        # If all high, return Unknown
        if lowest[1] >= 90:
            return ClientTopDriver.UNKNOWN
        
        return lowest[0]
    
    # =========================================================================
    # PORTFOLIO METHODS
    # =========================================================================
    
    def get_eligible_clients(self) -> List[str]:
        """
        Get clients eligible for portfolio per §4.
        """
        clients = self._query_all("""
            SELECT DISTINCT c.id
            FROM clients c
            WHERE 
                -- Has active client-facing project/retainer
                EXISTS (
                    SELECT 1 FROM projects p 
                    WHERE p.client_id = c.id AND p.is_internal = 0
                )
                -- OR has valid AR
                OR EXISTS (
                    SELECT 1 FROM invoices i
                    WHERE i.client_id = c.id
                    AND i.status IN ('sent', 'overdue')
                    AND i.paid_date IS NULL
                    AND i.due_date IS NOT NULL
                )
                -- OR has comms requiring response
                OR EXISTS (
                    SELECT 1 FROM communications cm
                    WHERE cm.client_id = c.id
                    AND (cm.requires_response = 1 OR cm.response_deadline IS NOT NULL)
                )
                -- OR has open commitments
                OR EXISTS (
                    SELECT 1 FROM commitments co
                    WHERE co.client_id = c.id AND co.status = 'open'
                )
        """)
        
        return [c['id'] for c in clients]
    
    def build_portfolio(self) -> List[ClientPortfolioItem]:
        """
        Build ranked client portfolio per §9.1.
        """
        client_ids = self.get_eligible_clients()
        items = []
        
        for client_id in client_ids:
            client = self._query_one("""
                SELECT id, name, tier, health_score
                FROM clients WHERE id = ?
            """, (client_id,))
            
            if not client:
                continue
            
            # Compute scores
            scores, confidence = self.compute_health_score(client_id)
            status = self.determine_status(scores)
            top_driver = self.determine_top_driver(scores)
            
            # Adjust status if confidence is LOW
            if confidence.level == Confidence.LOW:
                status = ClientStatus.PARTIAL
            
            # Calculate trend based on recent activity signals
            trend = self._compute_client_trend(client_id, scores.health)
            
            items.append(ClientPortfolioItem(
                client_id=client_id,
                name=client.get('name', ''),
                tier=client.get('tier', 'C'),
                status=status,
                health_score=scores.health,
                top_driver=top_driver,
                trend=trend,
                confidence=confidence.level,
                why_low=confidence.why_low,
            ))
        
        # Rank per §9.1
        status_order = {
            ClientStatus.RED: 0,
            ClientStatus.YELLOW: 1,
            ClientStatus.GREEN: 2,
            ClientStatus.PARTIAL: 3,
        }
        
        driver_priority = self.DRIVER_PRIORITY[self.mode]
        
        def rank_key(item: ClientPortfolioItem):
            driver_rank = driver_priority.index(item.top_driver) if item.top_driver in driver_priority else 99
            conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
            return (
                status_order.get(item.status, 99),
                item.health_score,  # Lower first
                driver_rank,
                conf_order.get(item.confidence, 99),
            )
        
        items.sort(key=rank_key)
        
        return items[:self.MAX_PORTFOLIO]
    
    # =========================================================================
    # CLIENT ROOM METHODS
    # =========================================================================
    
    def build_client_room(self, client_id: str) -> Optional[Dict]:
        """
        Build complete client room data per spec.
        """
        client = self._query_one("""
            SELECT id, name, tier
            FROM clients WHERE id = ?
        """, (client_id,))
        
        if not client:
            return None
        
        # Compute scores
        scores, confidence = self.compute_health_score(client_id)
        status = self.determine_status(scores)
        top_driver = self.determine_top_driver(scores)
        risk_band = self.determine_risk_band(client_id, scores)
        
        # Get last touched (latest comm)
        last_comm = self._query_one("""
            SELECT MAX(received_at) as last FROM communications WHERE client_id = ?
        """, (client_id,))
        last_touched = last_comm.get('last') if last_comm else None
        
        # Get primary owner (from dominant project owner)
        owner_row = self._query_one("""
            SELECT owner, COUNT(*) as cnt FROM projects
            WHERE client_id = ? AND owner IS NOT NULL
            GROUP BY owner ORDER BY cnt DESC LIMIT 1
        """, (client_id,))
        primary_owner = owner_row.get('owner') if owner_row else None
        
        # Build header with full fields for template
        header = {
            "name": client.get('name', ''),
            "tier": client.get('tier', 'C'),
            "risk_band": risk_band,
            "health_score": round(scores.health, 1),
            "trend": "UNKNOWN",  # Would need delta tracking
            "confidence": {
                "level": confidence.level.value,
                "why_low": confidence.why_low,
            },
            "last_touched_at": last_touched,
            "primary_owner": primary_owner,
        }
        
        # Build each module
        key_drivers = self._build_key_drivers(client_id, scores)
        delivery_exposure = self._build_delivery_exposure(client_id)
        cash_exposure = self._build_cash_exposure(client_id)
        comms = self._build_comms(client_id)
        commitments = self._build_commitments(client_id)
        capacity = self._build_capacity(client_id)
        recent_change = self._build_recent_change(client_id)
        actions = self._build_actions(client_id, scores, top_driver)
        
        # Summary sentence
        summary = f"Health is {scores.health:.0f} because {top_driver.value.lower()} "
        if top_driver == ClientTopDriver.DELIVERY:
            summary += f"score is {scores.delivery:.0f}."
        elif top_driver == ClientTopDriver.CASH:
            summary += f"score is {scores.finance:.0f}."
        elif top_driver == ClientTopDriver.COMMS:
            summary += f"responsiveness is {scores.responsiveness:.0f}."
        elif top_driver == ClientTopDriver.COMMITMENTS:
            summary += f"commitment health is {scores.commitments:.0f}."
        elif top_driver == ClientTopDriver.CAPACITY:
            summary += f"capacity score is {scores.capacity:.0f}."
        else:
            summary = f"Health is {scores.health:.0f} (no major concerns detected)."
        
        # Build tiles and narrative
        tiles = self._build_tiles(client_id)
        narrative = self._build_narrative(client_id, scores, top_driver)
        
        return {
            "client_id": client_id,
            "header": header,
            "summary_sentence": summary,
            "scores": {
                "health": round(scores.health, 1),
                "delivery": round(scores.delivery, 1),
                "finance": round(scores.finance, 1),
                "responsiveness": round(scores.responsiveness, 1),
                "commitments": round(scores.commitments, 1),
                "capacity": round(scores.capacity, 1),
            },
            "tiles": tiles,
            "narrative": narrative,
            "confidence": {
                "level": confidence.level.value,
                "why_low": confidence.why_low,
            },
            "key_drivers": key_drivers,
            "delivery_exposure": delivery_exposure,
            "cash_exposure": cash_exposure,
            "comms": comms,
            "commitments": commitments,
            "capacity": capacity,
            "recent_change": recent_change,
            "actions": actions,
        }
    
    def _build_header(self, client_id: str, client: Dict) -> Dict:
        """Build client header."""
        # Get owner (if defined)
        owner = None  # Would need owner field on clients table
        
        # Get brands count
        brands = self._query_scalar("""
            SELECT COUNT(*) FROM brands WHERE client_id = ?
        """, (client_id,))
        
        # Get active projects count
        projects = self._query_scalar("""
            SELECT COUNT(*) FROM projects 
            WHERE client_id = ? AND is_internal = 0
        """, (client_id,))
        
        return {
            "tier": client.get('tier', 'C'),
            "owner": owner,
            "brands_count": brands or 0,
            "active_projects_count": projects or 0,
        }
    
    def _build_key_drivers(self, client_id: str, scores: ClientScores) -> List[Dict]:
        """Build key drivers list (max 5)."""
        drivers = []
        
        # Add driver for each low score
        if scores.delivery < 70:
            overdue = self._query_scalar("""
                SELECT COUNT(*) FROM tasks
                WHERE client_id = ? AND due_date < date('now')
                AND status NOT IN ('done', 'completed')
            """, (client_id,))
            
            drivers.append({
                "title": f"Delivery risk: {overdue or 0} overdue tasks",
                "evidence": [{"type": "client", "id": client_id}],
                "primary_action": {
                    "action_id": f"review_delivery_{client_id}",
                    "risk_level": "auto",
                    "label": "Review overdue tasks",
                },
            })
        
        if scores.finance < 70:
            ar_total = self._query_scalar("""
                SELECT SUM(amount) FROM invoices
                WHERE client_id = ? AND status IN ('sent', 'overdue')
                AND paid_date IS NULL
            """, (client_id,))
            
            drivers.append({
                "title": f"AR exposure: AED {(ar_total or 0):,.0f} outstanding",
                "evidence": [{"type": "client", "id": client_id}],
                "primary_action": {
                    "action_id": f"review_ar_{client_id}",
                    "risk_level": "propose",
                    "label": "Send reminder",
                },
            })
        
        if scores.responsiveness < 70:
            overdue = self._query_scalar("""
                SELECT COUNT(*) FROM communications
                WHERE client_id = ?
                AND response_deadline < datetime('now')
                AND COALESCE(processed, 0) = 0
            """, (client_id,))
            
            drivers.append({
                "title": f"Comms risk: {overdue or 0} overdue responses",
                "evidence": [{"type": "communication", "id": client_id}],
                "primary_action": {
                    "action_id": f"respond_comms_{client_id}",
                    "risk_level": "propose",
                    "label": "Draft response",
                },
            })
        
        if scores.commitments < 70:
            broken = self._query_scalar("""
                SELECT COUNT(*) FROM commitments
                WHERE client_id = ? AND status = 'broken'
            """, (client_id,))
            
            drivers.append({
                "title": f"Commitment risk: {broken or 0} broken promises",
                "evidence": [{"type": "commitment", "id": client_id}],
                "primary_action": {
                    "action_id": f"review_commitments_{client_id}",
                    "risk_level": "propose",
                    "label": "Renegotiate deadlines",
                },
            })
        
        return drivers[:self.MAX_KEY_DRIVERS]
    
    def _build_delivery_exposure(self, client_id: str) -> Dict:
        """Build delivery exposure section."""
        projects = self._query_all("""
            SELECT 
                p.id as project_id,
                p.name,
                p.deadline,
                COUNT(t.id) as total_tasks,
                COUNT(CASE WHEN t.status NOT IN ('done', 'completed') THEN 1 END) as open_tasks,
                COUNT(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('done', 'completed') THEN 1 END) as overdue
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.client_id = ? AND p.is_internal = 0
            GROUP BY p.id
            ORDER BY overdue DESC, open_tasks DESC
            LIMIT ?
        """, (client_id, self.MAX_PROJECTS))
        
        items = []
        for proj in projects:
            # Compute slip risk
            deadline_pressure = 0.0
            time_to_slip = None
            if proj.get('deadline'):
                try:
                    deadline = datetime.strptime(proj['deadline'], '%Y-%m-%d').date()
                    days_to = (deadline - self.today).days
                    time_to_slip = days_to * 24
                    deadline_pressure = clamp01(1 - (days_to / 14))
                except:
                    pass
            
            total = proj.get('total_tasks') or 1
            open_t = proj.get('open_tasks') or 0
            overdue = proj.get('overdue') or 0
            
            remaining_ratio = open_t / max(1, total)
            blocking = clamp01(overdue / max(1, open_t)) if open_t > 0 else 0
            
            slip_risk = 0.35 * deadline_pressure + 0.25 * remaining_ratio + 0.15 * blocking
            
            # Status
            if overdue > 0 or slip_risk >= 0.75:
                status = "RED"
            elif slip_risk >= 0.45:
                status = "YELLOW"
            else:
                status = "GREEN"
            
            # Top driver
            if overdue > 0:
                driver = "Overdue"
            elif deadline_pressure > 0.5:
                driver = "Deadline"
            else:
                driver = "Scope"
            
            items.append({
                "project_id": proj['project_id'],
                "name": proj.get('name', ''),
                "status": status,
                "time_to_slip_hours": time_to_slip,
                "slip_risk_score": round(slip_risk, 2),
                "top_driver": driver,
                "confidence": "HIGH",
            })
        
        return {"projects": items}
    
    def _build_cash_exposure(self, client_id: str) -> Dict:
        """Build cash/AR exposure section."""
        buckets = self._query_one("""
            SELECT 
                SUM(amount) as total,
                SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END) as current,
                SUM(CASE WHEN aging_bucket = '1-30' THEN amount ELSE 0 END) as b1_30,
                SUM(CASE WHEN aging_bucket = '31-60' THEN amount ELSE 0 END) as b31_60,
                SUM(CASE WHEN aging_bucket = '61-90' THEN amount ELSE 0 END) as b61_90,
                SUM(CASE WHEN aging_bucket = '90+' THEN amount ELSE 0 END) as b90_plus
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
        """, (client_id,))
        
        # Get top overdue lines
        lines = self._query_all("""
            SELECT id, external_id, amount, due_date, aging_bucket,
                   julianday(date('now')) - julianday(due_date) as days_overdue
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
            AND due_date < date('now')
            ORDER BY amount DESC
            LIMIT ?
        """, (client_id, self.MAX_AR_LINES))
        
        # Count invalid AR
        invalid = self._query_scalar("""
            SELECT COUNT(*) FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND (due_date IS NULL OR client_id IS NULL)
        """, (client_id,))
        
        return {
            "ar_total": (buckets.get('total') or 0) if buckets else 0,
            "buckets": {
                "current": (buckets.get('current') or 0) if buckets else 0,
                "1-30": (buckets.get('b1_30') or 0) if buckets else 0,
                "31-60": (buckets.get('b31_60') or 0) if buckets else 0,
                "61-90": (buckets.get('b61_90') or 0) if buckets else 0,
                "90+": (buckets.get('b90_plus') or 0) if buckets else 0,
            },
            "top_lines": [
                {
                    "invoice_id": l['id'],
                    "amount": l.get('amount', 0),
                    "days_overdue": int(l.get('days_overdue') or 0),
                    "bucket": l.get('aging_bucket', 'unknown'),
                }
                for l in lines
            ],
            "excluded_invalid_ar_count": invalid or 0,
        }
    
    def _build_comms(self, client_id: str) -> Dict:
        """Build comms/responsiveness section."""
        stats = self._query_one("""
            SELECT 
                COUNT(CASE WHEN requires_response = 1 OR response_deadline IS NOT NULL THEN 1 END) as response_needed,
                COUNT(CASE 
                    WHEN response_deadline IS NOT NULL 
                    AND response_deadline < datetime('now')
                    AND COALESCE(processed, 0) = 0 
                    THEN 1 
                END) as overdue,
                MAX(CASE 
                    WHEN response_deadline IS NOT NULL 
                    AND response_deadline < datetime('now')
                    AND COALESCE(processed, 0) = 0 
                    THEN (julianday('now') - julianday(response_deadline)) * 24
                END) as oldest_age
            FROM communications
            WHERE client_id = ?
        """, (client_id,))
        
        threads = self._query_all("""
            SELECT id, subject, created_at, response_deadline,
                   (julianday('now') - julianday(created_at)) * 24 as age_hours
            FROM communications
            WHERE client_id = ?
            AND (requires_response = 1 OR response_deadline IS NOT NULL)
            ORDER BY 
                CASE WHEN response_deadline < datetime('now') THEN 0 ELSE 1 END,
                response_deadline ASC
            LIMIT ?
        """, (client_id, self.MAX_COMMS_THREADS))
        
        thread_items = []
        for t in threads:
            is_breach = (
                t.get('response_deadline') and 
                datetime.fromisoformat(t['response_deadline']) < self.now
            ) if t.get('response_deadline') else False
            
            age = t.get('age_hours') or 0
            risk = "HIGH" if is_breach else ("MED" if age > 24 else "LOW")
            
            thread_items.append({
                "thread_id": t['id'],
                "subject": t.get('subject', ''),
                "age_hours": round(age, 1),
                "expected_response_by": t.get('response_deadline'),
                "sla_breach": is_breach,
                "risk": risk,
            })
        
        return {
            "response_needed": (stats.get('response_needed') or 0) if stats else 0,
            "overdue": (stats.get('overdue') or 0) if stats else 0,
            "oldest_overdue_age_hours": round(stats.get('oldest_age') or 0, 1) if stats else 0,
            "threads": thread_items,
        }
    
    def _build_commitments(self, client_id: str) -> Dict:
        """Build commitments section."""
        stats = self._query_one("""
            SELECT 
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
                COUNT(CASE WHEN status = 'open' AND deadline < date('now') THEN 1 END) as overdue_open,
                COUNT(CASE WHEN status = 'broken' AND created_at >= date('now', '-30 days') THEN 1 END) as broken_30d
            FROM commitments
            WHERE client_id = ?
        """, (client_id,))
        
        items = self._query_all("""
            SELECT id, text, deadline, status
            FROM commitments
            WHERE client_id = ?
            AND status IN ('open', 'broken')
            ORDER BY 
                CASE WHEN status = 'broken' THEN 0 ELSE 1 END,
                deadline ASC
            LIMIT ?
        """, (client_id, self.MAX_COMMITMENTS))
        
        commitment_items = []
        for c in items:
            is_overdue = (
                c.get('deadline') and 
                datetime.strptime(c['deadline'], '%Y-%m-%d').date() < self.today
            ) if c.get('deadline') else False
            
            risk = "HIGH" if c['status'] == 'broken' or is_overdue else "MED" if c.get('deadline') else "LOW"
            
            commitment_items.append({
                "commitment_id": c['id'],
                "text": c.get('text', '')[:100],  # Truncate
                "deadline": c.get('deadline'),
                "status": c['status'],
                "risk": risk,
            })
        
        return {
            "open_count": (stats.get('open_count') or 0) if stats else 0,
            "overdue_open_count": (stats.get('overdue_open') or 0) if stats else 0,
            "broken_30d_count": (stats.get('broken_30d') or 0) if stats else 0,
            "items": commitment_items,
        }
    
    def _build_capacity(self, client_id: str) -> Dict:
        """Build capacity section."""
        tasks = self._query_one("""
            SELECT 
                SUM(COALESCE(duration_min, 60)) / 60.0 as hours_needed,
                lane
            FROM tasks
            WHERE client_id = ?
            AND client_link_status = 'linked'
            AND status NOT IN ('done', 'completed')
            GROUP BY lane
            ORDER BY hours_needed DESC
            LIMIT 1
        """, (client_id,))
        
        hours_needed = tasks.get('hours_needed') or 0 if tasks else 0
        hours_available = 40.0  # Simplified
        gap = max(0, hours_needed - hours_available)
        
        constraint = None
        if gap > 0 and tasks:
            constraint = {
                "type": "lane",
                "name": tasks.get('lane'),
            }
        
        return {
            "hours_needed": round(hours_needed, 1),
            "hours_available": round(hours_available, 1),
            "gap_hours": round(gap, 1),
            "top_constraint": constraint,
        }
    
    def _build_recent_change(self, client_id: str) -> List[Dict]:
        """Build recent change section (simplified)."""
        # Would need delta tracking against previous snapshot
        return []
    
    def _build_actions(self, client_id: str, scores: ClientScores, top_driver: ClientTopDriver) -> List[Dict]:
        """Build actions panel per §7."""
        actions = []
        
        # Delivery actions
        if scores.delivery < 70:
            actions.append({
                "action_id": f"assign_owner_{client_id}",
                "risk_level": "auto",
                "label": "Assign missing owners",
                "entity_type": "client",
                "entity_id": client_id,
                "idempotency_key": f"assign_owner_{client_id}_{self.today.isoformat()}",
                "payload": {"action": "assign_owner"},
                "why": "Tasks missing owners need assignment for accountability",
            })
            
            actions.append({
                "action_id": f"rebalance_{client_id}",
                "risk_level": "propose",
                "label": "Rebalance workload",
                "entity_type": "client",
                "entity_id": client_id,
                "idempotency_key": f"rebalance_{client_id}_{self.today.isoformat()}",
                "payload": {"action": "rebalance"},
                "why": "Redistribute tasks to reduce delivery risk",
            })
        
        # Finance actions
        if scores.finance < 70:
            actions.append({
                "action_id": f"send_reminder_{client_id}",
                "risk_level": "propose",
                "label": "Send invoice reminder",
                "entity_type": "client",
                "entity_id": client_id,
                "idempotency_key": f"reminder_{client_id}_{self.today.isoformat()}",
                "payload": {"action": "send_reminder"},
                "why": "Outstanding AR requires follow-up",
            })
        
        # Comms actions
        if scores.responsiveness < 70:
            actions.append({
                "action_id": f"draft_response_{client_id}",
                "risk_level": "propose",
                "label": "Draft response",
                "entity_type": "client",
                "entity_id": client_id,
                "idempotency_key": f"draft_{client_id}_{self.today.isoformat()}",
                "payload": {"action": "draft_response"},
                "why": "Overdue communications need response",
            })
        
        # Commitment actions
        if scores.commitments < 70:
            actions.append({
                "action_id": f"renegotiate_{client_id}",
                "risk_level": "propose",
                "label": "Renegotiate deadlines",
                "entity_type": "client",
                "entity_id": client_id,
                "idempotency_key": f"renegotiate_{client_id}_{self.today.isoformat()}",
                "payload": {"action": "renegotiate"},
                "why": "Commitments at risk of breach need renegotiation",
            })
        
        # Always include resolution queue action if issues exist
        actions.append({
            "action_id": f"create_queue_item_{client_id}",
            "risk_level": "auto",
            "label": "Create resolution item",
            "entity_type": "client",
            "entity_id": client_id,
            "idempotency_key": f"queue_{client_id}_{self.today.isoformat()}",
            "payload": {"action": "create_queue_item"},
            "why": "Track this client for ongoing attention",
        })
        
        return actions[:self.MAX_ACTIONS]
    
    # =========================================================================
    # MAIN OUTPUT (Page 5 §8.1 locked structure)
    # =========================================================================
    
    def generate(self, selected_client_id: Optional[str] = None) -> Dict:
        """
        Generate complete client_360 section per Page 5 §8.1.
        """
        # Build portfolio
        portfolio_items = self.build_portfolio()
        
        # Select client (default to highest risk)
        if not selected_client_id and portfolio_items:
            # Find first HIGH risk or first item
            for item in portfolio_items:
                if item.status == ClientStatus.RED:
                    selected_client_id = item.client_id
                    break
            if not selected_client_id:
                selected_client_id = portfolio_items[0].client_id
        
        # Build portfolio for output (per §8.1)
        portfolio = []
        for p in portfolio_items[:25]:  # Cap at 25
            scores, confidence = self.compute_health_score(p.client_id)
            risk_band = self.determine_risk_band(p.client_id, scores)
            
            # Get next break hours (from delivery or commitments)
            next_break = self._get_next_break_hours(p.client_id)
            
            portfolio.append({
                "client_id": p.client_id,
                "name": p.name,
                "tier": p.tier,
                "risk_band": risk_band,
                "health_score": round(p.health_score, 1),
                "trend": p.trend.upper() if p.trend else "UNKNOWN",
                "top_driver": p.top_driver.value,
                "next_break_hours": next_break,
                "confidence": p.confidence.value,
                "why_low": p.why_low,
            })
        
        # Build selected client room per §8.1
        selected_client = None
        if selected_client_id:
            selected_client = self._build_selected_client(selected_client_id)
        
        # Get last sync times
        last_sync = self._get_last_sync_times()
        
        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "client_coverage_pct": self.client_coverage_pct,
                    "finance_ar_coverage_pct": self.finance_ar_coverage_pct,
                    "commitment_ready_pct": getattr(self, 'commitment_ready_pct', 100.0),
                    "last_sync": last_sync,
                },
            },
            "portfolio": portfolio,
            "selected_client": selected_client,
        }
    
    def _get_next_break_hours(self, client_id: str) -> Optional[float]:
        """Get hours until next break for client."""
        # Check project time_to_slip
        project = self._query_one("""
            SELECT MIN(
                CASE WHEN p.deadline IS NOT NULL 
                THEN (julianday(p.deadline) - julianday('now')) * 24
                ELSE 999 END
            ) as hours
            FROM projects p
            WHERE p.client_id = ? AND p.is_internal = 0
            AND EXISTS (
                SELECT 1 FROM tasks t
                WHERE t.project_id = p.id
                AND t.status NOT IN ('done', 'completed')
            )
        """, (client_id,))
        
        if project and project.get('hours') and project['hours'] < 999:
            return round(project['hours'], 1)
        
        # Check commitment deadlines
        commit = self._query_one("""
            SELECT MIN((julianday(deadline) - julianday('now')) * 24) as hours
            FROM commitments
            WHERE client_id = ? AND status = 'open' AND deadline IS NOT NULL
        """, (client_id,))
        
        if commit and commit.get('hours'):
            return round(commit['hours'], 1)
        
        return None
    
    def _get_last_sync_times(self) -> Dict[str, Optional[str]]:
        """Get last sync times for each source."""
        result = {
            "gmail": None,
            "calendar": None,
            "tasks": None,
            "xero": None,
        }
        
        syncs = self._query_all("""
            SELECT source, last_sync FROM sync_state
            WHERE source IN ('gmail', 'calendar', 'asana', 'xero')
        """)
        
        for s in syncs:
            source = s['source']
            if source == 'asana':
                source = 'tasks'
            if source in result:
                result[source] = s.get('last_sync')
        
        return result
    
    def _build_selected_client(self, client_id: str) -> Optional[Dict]:
        """Build selected_client per Page 5 §8.1."""
        client = self._query_one("""
            SELECT id, name, tier FROM clients WHERE id = ?
        """, (client_id,))
        
        if not client:
            return None
        
        scores, confidence = self.compute_health_score(client_id)
        risk_band = self.determine_risk_band(client_id, scores)
        top_driver = self.determine_top_driver(scores)
        
        # Get last touched (latest comm)
        last_comm = self._query_one("""
            SELECT MAX(received_at) as last FROM communications WHERE client_id = ?
        """, (client_id,))
        last_touched = last_comm.get('last') if last_comm else None
        
        # Get primary owner (from dominant project owner)
        owner = self._query_one("""
            SELECT owner, COUNT(*) as cnt FROM projects
            WHERE client_id = ? AND owner IS NOT NULL
            GROUP BY owner ORDER BY cnt DESC LIMIT 1
        """, (client_id,))
        primary_owner = owner.get('owner') if owner else None
        
        # Build tiles per §6.2
        tiles = self._build_tiles(client_id)
        
        # Build narrative per §6.3
        narrative = self._build_narrative(client_id, scores, top_driver)
        
        # Build modules
        delivery_exposure = self._build_delivery_exposure(client_id)
        cash_exposure = self._build_cash_exposure(client_id)
        comms_commitments = self._build_comms_commitments(client_id)
        capacity_exposure = self._build_capacity_exposure(client_id)
        recent_change = self._build_recent_change(client_id)
        actions = self._build_actions(client_id, scores, top_driver)
        
        # Build reason line per §6.9
        reason = f"{self.horizon.value} | {risk_band} risk | top_driver={top_driver.value}"
        
        return {
            "client_id": client_id,
            "header": {
                "name": client.get('name', ''),
                "tier": client.get('tier', 'C'),
                "risk_band": risk_band,
                "health_score": round(scores.health, 1),
                "trend": "UNKNOWN",  # Would need delta tracking
                "confidence": {
                    "level": confidence.level.value,
                    "why_low": confidence.why_low,
                },
                "last_touched_at": last_touched,
                "primary_owner": primary_owner,
            },
            "tiles": tiles,
            "narrative": narrative,
            "delivery_exposure": delivery_exposure,
            "cash_exposure": cash_exposure,
            "comms_commitments": comms_commitments,
            "capacity_exposure": capacity_exposure,
            "recent_change": recent_change,
            "actions": actions,
            "reason": reason,
        }
    
    def _build_tiles(self, client_id: str) -> Dict:
        """Build executive snapshot tiles per §6.2."""
        # Delivery tile
        delivery = self._query_one("""
            SELECT 
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM tasks t WHERE t.project_id = p.id
                    AND t.due_date < date('now') AND t.status NOT IN ('done', 'completed')
                    GROUP BY t.project_id HAVING COUNT(*) >= 3
                ) THEN 1 END) as red,
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM tasks t WHERE t.project_id = p.id
                    AND t.due_date < date('now', '+7 days') AND t.status NOT IN ('done', 'completed')
                    GROUP BY t.project_id HAVING COUNT(*) >= 1
                ) THEN 1 END) as yellow
            FROM projects p
            WHERE p.client_id = ? AND p.is_internal = 0
        """, (client_id,))
        
        top_project = self._query_one("""
            SELECT name FROM projects WHERE client_id = ? AND is_internal = 0
            ORDER BY deadline ASC NULLS LAST LIMIT 1
        """, (client_id,))
        
        # Cash tile
        cash = self._query_one("""
            SELECT 
                SUM(amount) as total,
                SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe
            FROM invoices
            WHERE client_id = ? AND status IN ('sent', 'overdue')
            AND paid_date IS NULL AND due_date IS NOT NULL
        """, (client_id,))
        
        # Comms tile
        comms = self._query_one("""
            SELECT 
                COUNT(CASE WHEN COALESCE(expected_response_by, response_deadline) < datetime('now') THEN 1 END) as overdue,
                COUNT(CASE WHEN COALESCE(expected_response_by, response_deadline) < datetime('now') 
                      AND COALESCE(is_vip, 0) = 1 THEN 1 END) as vip_overdue
            FROM communications WHERE client_id = ?
        """, (client_id,))
        
        # Commitments tile
        commits = self.get_commitment_counts(client_id)
        
        return {
            "delivery": {
                "red": delivery.get('red', 0) if delivery else 0,
                "yellow": delivery.get('yellow', 0) if delivery else 0,
                "top_project": top_project.get('name') if top_project else None,
            },
            "cash": {
                "valid_ar_total": cash.get('total', 0) if cash else 0,
                "severe_total": cash.get('severe', 0) if cash else 0,
                "currency": "AED",  # Default
            },
            "comms": {
                "overdue": comms.get('overdue', 0) if comms else 0,
                "vip_overdue": comms.get('vip_overdue', 0) if comms else 0,
            },
            "commitments": commits,
        }
    
    def _build_narrative(self, client_id: str, scores: ClientScores, top_driver: ClientTopDriver) -> List[Dict]:
        """Build reality narrative per §6.3 (max 3 bullets)."""
        bullets = []
        
        if scores.delivery < 70:
            # Get specific evidence
            overdue = self._query_scalar("""
                SELECT COUNT(*) FROM tasks
                WHERE client_id = ? AND client_link_status = 'linked'
                AND due_date < date('now') AND status NOT IN ('done', 'completed')
            """, (client_id,))
            bullets.append({
                "text": f"Because {overdue or 0} tasks are overdue, the risk is Delivery.",
                "domain": "Delivery",
                "evidence_ids": [],
            })
        
        if scores.finance < 70:
            severe = self._query_one("""
                SELECT SUM(amount) as amt FROM invoices
                WHERE client_id = ? AND aging_bucket IN ('61-90', '90+')
                AND status IN ('sent', 'overdue') AND paid_date IS NULL
            """, (client_id,))
            amt = (severe.get('amt') or 0) if severe else 0
            bullets.append({
                "text": f"Because severe AR is AED {amt:,.0f}, the risk is Cash.",
                "domain": "Cash",
                "evidence_ids": [],
            })
        
        if scores.responsiveness < 70:
            overdue = self._query_scalar("""
                SELECT COUNT(DISTINCT COALESCE(thread_id, id)) FROM communications
                WHERE client_id = ?
                AND COALESCE(expected_response_by, response_deadline) < datetime('now')
            """, (client_id,))
            bullets.append({
                "text": f"Because {overdue or 0} threads are overdue, the risk is Comms.",
                "domain": "Comms",
                "evidence_ids": [],
            })
        
        return bullets[:3]
    
    def _build_comms_commitments(self, client_id: str) -> Dict:
        """Build comms & commitments module per §6.6."""
        # Threads (max 5)
        threads = self._query_all("""
            SELECT 
                COALESCE(thread_id, id) as thread_id,
                subject,
                (julianday('now') - julianday(received_at)) * 24 as age_hours,
                COALESCE(expected_response_by, response_deadline) as expected_response_by,
                CASE 
                    WHEN COALESCE(expected_response_by, response_deadline) < datetime('now') THEN 'OVERDUE'
                    WHEN COALESCE(expected_response_by, response_deadline) < datetime('now', '+24 hours') THEN 'DUE'
                    ELSE 'OK'
                END as response_status
            FROM communications
            WHERE client_id = ?
            ORDER BY 
                CASE response_status WHEN 'OVERDUE' THEN 0 WHEN 'DUE' THEN 1 ELSE 2 END,
                received_at DESC
            LIMIT 5
        """, (client_id,))
        
        thread_list = []
        for t in threads:
            age = t.get('age_hours') or 0
            risk = "HIGH" if t['response_status'] == 'OVERDUE' else ("MED" if age > 24 else "LOW")
            thread_list.append({
                "thread_id": t['thread_id'],
                "subject": t.get('subject', ''),
                "age_hours": round(age, 1),
                "response_status": t['response_status'],
                "expected_response_by": t.get('expected_response_by'),
                "risk": risk,
            })
        
        # Commitments (max 5)
        commits = self._query_all("""
            SELECT id, type, text, deadline, status, confidence
            FROM commitments
            WHERE client_id = ?
            ORDER BY 
                CASE status WHEN 'broken' THEN 0 WHEN 'open' THEN 1 ELSE 2 END,
                deadline ASC NULLS LAST
            LIMIT 5
        """, (client_id,))
        
        commit_list = []
        for c in commits:
            commit_list.append({
                "commitment_id": c['id'],
                "type": c.get('type', 'request'),
                "text": (c.get('text') or '')[:100],
                "deadline": c.get('deadline'),
                "status": c.get('status', 'open'),
                "confidence": c.get('confidence') or 0.5,
            })
        
        return {
            "threads": thread_list,
            "commitments": commit_list,
        }
    
    def _build_capacity_exposure(self, client_id: str) -> Dict:
        """Build capacity/team exposure per §6.7."""
        # Get hours needed
        tasks = self._query_one("""
            SELECT SUM(COALESCE(duration_min, 60)) / 60.0 as hours_needed
            FROM tasks
            WHERE client_id = ? AND client_link_status = 'linked'
            AND status NOT IN ('done', 'completed')
        """, (client_id,))
        
        hours_needed = (tasks.get('hours_needed') or 0) if tasks else 0
        hours_available = 40.0  # Simplified
        gap = max(0, hours_needed - hours_available)
        
        # Get top constraints (max 3)
        constraints = self._query_all("""
            SELECT 
                COALESCE(lane, 'Unassigned') as name,
                SUM(COALESCE(duration_min, 60)) / 60.0 as hours
            FROM tasks
            WHERE client_id = ? AND client_link_status = 'linked'
            AND status NOT IN ('done', 'completed')
            GROUP BY lane
            ORDER BY hours DESC
            LIMIT 3
        """, (client_id,))
        
        constraint_list = []
        for c in constraints:
            lane_hours = c.get('hours', 0)
            if lane_hours > 8:  # Only if meaningful
                constraint_list.append({
                    "type": "lane",
                    "name": c['name'],
                    "gap_hours": round(max(0, lane_hours - 8), 1),
                    "driver": "workload",
                })
        
        return {
            "hours_needed": round(hours_needed, 1),
            "hours_available": round(hours_available, 1),
            "gap_hours": round(gap, 1),
            "constraints": constraint_list[:3],
        }
