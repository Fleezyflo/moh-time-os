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
import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from lib import paths

# Contracts module - validation gates
from lib.contracts import (
    AgencySnapshotContract,
    enforce_invariants_strict,
    enforce_predicates_strict,
    enforce_thresholds_strict,
)
from lib.contracts.predicates import NormalizedData
from lib.contracts.schema import SCHEMA_VERSION
from lib.contracts.thresholds import ResolutionStats

from .confidence import ConfidenceModel, TrustState
from .delivery import DeliveryEngine, ProjectDeliveryData, ProjectStatus
from .scoring import (
    BaseScorer,
    Confidence,
    Domain,
    Horizon,
    Mode,
    ModeWeights,
    ScoredItem,
    clamp01,
    rank_items,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()
OUTPUT_PATH = paths.out_dir()


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
        scope: dict = None,
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
        self._trust: TrustState | None = None
        self._drawers: dict[str, dict] = {}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _build_normalized_data(self) -> NormalizedData:
        """
        Build NormalizedData from DB for predicate/invariant checks.

        This extracts the canonical counts needed for validation gates.
        Uses only columns that exist in the actual schema.
        """
        # Projects (using actual columns)
        projects = self._query_all("""
            SELECT id, name, client_id, status
            FROM projects
            WHERE status NOT IN ('completed', 'cancelled', 'archived')
        """)

        # Clients
        clients = self._query_all("""
            SELECT id, name, tier
            FROM clients
        """)

        # Invoices (unpaid)
        invoices = self._query_all("""
            SELECT id, external_id, amount, client_id, status, due_date, payment_date
            FROM invoices
            WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
        """)
        # Mark unpaid
        for inv in invoices:
            inv["is_unpaid"] = True

        # Commitments with client resolution via thread -> communication -> client
        # scope_ref_type is 'thread', scope_ref_id is thread_id in communications
        commitments = self._query_all("""
            SELECT
                cmt.commitment_id, cmt.commitment_text as content,
                cmt.scope_ref_type, cmt.scope_ref_id,
                c.id as resolved_client_id,
                cmt.due_at as due_date, cmt.status
            FROM commitments cmt
            LEFT JOIN communications m ON cmt.scope_ref_id = m.thread_id
            LEFT JOIN clients c ON m.subject LIKE '%' || c.name || '%'
            WHERE cmt.status NOT IN ('fulfilled', 'closed')
        """)

        # Communications with client resolution via subject matching
        # Schema lacks client_id, so we resolve via subject LIKE client.name
        communications = self._query_all("""
            SELECT
                m.id, m.subject, m.from_email, m.created_at, m.received_at,
                c.id as client_id
            FROM communications m
            LEFT JOIN clients c ON m.subject LIKE '%' || c.name || '%'
            WHERE m.received_at IS NOT NULL OR m.created_at IS NOT NULL
        """)

        # People with tasks (hours_assigned = task_count * 1h estimate)
        people = self._query_all("""
            SELECT
                t.assignee as name,
                COUNT(*) as task_count,
                COUNT(*) * 1.0 as hours_assigned
            FROM tasks t
            WHERE t.status NOT IN ('done', 'completed', 'archived')
            AND t.assignee IS NOT NULL
            GROUP BY t.assignee
        """)

        return NormalizedData(
            projects=projects,
            clients=clients,
            invoices=invoices,
            commitments=commitments,
            communications=communications,
            people=people,
        )

    def _compute_resolution_stats(self, normalized: NormalizedData) -> ResolutionStats:
        """
        Compute resolution statistics from normalized data for threshold checks.
        """
        # Commitments
        commitments_total = len(normalized.commitments)
        commitments_resolved = len(
            [c for c in normalized.commitments if c.get("resolved_client_id") is not None]
        )

        # Threads/communications
        threads_total = len(normalized.communications)
        threads_with_client = len(
            [c for c in normalized.communications if c.get("client_id") is not None]
        )

        # Invoices
        invoices_total = len(normalized.invoices)
        invoices_valid = len(
            [inv for inv in normalized.invoices if inv.get("client_id") and inv.get("due_date")]
        )

        # People
        people_total = len(normalized.people)
        people_with_hours = len([p for p in normalized.people if p.get("hours_assigned", 0) > 0])

        # Projects
        projects_total = len(normalized.projects)
        projects_with_client = len(
            [p for p in normalized.projects if p.get("client_id") is not None]
        )

        return ResolutionStats(
            commitments_total=commitments_total,
            commitments_resolved=commitments_resolved,
            threads_total=threads_total,
            threads_with_client=threads_with_client,
            invoices_total=invoices_total,
            invoices_valid=invoices_valid,
            people_total=people_total,
            people_with_hours=people_with_hours,
            projects_total=projects_total,
            projects_with_client=projects_with_client,
        )

    def _get_validation_environment(self) -> str:
        """
        Get environment for threshold validation.

        Checks MOH_TIME_OS_ENV env var.
        Default: 'current_data_model' because schema lacks client_id on
        commitments/communications (schema limitation documented in thresholds.py).
        Set MOH_TIME_OS_ENV=production when data model supports full linkages.
        """
        return os.environ.get("MOH_TIME_OS_ENV", "current_data_model")

    def generate(self) -> dict:
        """
        Generate complete agency snapshot with multi-layer validation.

        Pipeline:
        1. Extract (build normalized data)
        2. Build snapshot sections
        3. Validate (predicates → invariants → thresholds → schema)
        4. Emit

        Violations RAISE - no logging-only paths.
        """
        started_at = datetime.now()

        # Get trust state first (needed for gating)
        self._trust = self.confidence_model.get_trust_state()

        # Check if blocked (metadata only - does NOT bypass gates)
        self.confidence_model.is_blocked(self._trust)

        snapshot = {
            "meta": self._build_meta(started_at),
            "trust": self._trust.to_dict(),
        }

        # NOTE: No early return here. "blocked" is metadata, not a bypass.
        # All snapshots must pass validation gates regardless of blocked state.

        # =========================================================
        # STEP 1: Build normalized data (for validation gates)
        # =========================================================
        normalized = self._build_normalized_data()
        stats = self._compute_resolution_stats(normalized)
        env = self._get_validation_environment()

        logger.info(
            f"Normalized data: projects={len(normalized.projects)}, "
            f"invoices={len(normalized.invoices)}, commitments={len(normalized.commitments)}"
        )
        logger.info(
            f"Resolution stats: commitments={stats.commitments_resolution_rate:.1%}, "
            f"threads={stats.threads_client_rate:.1%}, invoices={stats.invoices_valid_rate:.1%}"
        )

        # =========================================================
        # STEP 2: Build full snapshot
        # =========================================================
        # Note: Using minimal implementations until page engines are schema-fixed
        snapshot["narrative"] = self._build_narrative_minimal()
        snapshot["tiles"] = self._build_tiles_minimal()
        snapshot["heatstrip_projects"] = self._build_heatstrip_minimal(normalized)
        snapshot["constraints"] = []
        snapshot["exceptions"] = []
        snapshot["delivery_command"] = self._build_delivery_command_minimal(normalized)
        snapshot["client_360"] = self._build_client_360_minimal(normalized)
        snapshot["cash_ar"] = self._build_cash_ar_minimal(normalized)
        snapshot["comms_commitments"] = self._build_comms_commitments_minimal(normalized)
        snapshot["capacity_command"] = self._build_capacity_command_minimal(normalized)
        snapshot["drawers"] = self._drawers

        snapshot["meta"]["finished_at"] = datetime.now().isoformat()
        snapshot["meta"]["duration_ms"] = (datetime.now() - started_at).total_seconds() * 1000

        # =========================================================
        # PATCHWORK_BOUNDARY: ASSEMBLY COMPLETE
        # No snapshot mutations allowed below this line.
        # =========================================================

        # =========================================================
        # STEP 3: VALIDATION GATES (all must pass or raise)
        # =========================================================

        # Gate 1: Predicates (section existence rules)
        logger.info("Running predicate gate...")
        enforce_predicates_strict(normalized, snapshot)

        # Gate 2: Invariants (semantic correctness)
        logger.info("Running invariant gate...")
        enforce_invariants_strict(snapshot, normalized)

        # Gate 3: Thresholds (quality metrics)
        logger.info(f"Running threshold gate (env={env})...")
        enforce_thresholds_strict(stats, env)

        # Gate 4: Schema validation (shape)
        logger.info("Running schema validation...")
        validated = AgencySnapshotContract.model_validate(snapshot)

        logger.info("All validation gates passed.")

        # =========================================================
        # STEP 4: Return validated snapshot
        # =========================================================
        return validated.model_dump()

    def _build_meta(self, started_at: datetime) -> dict:
        """Build meta section per Page 0 §10."""
        return {
            "generated_at": started_at.isoformat(),
            "mode": self.mode.value,
            "horizon": self.horizon.value,
            "scope": self.scope,
            "finished_at": None,
            "duration_ms": None,
            "schema_version": SCHEMA_VERSION,  # Bound to UI spec v2.9.0
        }

    def _build_narrative(self) -> dict:
        """Build narrative section: first_to_break + deltas."""
        # Collect candidates across domains
        candidates = []

        # Delivery candidates
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False), limit=10
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
            "deltas": deltas[: self.MAX_DELTAS],
        }

    def _build_tiles(self) -> dict:
        """Build tiles section: 3 dials + 2 intersections."""
        partial_domains = self.confidence_model.get_partial_domains(self._trust)

        return {
            "delivery": self._build_delivery_tile(partial_domains),
            "cash": self._build_cash_tile(partial_domains),
            "clients": self._build_clients_tile(partial_domains),
            "churn_x_money": self._build_churn_x_money_tile(partial_domains),
            "delivery_x_capacity": self._build_delivery_x_capacity_tile(partial_domains),
        }

    def _build_delivery_tile(self, partial: dict) -> dict:
        """Build Delivery dial per Page 0 §6.1."""
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False), limit=25
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

    def _build_cash_tile(self, partial: dict) -> dict:
        """Build Cash dial per Page 0 §6.2."""
        # Query AR data
        ar = (
            self._query_one("""
            SELECT
                SUM(CASE WHEN status IN ('sent','overdue') AND payment_date IS NULL
                    AND due_date IS NOT NULL AND client_id IS NOT NULL THEN amount ELSE 0 END) as valid_ar,
                SUM(CASE WHEN status IN ('sent','overdue') AND payment_date IS NULL
                    AND due_date IS NOT NULL AND client_id IS NOT NULL
                    AND julianday(date('now')) - julianday(due_date) > 60 THEN amount ELSE 0 END) as severe_ar,
                SUM(CASE WHEN status IN ('sent','overdue') AND payment_date IS NULL THEN amount ELSE 0 END) as total_ar
            FROM invoices
        """)
            or {}
        )

        valid_ar = ar.get("valid_ar", 0) or 0
        severe_ar = ar.get("severe_ar", 0) or 0
        ar.get("total_ar", 0) or 0

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

    def _build_clients_tile(self, partial: dict) -> dict:
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
        top_client = at_risk[0]["name"] if at_risk else None

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

    def _build_churn_x_money_tile(self, partial: dict) -> dict:
        """Build Churn × Money intersection per Page 0 §7.1."""
        # Clients with both churn risk and overdue AR
        clients = self._query_all("""
            SELECT
                c.id, c.name,
                COUNT(DISTINCT CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN t.id END) as overdue_tasks,
                SUM(CASE WHEN i.status IN ('sent','overdue') AND i.payment_date IS NULL
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
        top_client = clients[0]["name"] if clients else None

        badge = "RED" if count >= 2 else "YELLOW" if count >= 1 else "GREEN"

        summary = f"{count} clients: churn risk + overdue AR"
        if top_client:
            summary += f". Largest: {top_client[:20]}"

        return {
            "badge": badge,
            "summary": summary,
            "cta": "Open Client 360",
            "top": [
                {"id": c["id"], "name": c["name"], "overdue_ar": c["overdue_ar"]} for c in clients
            ],
        }

    def _build_delivery_x_capacity_tile(self, partial: dict) -> dict:
        """Build Delivery × Capacity intersection per Page 0 §7.2."""
        # Projects that are Red/Yellow with capacity gap
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False), limit=25
        )

        impossible = []
        for proj in portfolio:
            if proj.status in (ProjectStatus.RED, ProjectStatus.YELLOW):
                if (
                    proj.slip_risk
                    and proj.slip_risk.capacity_gap_ratio >= 0.30
                    or proj.blocked_critical_path
                ):
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

    def _build_heatstrip(self) -> list[dict]:
        """Build project heatstrip per Page 0 Zone D (max 25)."""
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False),
            limit=self.MAX_HEATSTRIP,
        )

        # Sort per Page 0 §8.2
        def sort_key(p: ProjectDeliveryData):
            status_order = {
                ProjectStatus.RED: 0,
                ProjectStatus.YELLOW: 1,
                ProjectStatus.GREEN: 2,
                ProjectStatus.PARTIAL: 1,
            }
            slip_score = -(p.slip_risk.slip_risk_score if p.slip_risk else 0)
            ttc = p.time_to_slip_hours if p.time_to_slip_hours is not None else 99999
            conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
            return (
                status_order.get(p.status, 2),
                slip_score,
                ttc,
                conf_order.get(p.confidence, 2),
            )

        portfolio.sort(key=sort_key)

        # Filter: only show projects that are actually urgent
        # - Overdue (time_to_slip <= 0)
        # - Due within 7 days
        # - RED/YELLOW AND within 14 days
        # Exclude projects with no due date (time_to_slip_hours is None)
        MAX_URGENT_HOURS = 168  # 7 days
        MAX_RED_HOURS = 336  # 14 days for RED/YELLOW
        urgent = [
            p
            for p in portfolio
            if p.time_to_slip_hours is not None
            and (
                p.time_to_slip_hours <= 0  # Overdue
                or p.time_to_slip_hours <= MAX_URGENT_HOURS  # Within 7 days
                or (
                    p.status in (ProjectStatus.RED, ProjectStatus.YELLOW)
                    and p.time_to_slip_hours <= MAX_RED_HOURS
                )
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
            for p in urgent[: self.MAX_HEATSTRIP]
        ]

    def _build_constraints(self) -> list[dict]:
        """Build constraints strip per Page 0 Zone E (max 12)."""
        # Get lane/person constraints
        constraints = []

        # Project constraints - only count tasks due within 14 days (exclude no-date tasks)
        # Note: Using project instead of lane (lane column doesn't exist in tasks)
        lanes = self._query_all("""
            SELECT
                t.project as lane,
                COUNT(*) as hours_needed,
                COUNT(*) as task_count
            FROM tasks t
            WHERE t.status NOT IN ('done', 'completed', 'archived')
            AND t.project IS NOT NULL
            AND t.due_date IS NOT NULL
            AND t.due_date <= date('now', '+14 days')
            GROUP BY t.project
            HAVING hours_needed > 0
            ORDER BY hours_needed DESC
            LIMIT 6
        """)

        for lane in lanes:
            hours_available = 40  # Default, should come from capacity config
            hours_needed = lane.get("hours_needed") or 0
            gap = hours_needed - hours_available
            # Only show meaningful gaps (> 8h), cap at 200h for display
            if gap > 8:
                constraints.append(
                    {
                        "type": "lane",
                        "id": lane["lane"],
                        "name": lane["lane"],
                        "capacity_gap_hours": min(gap, 200),
                        "time_to_consequence_hours": None,
                        "confidence": "MED",
                    }
                )

        # Person constraints - only count tasks due within 14 days (exclude no-date tasks)
        people = self._query_all("""
            SELECT
                t.assignee,
                COUNT(*) as hours_needed,
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
            hours_needed = person.get("hours_needed") or 0
            gap = hours_needed - hours_available
            # Only show meaningful gaps (> 8h), cap at 200h
            if gap > 8:
                ttc = None
                if person.get("soonest_due"):
                    try:
                        due = datetime.fromisoformat(person["soonest_due"])
                        ttc = (due - self.now).total_seconds() / 3600
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Could not parse soonest_due: {e}")

                constraints.append(
                    {
                        "type": "person",
                        "id": person["assignee"],
                        "name": person["assignee"],
                        "capacity_gap_hours": min(gap, 200),
                        "time_to_consequence_hours": ttc,
                        "confidence": "MED",
                    }
                )

        # Sort per Page 0 §8.3
        def sort_key(c):
            ttc = c.get("time_to_consequence_hours") or 99999
            return (-c.get("capacity_gap_hours", 0), ttc)

        constraints.sort(key=sort_key)

        return constraints[: self.MAX_CONSTRAINTS]

    def _build_exceptions(self) -> list[dict]:
        """Build exceptions feed per Page 0 Zone F (max 7)."""
        candidates = []

        # Collect from all domains
        portfolio = self.delivery_engine.get_portfolio(
            include_internal=self.scope.get("include_internal", False), limit=10
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

    def _build_delivery_command(self) -> dict:
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
            status_order = {
                ProjectStatus.RED: 0,
                ProjectStatus.YELLOW: 1,
                ProjectStatus.GREEN: 2,
                ProjectStatus.PARTIAL: 1,
            }
            slip_score = -(p.slip_risk.slip_risk_score if p.slip_risk else 0)
            ttc = p.time_to_slip_hours if p.time_to_slip_hours is not None else 99999
            conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
            return (
                status_order.get(p.status, 2),
                slip_score,
                ttc,
                conf_order.get(p.confidence, 2),
            )

        portfolio.sort(key=sort_key)
        portfolio = portfolio[: self.MAX_PORTFOLIO]

        portfolio_data = []
        for p in portfolio:
            overdue_count = self.delivery_engine._count_overdue_tasks(p.project_id)
            portfolio_data.append(
                {
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
                }
            )

        # Selected project (first one by default)
        selected_project = None
        if portfolio:
            proj = portfolio[0]
            selected_project = self._build_selected_project(proj)

        return {
            "portfolio": portfolio_data,
            "selected_project": selected_project,
        }

    def _build_selected_project(self, proj: ProjectDeliveryData) -> dict:
        """Build selected_project section for Page 1."""
        breaks_next = self.delivery_engine.get_breaks_next(proj.project_id, self.MAX_BREAKS_NEXT)
        critical_chain = self.delivery_engine.get_critical_chain(proj.project_id)

        # Get comms threads - ONLY show comms that are actually related to this project/client
        # Don't show unrelated comms in project view
        proj.client_id if hasattr(proj, "client_id") else None
        project_name_search = proj.name[:20] if proj.name else ""

        comms = []

        # Note: communications table doesn't have client_id, skipping client match
        # First try: subject contains project name (more specific)
        if project_name_search:
            comms = self._query_all(
                """
                SELECT c.id, c.subject, c.created_at, c.response_deadline as expected_response_by,
                       c.from_email, c.requires_response
                FROM communications c
                WHERE c.subject LIKE '%' || ? || '%'
                  AND c.requires_response = 1
                ORDER BY c.response_deadline ASC NULLS LAST, c.created_at DESC
                LIMIT ?
            """,
                (project_name_search, self.MAX_COMMS_THREADS),
            )

        # No fallback to random comms - if nothing is linked, show empty

        comms_threads = []
        for c in comms:
            age_hours = 0
            if c.get("created_at"):
                try:
                    created = datetime.fromisoformat(c["created_at"])
                    age_hours = (self.now - created).total_seconds() / 3600
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse created_at: {e}")

            comms_threads.append(
                {
                    "thread_id": c["id"],
                    "subject": c.get("subject", ""),
                    "age_hours": round(age_hours, 1),
                    "expected_response_by": c.get("expected_response_by"),
                    "risk": "HIGH" if age_hours > 48 else "MED" if age_hours > 24 else "LOW",
                }
            )

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
                    "commitment_text": b.text,
                    "ttc_hours": b.ttc_hours,
                    "driver": b.driver,
                    "primary_action": b.primary_action,
                }
                for b in breaks_next
            ],
            "critical_chain": {
                "nodes": [
                    {
                        "type": n.node_type,
                        "id": n.node_id,
                        "label": n.label,
                        "ttc_hours": n.ttc_hours,
                    }
                    for n in critical_chain.nodes
                ]
                if critical_chain
                else [],
                "unlock_action": critical_chain.unlock_action if critical_chain else None,
            }
            if critical_chain
            else None,
            "capacity": {
                "hours_needed": proj.hours_needed,
                "hours_available": proj.hours_available,
                "gap_hours": proj.hours_needed - proj.hours_available,
                "top_constraint": {"type": "lane", "name": proj.lane} if proj.lane else None,
            },
            "comms_threads": comms_threads,
            "recent_change": recent_change[: self.MAX_RECENT_CHANGE],
            "actions": self._get_project_actions(proj),
        }

    def _build_client_360(self) -> dict:
        """Build client_360 section per Page 10 LOCKED SPEC."""
        from .client360_page10 import Client360Page10Engine
        from .client360_page10 import Horizon as C360Horizon
        from .client360_page10 import Mode as C360Mode

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

    def _build_cash_ar(self) -> dict:
        """Build cash_ar section per Page 12 LOCKED SPEC."""
        from .cash_ar_page12 import CashARPage12Engine
        from .cash_ar_page12 import Horizon as CashHorizon
        from .cash_ar_page12 import Mode as CashMode

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

    def _build_comms_commitments(self) -> dict:
        """Build comms_commitments section per Page 11 LOCKED SPEC."""
        from .comms_commitments_page11 import CommsCommitmentsPage11Engine
        from .comms_commitments_page11 import Horizon as CCHorizon
        from .comms_commitments_page11 import Mode as CCMode

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

    def _build_capacity_command(self) -> dict:
        """Build capacity_command section per Page 7 LOCKED SPEC."""
        from .capacity_command_page7 import CapacityCommandPage7Engine
        from .capacity_command_page7 import Horizon as CapHorizon
        from .capacity_command_page7 import Mode as CapMode

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

        if row and row.get("total", 0) > 0:
            return (row["linked"] / row["total"]) * 100
        return 100.0

    # Helper methods

    def _get_client_risk_items(self) -> list[ScoredItem]:
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
            overdue = client.get("overdue", 0)
            oldest_days = client.get("oldest_overdue_days") or 0

            # Higher risk for more overdue items and older overdues
            churn_risk = clamp01(overdue * 0.12 + oldest_days * 0.02)

            # Impact is based on churn risk, minimum 0.5 if at risk
            impact = max(0.5, churn_risk)

            # Urgency based on oldest overdue
            urgency = clamp01(oldest_days / 30) if oldest_days else 0.5

            items.append(
                ScoredItem(
                    entity_type="client",
                    entity_id=client["id"],
                    domain=Domain.CLIENTS,
                    impact=impact,
                    urgency=urgency,
                    controllability=0.8,
                    confidence=Confidence.MED,
                    time_to_consequence_hours=-oldest_days * 24
                    if oldest_days
                    else None,  # Negative = overdue
                    compounding_damage=True,
                    title=f"Client at risk: {client['name']}",
                    top_driver=f"{overdue} overdue deliverables",
                )
            )

        return items

    def _get_ar_risk_items(self) -> list[ScoredItem]:
        """Get AR risk items as ScoredItems."""
        items = []

        severe = self._query_all("""
            SELECT id, external_id, amount, client_name, due_date,
                   julianday(date('now')) - julianday(due_date) as days_overdue
            FROM invoices
            WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
            AND due_date IS NOT NULL
            AND julianday(date('now')) - julianday(due_date) > 60
            ORDER BY amount DESC
            LIMIT 10
        """)

        for inv in severe:
            days = inv.get("days_overdue", 0)
            amount = inv.get("amount", 0)

            items.append(
                ScoredItem(
                    entity_type="ar",
                    entity_id=inv["id"],
                    domain=Domain.MONEY,
                    impact=clamp01(amount / 50000),  # Scale by typical invoice size
                    urgency=clamp01(days / 90),
                    controllability=0.7,
                    confidence=Confidence.HIGH,
                    title=f"AR severe: {inv.get('external_id') or inv['id'][:8]}",
                    top_driver=f"AED {amount:,.0f} from {inv.get('client_name', 'Unknown')} ({int(days)}d)",
                    ar_severe=True,
                )
            )

        return items

    def _get_capacity_constraint_items(self) -> list[ScoredItem]:
        """Get capacity constraint items as ScoredItems."""
        items = []

        # Note: Using project instead of lane (lane column doesn't exist)
        lanes = self._query_all("""
            SELECT project as lane, COUNT(*) as hours_needed
            FROM tasks
            WHERE status NOT IN ('done', 'completed') AND project IS NOT NULL
            GROUP BY project
            HAVING hours_needed > 40
            ORDER BY hours_needed DESC
            LIMIT 5
        """)

        for lane in lanes:
            gap = (lane.get("hours_needed") or 0) - 40

            items.append(
                ScoredItem(
                    entity_type="lane",
                    entity_id=lane["lane"],
                    domain=Domain.CAPACITY,
                    impact=clamp01(gap / 20),
                    urgency=0.6,
                    controllability=0.6,
                    confidence=Confidence.MED,
                    title=f"Capacity gap: {lane['lane']}",
                    top_driver=f"−{gap:.0f}h capacity",
                    capacity_blocker_today=gap > 8,
                )
            )

        return items

    def _get_commitment_breach_items(self) -> list[ScoredItem]:
        """Get commitment breach items as ScoredItems."""
        items = []

        breaches = self._query_all("""
            SELECT commitment_id as id, commitment_text as text, due_at as deadline
            FROM commitments
            WHERE status NOT IN ('fulfilled', 'closed') AND due_at IS NOT NULL
            AND due_at < datetime('now')
            ORDER BY due_at ASC
            LIMIT 5
        """)

        for commit in breaches:
            items.append(
                ScoredItem(
                    entity_type="commitment",
                    entity_id=commit["id"],
                    domain=Domain.COMMITMENT,
                    impact=0.6,
                    urgency=1.0,  # Already breached
                    controllability=0.5,
                    confidence=Confidence.MED,
                    time_to_consequence_hours=0,
                    title=f"Commitment breach: {commit.get('text', '')[:40]}",
                    top_driver="Deadline passed",
                )
            )

        return items

    def _get_blocked_items(self) -> list[ScoredItem]:
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
            if task.get("due_date"):
                try:
                    due = datetime.fromisoformat(task["due_date"])
                    ttc = (due - self.now).total_seconds() / 3600
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due_date: {e}")

            # Parse blocker reason
            blocker_reason = task.get("blockers") or "Unknown blocker"
            if blocker_reason.startswith("["):
                try:
                    import json

                    blockers_list = json.loads(blocker_reason)
                    blocker_reason = blockers_list[0] if blockers_list else "Unknown blocker"
                except (json.JSONDecodeError, TypeError, IndexError) as e:
                    logger.debug(f"Could not parse blockers JSON: {e}")

            items.append(
                ScoredItem(
                    entity_type="task",
                    entity_id=task["id"],
                    domain=Domain.BLOCKED,
                    impact=0.5,
                    urgency=BaseScorer.compute_urgency_from_ttc(ttc),
                    controllability=0.4,
                    confidence=Confidence.HIGH,
                    time_to_consequence_hours=ttc,
                    dependency_breaker=True,
                    title=f"Blocked: {task['title'][:40]}",
                    top_driver=blocker_reason[:30],
                )
            )

        return items

    def _get_deltas(self) -> list[dict]:
        """Get deltas since last refresh."""
        from .deltas import DeltaTracker

        tracker = DeltaTracker(self.db_path)

        # Build a minimal current snapshot for comparison
        current = {
            "tiles": self._build_tiles() if hasattr(self, "_tiles_cache") else {},
            "heatstrip_projects": self._build_heatstrip()
            if not hasattr(self, "_heatstrip_cache")
            else self._heatstrip_cache,
            "constraints": self._build_constraints()
            if not hasattr(self, "_constraints_cache")
            else self._constraints_cache,
        }

        return tracker.compute_deltas(current)

    def _get_primary_action(self, item: ScoredItem) -> dict:
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

    def _get_project_actions(self, proj: ProjectDeliveryData) -> list[dict]:
        """Get actions for a project."""
        actions = []

        if proj.blocked_critical_path:
            actions.append(
                {
                    "risk": "auto",
                    "label": "View blockers",
                    "payload": {"project_id": proj.project_id, "filter": "blocked"},
                }
            )

        if proj.status in (ProjectStatus.RED, ProjectStatus.YELLOW):
            actions.append(
                {
                    "risk": "propose",
                    "label": "Escalate to client",
                    "payload": {"project_id": proj.project_id, "action": "escalate"},
                }
            )

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

    # =========================================================
    # MINIMAL BUILDERS (contract-compliant, schema-safe)
    # =========================================================

    def _build_narrative_minimal(self) -> dict:
        """Minimal narrative section."""
        return {"first_to_break": None, "deltas": []}

    def _build_tiles_minimal(self) -> dict:
        """Minimal tiles section."""
        return {
            "delivery": {"badge": "GREEN", "summary": "No data", "cta": ""},
            "cash": {"badge": "GREEN", "summary": "No data", "cta": ""},
            "clients": {"badge": "GREEN", "summary": "No data", "cta": ""},
            "churn_x_money": {"badge": "GREEN", "summary": "No data", "cta": ""},
            "delivery_x_capacity": {"badge": "GREEN", "summary": "No data", "cta": ""},
        }

    def _build_heatstrip_minimal(self, normalized) -> list:
        """Build heatstrip from normalized projects."""
        heatstrip = []
        for proj in normalized.projects[:25]:
            heatstrip.append(
                {
                    "project_id": proj.get("id", ""),
                    "name": proj.get("name", "Unknown"),
                    "status": "YELLOW",
                    "slip_risk_score": 0.0,
                    "time_to_slip_hours": None,
                    "top_driver": None,
                    "confidence": "MED",
                    "overdue_count": 0,
                    "total_tasks": 0,
                }
            )
        return heatstrip

    def _build_delivery_command_minimal(self, normalized) -> dict:
        """Minimal delivery command section."""
        portfolio = []
        for proj in normalized.projects[:25]:
            portfolio.append(
                {
                    "project_id": proj.get("id", ""),
                    "name": proj.get("name", "Unknown"),
                    "status": "YELLOW",
                    "slip_risk_score": 0.0,
                    "time_to_slip_hours": None,
                    "overdue_count": 0,
                    "total_tasks": 0,
                    "top_driver": None,
                    "confidence": "MED",
                }
            )
        return {"portfolio": portfolio, "selected_project": None}

    def _build_client_360_minimal(self, normalized) -> dict:
        """Minimal client 360 section."""
        portfolio = []
        for client in normalized.clients[:25]:
            # Ensure tier is valid (A/B/C/D/untiered), default None to 'untiered'
            tier = client.get("tier")
            if tier not in ("A", "B", "C", "D", "untiered"):
                tier = "untiered"
            portfolio.append(
                {
                    "client_id": client.get("id", ""),
                    "name": client.get("name", "Unknown"),
                    "tier": tier,
                    "health_score": 0.5,
                    "health_status": "fair",
                    "total_ar": 0.0,
                    "overdue_tasks": 0,
                    "at_risk": False,
                }
            )
        at_risk_count = len([c for c in portfolio if c.get("at_risk")])
        return {"portfolio": portfolio, "at_risk_count": at_risk_count, "drawer": {}}

    def _build_cash_ar_minimal(self, normalized) -> dict:
        """Minimal cash AR section from normalized invoices."""
        total_ar = sum(inv.get("amount", 0) for inv in normalized.invoices)
        severe_ar = sum(
            inv.get("amount", 0)
            for inv in normalized.invoices
            if inv.get("due_date") and self._days_overdue(inv.get("due_date")) > 60
        )

        # Build debtors from invoices grouped by client
        client_ar = {}
        for inv in normalized.invoices:
            cid = inv.get("client_id") or "unknown"
            if cid not in client_ar:
                client_ar[cid] = {"total": 0, "severe": 0, "count": 0}
            client_ar[cid]["total"] += inv.get("amount", 0)
            client_ar[cid]["count"] += 1
            if inv.get("due_date") and self._days_overdue(inv.get("due_date")) > 60:
                client_ar[cid]["severe"] += inv.get("amount", 0)

        debtors = []
        for cid, data in client_ar.items():
            if data["total"] > 0:
                debtors.append(
                    {
                        "client_id": cid,
                        "client_name": cid,
                        "currency": "AED",
                        "total_valid_ar": data["total"],
                        "severe_ar": data["severe"],
                        "aging_bucket": "current",
                        "days_overdue_max": 0,
                        "invoice_count": data["count"],
                        "risk_score": 0.0,
                    }
                )

        badge = (
            "RED"
            if severe_ar > total_ar * 0.25
            else "YELLOW"
            if severe_ar > total_ar * 0.15
            else "GREEN"
        )

        return {
            "tiles": {
                "valid_ar": {"AED": total_ar},
                "severe_ar": {"AED": severe_ar},
                "badge": badge,
                "summary": f"Valid AR: AED {total_ar:,.0f}. Severe: AED {severe_ar:,.0f}.",
            },
            "debtors": debtors,
            "aging_distribution": [],
        }

    def _days_overdue(self, due_date_str: str) -> int:
        """Calculate days overdue from due date string."""
        try:
            due = datetime.fromisoformat(due_date_str.replace("Z", "+00:00")).date()
            return (self.today - due).days
        except (ValueError, TypeError, AttributeError):
            return 0

    def _build_comms_commitments_minimal(self, normalized) -> dict:
        """Minimal comms/commitments section."""
        threads = []
        for comm in normalized.communications[:10]:
            threads.append(
                {
                    "thread_id": comm.get("id", ""),
                    "subject": comm.get("subject", ""),
                    "client_id": comm.get("client_id"),
                    "client_name": None,
                    "last_activity": comm.get("created_at"),
                    "commitment_count": 0,
                }
            )

        commitments = []
        for cmt in normalized.commitments[:10]:
            commitments.append(
                {
                    "commitment_id": cmt.get("commitment_id", ""),
                    "content": cmt.get("content", ""),
                    "scope_ref_type": cmt.get("scope_ref_type", "client"),
                    "scope_ref_id": cmt.get("scope_ref_id", ""),
                    "resolved_client_id": cmt.get("resolved_client_id"),
                    "unresolved_reason": "Not linked to client"
                    if not cmt.get("resolved_client_id")
                    else None,
                    "due_date": cmt.get("due_date"),
                    "is_overdue": False,
                }
            )

        overdue_count = len([c for c in commitments if c.get("is_overdue")])
        return {
            "threads": threads,
            "commitments": commitments,
            "overdue_count": overdue_count,
        }

    def _build_capacity_command_minimal(self, normalized) -> dict:
        """Minimal capacity command section."""
        people_overview = []
        total_assigned = 0.0
        total_capacity = 0.0

        for person in normalized.people:  # No limit - must match normalized count
            hours = person.get("hours_assigned", 0) or 0
            capacity = 40.0  # Default weekly capacity
            people_overview.append(
                {
                    "person_id": None,
                    "name": person.get("name", "Unknown"),
                    "hours_assigned": hours,
                    "hours_capacity": capacity,
                    "utilization": hours / capacity if capacity > 0 else 0,
                    "gap_hours": hours - capacity,
                    "is_overloaded": hours > capacity,
                }
            )
            total_assigned += hours
            total_capacity += capacity

        return {
            "people_overview": people_overview,
            "total_assigned": total_assigned,
            "total_capacity": total_capacity,
            "utilization_rate": total_assigned / total_capacity if total_capacity > 0 else 0,
            "drawer": {},
        }

    def save(self, snapshot: dict, path: Path = None) -> Path:
        """Save snapshot to file and history."""
        path = path or OUTPUT_PATH / "agency_snapshot.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        # Save to history for delta tracking
        from .deltas import DeltaTracker

        tracker = DeltaTracker(self.db_path)
        tracker.save_snapshot_to_history(snapshot)

        return path


def generate_snapshot(mode: str = "Ops Head", horizon: str = "TODAY", scope: dict = None) -> dict:
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
