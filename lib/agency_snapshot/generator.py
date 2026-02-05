"""
Agency Snapshot Generator - Produces agency_snapshot.json per Page 0/1/2/3/4 specs.

Single artifact the dashboard consumes.

Page structure:
- Page 0: Agency Control Room (tiles, narrative, exceptions)
- Page 1: Delivery Command (portfolio + selected project)
- Page 2: Client 360 (client health + relationship view)
- Page 3: Cash/AR Command (AR, aging buckets, risk scoring)
- Page 4: Comms/Commitments Command (threads, SLAs, promises, loop closure)
"""

import json
from dataclasses import asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import sqlite3

from .scoring import (
    Mode, Horizon, Confidence, Domain, ScoredItem,
    BaseScorer, ModeWeights, EligibilityGates, rank_items, clamp01
)
from .delivery import DeliveryEngine, ProjectDeliveryData, ProjectStatus, TopDriver
from .confidence import ConfidenceModel, TrustState


DB_PATH = Path(__file__).parent.parent.parent / "data" / "state.db"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "output"


class AgencySnapshotGenerator:
    """
    Generates agency_snapshot.json per Page 0 and Page 1 locked specs.
    
    Snapshot structure:
    - meta: run metadata (mode, horizon, scope)
    - trust: gate states and coverage metrics
    - narrative: first_to_break + deltas
    - tiles: delivery, cash, clients, churn_x_money, delivery_x_capacity
    - heatstrip_projects: top 25 projects
    - constraints: top 12 capacity constraints
    - exceptions: max 7 taxonomized exceptions
    - drawers: drawer data keyed by ref
    - delivery_command: Page 1 data (portfolio + selected_project)
    """
    
    # Hard caps per spec
    MAX_DELTAS = 5
    MAX_HEATSTRIP = 25
    MAX_CONSTRAINTS = 12
    MAX_EXCEPTIONS = 7
    MAX_PORTFOLIO = 25
    MAX_BREAKS_NEXT = 3
    MAX_RECENT_CHANGE = 3
    MAX_COMMS_THREADS = 5
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        mode: Mode = Mode.OPS_HEAD,
        horizon: Horizon = Horizon.THIS_WEEK,  # Weekly view is more useful for capacity planning
        scope: Dict = None
    ):
        self.db_path = db_path
        self.mode = mode
        self.horizon = horizon
        self.scope = scope or {
            "lanes": [],
            "owners": [],
            "clients": [],
            "include_internal": False,
        }
        
        self.delivery_engine = DeliveryEngine(db_path)
        self.confidence_model = ConfidenceModel(db_path)
        
        self.now = datetime.now()
        self.today = date.today()
        
        # Cache
        self._trust: Optional[TrustState] = None
        self._drawers: Dict[str, Dict] = {}
    
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
    
    def generate(self) -> Dict:
        """Generate complete agency snapshot."""
        started_at = datetime.now()
        
        # Get trust state first (needed for gating)
        self._trust = self.confidence_model.get_trust_state()
        
        # Check if blocked
        is_blocked = self.confidence_model.is_blocked(self._trust)
        
        snapshot = {
            "meta": self._build_meta(started_at),
            "trust": self._trust.to_dict(),
        }
        
        if is_blocked:
            # Only include integrity failure info
            snapshot["blocked"] = True
            snapshot["blocked_reason"] = "Data integrity check failed"
            return snapshot
        
        # Build full snapshot
        snapshot["narrative"] = self._build_narrative()
        snapshot["tiles"] = self._build_tiles()
        snapshot["heatstrip_projects"] = self._build_heatstrip()
        snapshot["constraints"] = self._build_constraints()
        snapshot["exceptions"] = self._build_exceptions()
        snapshot["delivery_command"] = self._build_delivery_command()
        snapshot["client_360"] = self._build_client_360()
        snapshot["cash_ar"] = self._build_cash_ar()
        snapshot["comms_commitments"] = self._build_comms_commitments()
        snapshot["capacity_command"] = self._build_capacity_command()
        snapshot["drawers"] = self._drawers
        
        snapshot["meta"]["finished_at"] = datetime.now().isoformat()
        snapshot["meta"]["duration_ms"] = (datetime.now() - started_at).total_seconds() * 1000
        
        return snapshot
    
    def _build_meta(self, started_at: datetime) -> Dict:
        """Build meta section per Page 0 §10."""
        return {
            "generated_at": started_at.isoformat(),
            "mode": self.mode.value,
            "horizon": self.horizon.value,
            "scope": self.scope,
            "finished_at": None,
            "duration_ms": None,
        }
    
    def _build_narrative(self) -> Dict:
        """Build narrative section: first_to_break + deltas."""
        # Collect candidates across domains
        candidates = []
        
        # Delivery candidates
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=10
        )
        for proj in portfolio:
            candidates.append(self.delivery_engine.project_to_scored_item(proj))
        
        # Client candidates
        client_items = self._get_client_risk_items()
        candidates.extend(client_items)
        
        # Capacity candidates
        capacity_items = self._get_capacity_constraint_items()
        candidates.extend(capacity_items)
        
        # Cash candidates
        cash_items = self._get_ar_risk_items()
        candidates.extend(cash_items)
        
        # Rank and pick first to break
        ranked = rank_items(candidates, self.mode, self.horizon, max_items=1)
        
        first_to_break = None
        if ranked:
            item = ranked[0]
            first_to_break = {
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "time_to_consequence_hours": item.time_to_consequence_hours,
                "top_driver": item.top_driver,
                "primary_action": self._get_primary_action(item),
                "reason": f"{self.horizon.value} | {item.domain.value} | {item.top_driver}",
                "confidence": item.confidence.value,
                "why_low": item.why_low if item.confidence == Confidence.LOW else [],
            }
            
            # Add to drawers
            self._add_drawer(item)
        
        # Build deltas
        deltas = self._get_deltas()
        
        return {
            "first_to_break": first_to_break,
            "deltas": deltas[:self.MAX_DELTAS],
        }
    
    def _build_tiles(self) -> Dict:
        """Build tiles section: 3 dials + 2 intersections."""
        partial_domains = self.confidence_model.get_partial_domains(self._trust)
        
        return {
            "delivery": self._build_delivery_tile(partial_domains),
            "cash": self._build_cash_tile(partial_domains),
            "clients": self._build_clients_tile(partial_domains),
            "churn_x_money": self._build_churn_x_money_tile(partial_domains),
            "delivery_x_capacity": self._build_delivery_x_capacity_tile(partial_domains),
        }
    
    def _build_delivery_tile(self, partial: Dict) -> Dict:
        """Build Delivery dial per Page 0 §6.1."""
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=25
        )
        
        red_count = sum(1 for p in portfolio if p.status == ProjectStatus.RED)
        yellow_count = sum(1 for p in portfolio if p.status == ProjectStatus.YELLOW)
        green_count = sum(1 for p in portfolio if p.status == ProjectStatus.GREEN)
        
        # Find highest risk
        highest_risk = None
        highest_slip = 0.0
        for proj in portfolio:
            if proj.slip_risk and proj.slip_risk.slip_risk_score > highest_slip:
                highest_slip = proj.slip_risk.slip_risk_score
                highest_risk = proj
        
        # Determine badge
        if red_count > 0:
            badge = "RED"
        elif yellow_count > 0:
            badge = "YELLOW"
        else:
            badge = "GREEN"
        
        if "delivery" in partial:
            badge = "PARTIAL"
        
        summary = f"{red_count} Red, {yellow_count} Yellow, {green_count} Green (top 25)"
        if highest_risk:
            ttc = highest_risk.time_to_slip_hours
            ttc_str = f"{ttc:.0f}h" if ttc and ttc > 0 else "overdue"
            summary += f". Highest risk: {highest_risk.name[:30]} ({ttc_str})"
        
        return {
            "badge": badge,
            "summary": summary,
            "cta": "Open Delivery Command",
            "red_count": red_count,
            "yellow_count": yellow_count,
            "green_count": green_count,
        }
    
    def _build_cash_tile(self, partial: Dict) -> Dict:
        """Build Cash dial per Page 0 §6.2."""
        # Query AR data
        ar = self._query_one("""
            SELECT 
                SUM(CASE WHEN status IN ('sent','overdue') AND paid_date IS NULL 
                    AND due_date IS NOT NULL AND client_id IS NOT NULL THEN amount ELSE 0 END) as valid_ar,
                SUM(CASE WHEN status IN ('sent','overdue') AND paid_date IS NULL 
                    AND due_date IS NOT NULL AND client_id IS NOT NULL 
                    AND julianday(date('now')) - julianday(due_date) > 60 THEN amount ELSE 0 END) as severe_ar,
                SUM(CASE WHEN status IN ('sent','overdue') AND paid_date IS NULL THEN amount ELSE 0 END) as total_ar
            FROM invoices
        """) or {}
        
        valid_ar = ar.get('valid_ar', 0) or 0
        severe_ar = ar.get('severe_ar', 0) or 0
        total_ar = ar.get('total_ar', 0) or 0
        
        severe_pct = severe_ar / max(1, valid_ar)
        
        # Badge logic
        if severe_pct >= 0.25:
            badge = "RED"
        elif severe_pct >= 0.15:
            badge = "YELLOW"
        else:
            badge = "GREEN"
        
        if "cash" in partial:
            badge = "PARTIAL"
        
        return {
            "badge": badge,
            "summary": f"Valid AR: AED {valid_ar:,.0f}. Severe (61+): AED {severe_ar:,.0f}.",
            "cta": "Open Cash Command",
            "valid_ar": valid_ar,
            "severe_ar": severe_ar,
        }
    
    def _build_clients_tile(self, partial: Dict) -> Dict:
        """Build Clients dial per Page 0 §6.3."""
        # Get at-risk clients (simplified - would need health scores)
        at_risk = self._query_all("""
            SELECT c.id, c.name, c.tier,
                   COUNT(CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN 1 END) as overdue
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            GROUP BY c.id
            HAVING overdue >= 2
            ORDER BY overdue DESC
            LIMIT 5
        """)
        
        at_risk_count = len(at_risk)
        top_client = at_risk[0]['name'] if at_risk else None
        
        # Badge logic (simplified)
        if at_risk_count >= 3:
            badge = "RED"
        elif at_risk_count >= 1:
            badge = "YELLOW"
        else:
            badge = "GREEN"
        
        if "clients" in partial:
            badge = "PARTIAL"
        
        summary = f"At-risk clients: {at_risk_count}"
        if top_client:
            summary += f" (Top: {top_client[:20]})"
        
        return {
            "badge": badge,
            "summary": summary,
            "cta": "Open Client 360",
            "at_risk_count": at_risk_count,
        }
    
    def _build_churn_x_money_tile(self, partial: Dict) -> Dict:
        """Build Churn × Money intersection per Page 0 §7.1."""
        # Clients with both churn risk and overdue AR
        clients = self._query_all("""
            SELECT 
                c.id, c.name,
                COUNT(DISTINCT CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN t.id END) as overdue_tasks,
                SUM(CASE WHEN i.status IN ('sent','overdue') AND i.paid_date IS NULL 
                    AND julianday(date('now')) - julianday(i.due_date) > 0 THEN i.amount ELSE 0 END) as overdue_ar
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            LEFT JOIN invoices i ON i.client_id = c.id
            GROUP BY c.id
            HAVING overdue_tasks >= 2 AND overdue_ar > 0
            ORDER BY overdue_ar DESC
            LIMIT 5
        """)
        
        count = len(clients)
        top_client = clients[0]['name'] if clients else None
        
        badge = "RED" if count >= 2 else "YELLOW" if count >= 1 else "GREEN"
        
        summary = f"{count} clients: churn risk + overdue AR"
        if top_client:
            summary += f". Largest: {top_client[:20]}"
        
        return {
            "badge": badge,
            "summary": summary,
            "cta": "Open Client 360",
            "top": [{"id": c['id'], "name": c['name'], "overdue_ar": c['overdue_ar']} for c in clients],
        }
    
    def _build_delivery_x_capacity_tile(self, partial: Dict) -> Dict:
        """Build Delivery × Capacity intersection per Page 0 §7.2."""
        # Projects that are Red/Yellow with capacity gap
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=25
        )
        
        impossible = []
        for proj in portfolio:
            if proj.status in (ProjectStatus.RED, ProjectStatus.YELLOW):
                if proj.slip_risk and proj.slip_risk.capacity_gap_ratio >= 0.30:
                    impossible.append(proj)
                elif proj.blocked_critical_path:
                    impossible.append(proj)
        
        count = len(impossible)
        worst = impossible[0].name if impossible else None
        
        badge = "RED" if count >= 3 else "YELLOW" if count >= 1 else "GREEN"
        
        summary = f"{count} projects impossible under current capacity"
        if worst:
            summary += f". Worst: {worst[:20]}"
        
        return {
            "badge": badge,
            "summary": summary,
            "cta": "Open Delivery Command",
            "top": [{"project_id": p.project_id, "name": p.name} for p in impossible[:5]],
        }
    
    def _build_heatstrip(self) -> List[Dict]:
        """Build project heatstrip per Page 0 Zone D (max 25)."""
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=self.MAX_HEATSTRIP
        )
        
        # Sort per Page 0 §8.2
        def sort_key(p: ProjectDeliveryData):
            status_order = {ProjectStatus.RED: 0, ProjectStatus.YELLOW: 1, ProjectStatus.GREEN: 2, ProjectStatus.PARTIAL: 1}
            slip_score = -(p.slip_risk.slip_risk_score if p.slip_risk else 0)
            ttc = p.time_to_slip_hours if p.time_to_slip_hours is not None else 99999
            conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
            return (status_order.get(p.status, 2), slip_score, ttc, conf_order.get(p.confidence, 2))
        
        portfolio.sort(key=sort_key)
        
        # Filter: only show projects that are actually urgent
        # - Overdue (time_to_slip <= 0)
        # - Due within 7 days
        # - RED/YELLOW AND within 14 days
        # Exclude projects with no due date (time_to_slip_hours is None)
        MAX_URGENT_HOURS = 168  # 7 days
        MAX_RED_HOURS = 336  # 14 days for RED/YELLOW
        urgent = [
            p for p in portfolio
            if p.time_to_slip_hours is not None and (
                p.time_to_slip_hours <= 0  # Overdue
                or p.time_to_slip_hours <= MAX_URGENT_HOURS  # Within 7 days
                or (p.status in (ProjectStatus.RED, ProjectStatus.YELLOW) and p.time_to_slip_hours <= MAX_RED_HOURS)
            )
        ]
        
        return [
            {
                "project_id": p.project_id,
                "name": p.name,
                "status": p.status.value,
                "time_to_slip_hours": p.time_to_slip_hours,
                "confidence": p.confidence.value,
            }
            for p in urgent[:self.MAX_HEATSTRIP]
        ]
    
    def _build_constraints(self) -> List[Dict]:
        """Build constraints strip per Page 0 Zone E (max 12)."""
        # Get lane/person constraints
        constraints = []
        
        # Lane constraints - only count tasks due within 14 days (exclude no-date tasks)
        lanes = self._query_all("""
            SELECT 
                t.lane,
                SUM(COALESCE(t.duration_min, 60) / 60.0) as hours_needed,
                COUNT(*) as task_count
            FROM tasks t
            WHERE t.status NOT IN ('done', 'completed', 'archived') 
            AND t.lane IS NOT NULL
            AND t.due_date IS NOT NULL
            AND t.due_date <= date('now', '+14 days')
            GROUP BY t.lane
            HAVING hours_needed > 0
            ORDER BY hours_needed DESC
            LIMIT 6
        """)
        
        for lane in lanes:
            hours_available = 40  # Default, should come from capacity config
            hours_needed = lane.get('hours_needed') or 0
            gap = hours_needed - hours_available
            # Only show meaningful gaps (> 8h), cap at 200h for display
            if gap > 8:
                constraints.append({
                    "type": "lane",
                    "id": lane['lane'],
                    "name": lane['lane'],
                    "capacity_gap_hours": min(gap, 200),
                    "time_to_consequence_hours": None,
                    "confidence": "MED",
                })
        
        # Person constraints - only count tasks due within 14 days (exclude no-date tasks)
        people = self._query_all("""
            SELECT 
                t.assignee,
                SUM(COALESCE(t.duration_min, 60) / 60.0) as hours_needed,
                MIN(t.due_date) as soonest_due
            FROM tasks t
            WHERE t.status NOT IN ('done', 'completed', 'archived') 
            AND t.assignee IS NOT NULL
            AND t.due_date IS NOT NULL
            AND t.due_date <= date('now', '+14 days')
            GROUP BY t.assignee
            HAVING hours_needed > 0
            ORDER BY hours_needed DESC
            LIMIT 6
        """)
        
        for person in people:
            hours_available = 40  # Default
            hours_needed = person.get('hours_needed') or 0
            gap = hours_needed - hours_available
            # Only show meaningful gaps (> 8h), cap at 200h
            if gap > 8:
                ttc = None
                if person.get('soonest_due'):
                    try:
                        due = datetime.fromisoformat(person['soonest_due'])
                        ttc = (due - self.now).total_seconds() / 3600
                    except:
                        pass
                
                constraints.append({
                    "type": "person",
                    "id": person['assignee'],
                    "name": person['assignee'],
                    "capacity_gap_hours": min(gap, 200),
                    "time_to_consequence_hours": ttc,
                    "confidence": "MED",
                })
        
        # Sort per Page 0 §8.3
        def sort_key(c):
            ttc = c.get('time_to_consequence_hours') or 99999
            return (-c.get('capacity_gap_hours', 0), ttc)
        
        constraints.sort(key=sort_key)
        
        return constraints[:self.MAX_CONSTRAINTS]
    
    def _build_exceptions(self) -> List[Dict]:
        """Build exceptions feed per Page 0 Zone F (max 7)."""
        candidates = []
        
        # Collect from all domains
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=10
        )
        for proj in portfolio:
            item = self.delivery_engine.project_to_scored_item(proj)
            candidates.append(item)
        
        candidates.extend(self._get_client_risk_items())
        candidates.extend(self._get_ar_risk_items())
        candidates.extend(self._get_capacity_constraint_items())
        candidates.extend(self._get_commitment_breach_items())
        candidates.extend(self._get_blocked_items())
        
        # Rank
        ranked = rank_items(candidates, self.mode, self.horizon, max_items=self.MAX_EXCEPTIONS)
        
        exceptions = []
        for idx, item in enumerate(ranked):
            exc_type = self._map_domain_to_exception_type(item.domain)
            # Compute base score, then add small variation for differentiation
            base_score = ModeWeights.compute(item, self.mode)
            # Add deterministic variation based on entity_id for tie-breaking (0.001-0.099)
            variation = (hash(item.entity_id) % 100 + 1) / 1000
            # Also factor in ranking position (higher ranked = slightly higher score)
            position_boost = (len(ranked) - idx) / (len(ranked) * 100)  # 0.01-0.07 boost
            final_score = base_score + variation + position_boost
            
            exc = {
                "type": exc_type,
                "id": item.entity_id,
                "title": item.title,
                "score": final_score,
                "confidence": item.confidence.value,
                "primary_action": self._get_primary_action(item),
                "drawer_ref": f"exc_{item.entity_id}",
            }
            exceptions.append(exc)
            self._add_drawer(item)
        
        return exceptions
    
    def _build_delivery_command(self) -> Dict:
        """Build delivery_command section for Page 1."""
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            lanes=self.scope.get("lanes"),
            owners=self.scope.get("owners"),
            clients=self.scope.get("clients"),
            limit=self.MAX_PORTFOLIO,
        )
        
        # Sort per Page 1 §7.1
        def sort_key(p: ProjectDeliveryData):
            status_order = {ProjectStatus.RED: 0, ProjectStatus.YELLOW: 1, ProjectStatus.GREEN: 2, ProjectStatus.PARTIAL: 1}
            slip_score = -(p.slip_risk.slip_risk_score if p.slip_risk else 0)
            ttc = p.time_to_slip_hours if p.time_to_slip_hours is not None else 99999
            conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
            return (status_order.get(p.status, 2), slip_score, ttc, conf_order.get(p.confidence, 2))
        
        portfolio.sort(key=sort_key)
        portfolio = portfolio[:self.MAX_PORTFOLIO]
        
        portfolio_data = []
        for p in portfolio:
            overdue_count = self.delivery_engine._count_overdue_tasks(p.project_id)
            portfolio_data.append({
                "project_id": p.project_id,
                "name": p.name,
                "status": p.status.value,
                "slip_risk_score": p.slip_risk.slip_risk_score if p.slip_risk else 0.0,
                "time_to_slip_hours": p.time_to_slip_hours,
                "top_driver": p.top_driver.value,
                "confidence": p.confidence.value,
                "why_low": p.why_low,
                "overdue_count": overdue_count,
                "total_tasks": p.total_tasks,
            })
        
        # Selected project (first one by default)
        selected_project = None
        if portfolio:
            proj = portfolio[0]
            selected_project = self._build_selected_project(proj)
        
        return {
            "portfolio": portfolio_data,
            "selected_project": selected_project,
        }
    
    def _build_selected_project(self, proj: ProjectDeliveryData) -> Dict:
        """Build selected_project section for Page 1."""
        breaks_next = self.delivery_engine.get_breaks_next(proj.project_id, self.MAX_BREAKS_NEXT)
        critical_chain = self.delivery_engine.get_critical_chain(proj.project_id)
        
        # Get comms threads - ONLY show comms that are actually related to this project/client
        # Don't show unrelated comms in project view
        project_client_id = proj.client_id if hasattr(proj, 'client_id') else None
        project_name_search = proj.name[:20] if proj.name else ''
        
        comms = []
        
        # First try: exact client_id match
        if project_client_id:
            comms = self._query_all("""
                SELECT c.id, c.subject, c.created_at, c.response_deadline as expected_response_by,
                       c.from_email, c.requires_response
                FROM communications c
                WHERE c.client_id = ?
                  AND c.requires_response = 1
                ORDER BY c.response_deadline ASC NULLS LAST, c.created_at DESC
                LIMIT ?
            """, (project_client_id, self.MAX_COMMS_THREADS))
        
        # Second try: subject contains project name (more specific)
        if not comms and project_name_search:
            comms = self._query_all("""
                SELECT id, subject, created_at, response_deadline as expected_response_by,
                       from_email, requires_response
                FROM communications
                WHERE subject LIKE '%' || ? || '%'
                  AND requires_response = 1
                ORDER BY response_deadline ASC NULLS LAST, created_at DESC
                LIMIT ?
            """, (project_name_search, self.MAX_COMMS_THREADS))
        
        # No fallback to random comms - if nothing is linked, show empty
        
        comms_threads = []
        for c in comms:
            age_hours = 0
            if c.get('created_at'):
                try:
                    created = datetime.fromisoformat(c['created_at'])
                    age_hours = (self.now - created).total_seconds() / 3600
                except:
                    pass
            
            comms_threads.append({
                "thread_id": c['id'],
                "subject": c.get('subject', ''),
                "age_hours": round(age_hours, 1),
                "expected_response_by": c.get('expected_response_by'),
                "risk": "HIGH" if age_hours > 48 else "MED" if age_hours > 24 else "LOW",
            })
        
        # Recent change (simplified - would need delta tracking)
        recent_change = []
        
        return {
            "project_id": proj.project_id,
            "header": {
                "owner": proj.owner,
                "lane": proj.lane,
                "client": proj.client,
                "type": proj.project_type,
                "is_internal": proj.is_internal,
            },
            "slip": {
                "slip_risk_score": proj.slip_risk.slip_risk_score if proj.slip_risk else 0.0,
                "time_to_slip_hours": proj.time_to_slip_hours,
                "top_drivers": proj.slip_risk.top_drivers if proj.slip_risk else [],
            },
            "breaks_next": [
                {
                    "text": b.text,
                    "ttc_hours": b.ttc_hours,
                    "driver": b.driver,
                    "primary_action": b.primary_action,
                }
                for b in breaks_next
            ],
            "critical_chain": {
                "nodes": [
                    {"type": n.node_type, "id": n.node_id, "label": n.label, "ttc_hours": n.ttc_hours}
                    for n in critical_chain.nodes
                ] if critical_chain else [],
                "unlock_action": critical_chain.unlock_action if critical_chain else None,
            } if critical_chain else None,
            "capacity": {
                "hours_needed": proj.hours_needed,
                "hours_available": proj.hours_available,
                "gap_hours": proj.hours_needed - proj.hours_available,
                "top_constraint": {"type": "lane", "name": proj.lane} if proj.lane else None,
            },
            "comms_threads": comms_threads,
            "recent_change": recent_change[:self.MAX_RECENT_CHANGE],
            "actions": self._get_project_actions(proj),
        }
    
    def _build_client_360(self) -> Dict:
        """Build client_360 section per Page 10 LOCKED SPEC."""
        from .client360_page10 import Client360Page10Engine, Mode as C360Mode, Horizon as C360Horizon
        
        # Map modes
        c360_mode = C360Mode.OPS_HEAD
        if self.mode.value == "Co-Founder":
            c360_mode = C360Mode.CO_FOUNDER
        elif self.mode.value == "Artist":
            c360_mode = C360Mode.ARTIST
            
        c360_horizon = C360Horizon.TODAY
        if self.horizon.value == "NOW":
            c360_horizon = C360Horizon.NOW
        elif self.horizon.value == "THIS_WEEK":
            c360_horizon = C360Horizon.THIS_WEEK
        
        engine = Client360Page10Engine(
            db_path=self.db_path,
            mode=c360_mode,
            horizon=c360_horizon,
        )
        
        # Pass trust state
        engine.data_integrity = self._trust.data_integrity if self._trust else True
        
        return engine.generate()
    
    def _build_cash_ar(self) -> Dict:
        """Build cash_ar section per Page 12 LOCKED SPEC."""
        from .cash_ar_page12 import CashARPage12Engine, Mode as CashMode, Horizon as CashHorizon
        
        # Map modes (they have same values but are different enum classes)
        cash_mode = CashMode.OPS_HEAD
        if self.mode.value == "Co-Founder":
            cash_mode = CashMode.CO_FOUNDER
        elif self.mode.value == "Artist":
            cash_mode = CashMode.ARTIST
            
        cash_horizon = CashHorizon.TODAY
        if self.horizon.value == "NOW":
            cash_horizon = CashHorizon.NOW
        elif self.horizon.value == "THIS_WEEK":
            cash_horizon = CashHorizon.THIS_WEEK
        
        engine = CashARPage12Engine(
            db_path=self.db_path,
            mode=cash_mode,
            horizon=cash_horizon,
        )
        
        # Pass trust state
        engine.data_integrity = self._trust.data_integrity if self._trust else True
        
        return engine.generate()
    
    def _build_comms_commitments(self) -> Dict:
        """Build comms_commitments section per Page 11 LOCKED SPEC."""
        from .comms_commitments_page11 import CommsCommitmentsPage11Engine, Mode as CCMode, Horizon as CCHorizon
        
        # Map modes
        cc_mode = CCMode.OPS_HEAD
        if self.mode.value == "Co-Founder":
            cc_mode = CCMode.CO_FOUNDER
        elif self.mode.value == "Artist":
            cc_mode = CCMode.ARTIST
            
        cc_horizon = CCHorizon.TODAY
        if self.horizon.value == "NOW":
            cc_horizon = CCHorizon.NOW
        elif self.horizon.value == "THIS_WEEK":
            cc_horizon = CCHorizon.THIS_WEEK
        
        engine = CommsCommitmentsPage11Engine(
            db_path=self.db_path,
            mode=cc_mode,
            horizon=cc_horizon,
        )
        
        # Pass trust state
        engine.data_integrity = self._trust.data_integrity if self._trust else True
        
        return engine.generate()
    
    def _build_capacity_command(self) -> Dict:
        """Build capacity_command section per Page 7 LOCKED SPEC."""
        from .capacity_command_page7 import CapacityCommandPage7Engine, Mode as CapMode, Horizon as CapHorizon
        
        # Map modes
        cap_mode = CapMode.OPS_HEAD
        if self.mode.value == "Co-Founder":
            cap_mode = CapMode.CO_FOUNDER
        elif self.mode.value == "Artist":
            cap_mode = CapMode.ARTIST
            
        cap_horizon = CapHorizon.TODAY
        if self.horizon.value == "NOW":
            cap_horizon = CapHorizon.NOW
        elif self.horizon.value == "THIS_WEEK":
            cap_horizon = CapHorizon.THIS_WEEK
        
        engine = CapacityCommandPage7Engine(
            db_path=self.db_path,
            mode=cap_mode,
            horizon=cap_horizon,
        )
        
        # Pass trust state
        engine.data_integrity = self._trust.data_integrity if self._trust else True
        
        return engine.generate()
    
    def _compute_comms_link_rate(self) -> float:
        """Compute rate of communications linked to clients."""
        row = self._query_one("""
            SELECT 
                COUNT(*) as total,
                COUNT(client_id) as linked
            FROM communications
            WHERE received_at IS NOT NULL OR created_at IS NOT NULL
        """)
        
        if row and row.get('total', 0) > 0:
            return (row['linked'] / row['total']) * 100
        return 100.0
    
    # Helper methods
    
    def _get_client_risk_items(self) -> List[ScoredItem]:
        """Get client risk items as ScoredItems."""
        items = []
        
        at_risk = self._query_all("""
            SELECT c.id, c.name, c.tier,
                   COUNT(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('done', 'completed') THEN 1 END) as overdue,
                   MIN(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('done', 'completed') 
                       THEN julianday(date('now')) - julianday(t.due_date) END) as oldest_overdue_days
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            GROUP BY c.id
            HAVING overdue >= 2
            ORDER BY overdue DESC
            LIMIT 10
        """)
        
        for client in at_risk:
            # Churn risk based on overdue count and age
            overdue = client.get('overdue', 0)
            oldest_days = client.get('oldest_overdue_days') or 0
            
            # Higher risk for more overdue items and older overdues
            churn_risk = clamp01(overdue * 0.12 + oldest_days * 0.02)
            
            # Impact is based on churn risk, minimum 0.5 if at risk
            impact = max(0.5, churn_risk)
            
            # Urgency based on oldest overdue
            urgency = clamp01(oldest_days / 30) if oldest_days else 0.5
            
            items.append(ScoredItem(
                entity_type="client",
                entity_id=client['id'],
                domain=Domain.CLIENTS,
                impact=impact,
                urgency=urgency,
                controllability=0.8,
                confidence=Confidence.MED,
                time_to_consequence_hours=-oldest_days * 24 if oldest_days else None,  # Negative = overdue
                compounding_damage=True,
                title=f"Client at risk: {client['name']}",
                top_driver=f"{overdue} overdue deliverables",
            ))
        
        return items
    
    def _get_ar_risk_items(self) -> List[ScoredItem]:
        """Get AR risk items as ScoredItems."""
        items = []
        
        severe = self._query_all("""
            SELECT id, external_id, amount, client_name, due_date,
                   julianday(date('now')) - julianday(due_date) as days_overdue
            FROM invoices
            WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
            AND due_date IS NOT NULL
            AND julianday(date('now')) - julianday(due_date) > 60
            ORDER BY amount DESC
            LIMIT 10
        """)
        
        for inv in severe:
            days = inv.get('days_overdue', 0)
            amount = inv.get('amount', 0)
            
            items.append(ScoredItem(
                entity_type="ar",
                entity_id=inv['id'],
                domain=Domain.MONEY,
                impact=clamp01(amount / 50000),  # Scale by typical invoice size
                urgency=clamp01(days / 90),
                controllability=0.7,
                confidence=Confidence.HIGH,
                title=f"AR severe: {inv.get('external_id') or inv['id'][:8]}",
                top_driver=f"AED {amount:,.0f} from {inv.get('client_name', 'Unknown')} ({int(days)}d)",
                ar_severe=True,
            ))
        
        return items
    
    def _get_capacity_constraint_items(self) -> List[ScoredItem]:
        """Get capacity constraint items as ScoredItems."""
        items = []
        
        lanes = self._query_all("""
            SELECT lane, SUM(duration_min / 60.0) as hours_needed
            FROM tasks
            WHERE status NOT IN ('done', 'completed') AND lane IS NOT NULL
            GROUP BY lane
            HAVING hours_needed > 40
            ORDER BY hours_needed DESC
            LIMIT 5
        """)
        
        for lane in lanes:
            gap = (lane.get('hours_needed') or 0) - 40
            
            items.append(ScoredItem(
                entity_type="lane",
                entity_id=lane['lane'],
                domain=Domain.CAPACITY,
                impact=clamp01(gap / 20),
                urgency=0.6,
                controllability=0.6,
                confidence=Confidence.MED,
                title=f"Capacity gap: {lane['lane']}",
                top_driver=f"−{gap:.0f}h capacity",
                capacity_blocker_today=gap > 8,
            ))
        
        return items
    
    def _get_commitment_breach_items(self) -> List[ScoredItem]:
        """Get commitment breach items as ScoredItems."""
        items = []
        
        breaches = self._query_all("""
            SELECT id, text, deadline, client_id
            FROM commitments
            WHERE status NOT IN ('fulfilled', 'closed') AND deadline IS NOT NULL
            AND deadline < datetime('now')
            ORDER BY deadline ASC
            LIMIT 5
        """)
        
        for commit in breaches:
            items.append(ScoredItem(
                entity_type="commitment",
                entity_id=commit['id'],
                domain=Domain.COMMITMENT,
                impact=0.6,
                urgency=1.0,  # Already breached
                controllability=0.5,
                confidence=Confidence.MED,
                time_to_consequence_hours=0,
                title=f"Commitment breach: {commit.get('text', '')[:40]}",
                top_driver="Deadline passed",
            ))
        
        return items
    
    def _get_blocked_items(self) -> List[ScoredItem]:
        """Get blocked waiting items as ScoredItems."""
        items = []
        
        blocked = self._query_all("""
            SELECT id, title, blockers, due_date, project_id
            FROM tasks
            WHERE status NOT IN ('done', 'completed') 
            AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'
            ORDER BY due_date ASC NULLS LAST
            LIMIT 5
        """)
        
        for task in blocked:
            ttc = None
            if task.get('due_date'):
                try:
                    due = datetime.fromisoformat(task['due_date'])
                    ttc = (due - self.now).total_seconds() / 3600
                except:
                    pass
            
            # Parse blocker reason
            blocker_reason = task.get('blockers') or 'Unknown blocker'
            if blocker_reason.startswith('['):
                try:
                    import json
                    blockers_list = json.loads(blocker_reason)
                    blocker_reason = blockers_list[0] if blockers_list else 'Unknown blocker'
                except:
                    pass
            
            items.append(ScoredItem(
                entity_type="task",
                entity_id=task['id'],
                domain=Domain.BLOCKED,
                impact=0.5,
                urgency=BaseScorer.compute_urgency_from_ttc(ttc),
                controllability=0.4,
                confidence=Confidence.HIGH,
                time_to_consequence_hours=ttc,
                dependency_breaker=True,
                title=f"Blocked: {task['title'][:40]}",
                top_driver=blocker_reason[:30],
            ))
        
        return items
    
    def _get_deltas(self) -> List[Dict]:
        """Get deltas since last refresh."""
        from .deltas import DeltaTracker
        
        tracker = DeltaTracker(self.db_path)
        
        # Build a minimal current snapshot for comparison
        current = {
            'tiles': self._build_tiles() if hasattr(self, '_tiles_cache') else {},
            'heatstrip_projects': self._build_heatstrip() if not hasattr(self, '_heatstrip_cache') else self._heatstrip_cache,
            'constraints': self._build_constraints() if not hasattr(self, '_constraints_cache') else self._constraints_cache,
        }
        
        return tracker.compute_deltas(current)
    
    def _get_primary_action(self, item: ScoredItem) -> Dict:
        """Get primary action for an item."""
        # Determine risk level
        risk = "auto"
        label = "View"
        payload = {"entity_type": item.entity_type, "entity_id": item.entity_id}
        
        if item.domain == Domain.MONEY:
            risk = "propose"
            label = "Send reminder"
        elif item.domain == Domain.CLIENTS:
            risk = "propose"
            label = "Schedule touchpoint"
        elif item.domain in (Domain.BLOCKED, Domain.DELIVERY):
            risk = "auto"
            label = "Open context"
        
        return {"risk": risk, "label": label, "payload": payload}
    
    def _get_project_actions(self, proj: ProjectDeliveryData) -> List[Dict]:
        """Get actions for a project."""
        actions = []
        
        if proj.blocked_critical_path:
            actions.append({
                "risk": "auto",
                "label": "View blockers",
                "payload": {"project_id": proj.project_id, "filter": "blocked"},
            })
        
        if proj.status in (ProjectStatus.RED, ProjectStatus.YELLOW):
            actions.append({
                "risk": "propose",
                "label": "Escalate to client",
                "payload": {"project_id": proj.project_id, "action": "escalate"},
            })
        
        return actions
    
    def _add_drawer(self, item: ScoredItem):
        """Add drawer data for an item."""
        ref = f"exc_{item.entity_id}"
        self._drawers[ref] = {
            "summary": f"{item.title}. Driver: {item.top_driver}.",
            "evidence": [],
            "actions": [self._get_primary_action(item)],
            "reason": f"{self.horizon.value} | {item.domain.value} | {item.top_driver}",
            "why_low": item.why_low if item.confidence == Confidence.LOW else [],
        }
    
    def _map_domain_to_exception_type(self, domain: Domain) -> str:
        """Map domain to exception type per spec."""
        mapping = {
            Domain.DELIVERY: "delivery",
            Domain.MONEY: "money",
            Domain.CLIENTS: "churn",
            Domain.CAPACITY: "capacity",
            Domain.COMMITMENT: "commitment",
            Domain.BLOCKED: "blocked",
            Domain.UNKNOWN: "unknown",
            Domain.COMMS: "commitment",
        }
        return mapping.get(domain, "unknown")
    
    def save(self, snapshot: Dict, path: Path = None) -> Path:
        """Save snapshot to file and history."""
        path = path or OUTPUT_PATH / "agency_snapshot.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(snapshot, f, indent=2, default=str)
        
        # Save to history for delta tracking
        from .deltas import DeltaTracker
        tracker = DeltaTracker(self.db_path)
        tracker.save_snapshot_to_history(snapshot)
        
        return path


def generate_snapshot(
    mode: str = "Ops Head",
    horizon: str = "TODAY",
    scope: Dict = None
) -> Dict:
    """Convenience function to generate snapshot."""
    mode_enum = Mode(mode) if mode in [m.value for m in Mode] else Mode.OPS_HEAD
    horizon_enum = Horizon(horizon) if horizon in [h.value for h in Horizon] else Horizon.TODAY
    
    generator = AgencySnapshotGenerator(
        mode=mode_enum,
        horizon=horizon_enum,
        scope=scope or {},
    )
    
    snapshot = generator.generate()
    generator.save(snapshot)
    
    return snapshot
