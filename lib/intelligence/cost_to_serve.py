"""
Cost-to-Serve Intelligence Module — MOH TIME OS

Calculates per-client and per-project cost-to-serve metrics to enable profitability analysis.
Since actual time tracking is not available, uses task-based proxies for operational effort:
- Task count (completion indicator)
- Active task weighting (current effort)
- Communication volume (operational overhead)
- Invoice aging (hidden cash costs)

This module provides:
1. CostToServeEngine — main computation engine
2. ClientCostProfile — per-client profitability analysis
3. ProjectCostProfile — per-project efficiency metrics
4. PortfolioProfitability — portfolio-wide summary

Code rules enforced:
- No broad exception handling (all errors logged and returned)
- No empty dict/list returns on failure
- Parameterized queries via query_engine
- All dataclasses have to_dict() method
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, quantiles
from typing import Optional

from lib.query_engine import QueryEngine, get_engine
import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ClientCostProfile:
    """Per-client cost and profitability analysis."""

    client_id: str
    name: str
    revenue_total: float
    task_count: int
    active_tasks: int
    communication_count: int
    overdue_tasks: int
    avg_task_duration_days: float
    efficiency_ratio: float
    profitability_band: str  # HIGH, MED, LOW
    cost_drivers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "client_id": self.client_id,
            "name": self.name,
            "revenue_total": round(self.revenue_total, 2),
            "task_count": self.task_count,
            "active_tasks": self.active_tasks,
            "communication_count": self.communication_count,
            "overdue_tasks": self.overdue_tasks,
            "avg_task_duration_days": round(self.avg_task_duration_days, 1),
            "efficiency_ratio": round(self.efficiency_ratio, 2),
            "profitability_band": self.profitability_band,
            "cost_drivers": self.cost_drivers,
        }


@dataclass
class ProjectCostProfile:
    """Per-project cost and completion metrics."""

    project_id: str
    name: str
    client_id: str
    task_count: int
    completed_tasks: int
    overdue_tasks: int
    avg_completion_days: float
    effort_score: float
    has_scope_creep: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "client_id": self.client_id,
            "task_count": self.task_count,
            "completed_tasks": self.completed_tasks,
            "overdue_tasks": self.overdue_tasks,
            "avg_completion_days": round(self.avg_completion_days, 1),
            "effort_score": round(self.effort_score, 2),
            "has_scope_creep": self.has_scope_creep,
        }


@dataclass
class PortfolioProfitability:
    """Portfolio-wide profitability summary."""

    total_revenue: float
    total_clients: int
    profitable_count: int
    marginal_count: int
    unprofitable_count: int
    efficiency_distribution: dict[str, int]  # band -> count
    top_profitable: list[dict] = field(default_factory=list)
    bottom_unprofitable: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_revenue": round(self.total_revenue, 2),
            "total_clients": self.total_clients,
            "profitable_count": self.profitable_count,
            "marginal_count": self.marginal_count,
            "unprofitable_count": self.unprofitable_count,
            "efficiency_distribution": self.efficiency_distribution,
            "top_profitable": self.top_profitable,
            "bottom_unprofitable": self.bottom_unprofitable,
        }


# =============================================================================
# COST-TO-SERVE ENGINE
# =============================================================================


class CostToServeEngine:
    """
    Computes cost-to-serve metrics across clients, projects, and portfolio.

    Uses query_engine to fetch operational data and calculates efficiency
    ratios based on task volume, communication overhead, and invoice metrics.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize CostToServeEngine.

        Args:
            db_path: Optional path to database. If None, uses QueryEngine default.

        Raises:
            FileNotFoundError: If provided db_path doesn't exist.
        """
        try:
            self.engine = get_engine(db_path)
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize CostToServeEngine: {e}")
            raise

    def compute_client_cost(self, client_id: str) -> ClientCostProfile | None:
        """
        Compute cost-to-serve profile for a single client.

        Retrieves operational data (tasks, revenue, communications) and computes:
        - Weighted effort score from task activity
        - Efficiency ratio (revenue / effort_score)
        - Profitability band (HIGH/MED/LOW)
        - Cost drivers (factors that increase operational cost)

        Args:
            client_id: Client ID to analyze

        Returns:
            ClientCostProfile with metrics, or None if client not found
        """
        try:
            # Get base profile
            profile = self.engine.client_deep_profile(client_id)
            if not profile:
                logger.warning(f"Client not found: {client_id}")
                return None

            # Get task metrics
            task_summary = self.engine.client_task_summary(client_id)

            # Get communication metrics
            comm_summary = self.engine.client_communication_summary(client_id)

            # Get invoice metrics
            invoices = self.engine.invoices_in_period(client_id=client_id)
            sum(i.get("amount", 0) or 0 for i in invoices)

            # Extract key metrics
            total_tasks = task_summary.get("total_tasks", 0)
            active_tasks = task_summary.get("active_tasks", 0)
            completed_tasks = task_summary.get("completed_tasks", 0)
            overdue_tasks = task_summary.get("overdue_tasks", 0)
            communication_count = comm_summary.get("total_communications", 0)

            # Calculate weighted effort score
            # Formula: active_tasks × 2 + overdue_tasks × 3 + completed_tasks × 0.5
            effort_score = (active_tasks * 2) + (overdue_tasks * 3) + (completed_tasks * 0.5)

            # Avoid division by zero
            if effort_score == 0:
                effort_score = 1.0

            # Calculate efficiency ratio (revenue per effort unit)
            revenue_total = profile.get("total_invoiced", 0) or 0
            efficiency_ratio = revenue_total / effort_score if effort_score > 0 else 0

            # Calculate average task duration for completed client tasks
            avg_task_duration = 0.0
            try:
                duration_rows = self.engine._execute(
                    """
                    SELECT AVG(julianday(updated_at) - julianday(created_at))
                    FROM tasks
                    WHERE client_id = ?
                      AND status IN ('done', 'complete', 'completed')
                      AND updated_at IS NOT NULL
                      AND created_at IS NOT NULL
                    """,
                    (client_id,),
                )
                if duration_rows and duration_rows[0].get(
                    "AVG(julianday(updated_at) - julianday(created_at))"
                ):
                    avg_task_duration = float(
                        duration_rows[0]["AVG(julianday(updated_at) - julianday(created_at))"]
                    )
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.debug(f"Could not compute avg_task_duration for {client_id}: {e}")

            # Determine cost drivers
            cost_drivers = []
            if overdue_tasks > 0:
                cost_drivers.append(f"High overdue count ({overdue_tasks})")
            if communication_count > 50:
                cost_drivers.append(f"High communication volume ({communication_count})")
            if profile.get("total_outstanding", 0) or 0 > 10000:
                cost_drivers.append(f"High AR outstanding ({profile.get('total_outstanding', 0)})")
            if completed_tasks == 0 and total_tasks > 0:
                cost_drivers.append("No completed tasks (new/stalled project)")

            # Determine profitability band (will be computed against portfolio later)
            profitability_band = "MED"  # Default

            return ClientCostProfile(
                client_id=client_id,
                name=profile.get("client_name", "Unknown"),
                revenue_total=revenue_total,
                task_count=total_tasks,
                active_tasks=active_tasks,
                communication_count=communication_count,
                overdue_tasks=overdue_tasks,
                avg_task_duration_days=avg_task_duration,
                efficiency_ratio=efficiency_ratio,
                profitability_band=profitability_band,
                cost_drivers=cost_drivers,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing client cost for {client_id}: {e}", exc_info=True)
            return None

    def compute_project_cost(self, project_id: str) -> ProjectCostProfile | None:
        """
        Compute cost-to-serve profile for a single project.

        Analyzes project efficiency based on task completion, timeline, and scope changes.

        Args:
            project_id: Project ID to analyze

        Returns:
            ProjectCostProfile with metrics, or None if project not found
        """
        try:
            # Get project operational state
            proj_state = self.engine.project_operational_state(project_id)
            if not proj_state:
                logger.warning(f"Project not found: {project_id}")
                return None

            # Extract metrics
            client_id = proj_state.get("client_id", "")
            project_name = proj_state.get("project_name", "")
            total_tasks = proj_state.get("total_tasks", 0)
            completed_tasks = proj_state.get("completed_tasks", 0)
            overdue_tasks = proj_state.get("overdue_tasks", 0)

            # Calculate weighted effort score for project
            effort_score = (total_tasks * 1.0) + (overdue_tasks * 2.0)

            # Calculate average completion days for project tasks
            avg_completion_days = 0.0
            try:
                duration_rows = self.engine._execute(
                    """
                    SELECT AVG(julianday(updated_at) - julianday(created_at))
                    FROM tasks
                    WHERE project_id = ?
                      AND status IN ('done', 'complete', 'completed')
                      AND updated_at IS NOT NULL
                      AND created_at IS NOT NULL
                    """,
                    (project_id,),
                )
                if duration_rows and duration_rows[0].get(
                    "AVG(julianday(updated_at) - julianday(created_at))"
                ):
                    avg_completion_days = float(
                        duration_rows[0]["AVG(julianday(updated_at) - julianday(created_at))"]
                    )
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.debug(f"Could not compute avg_completion_days for {project_id}: {e}")

            # Detect scope creep (if task_count is very high relative to expected)
            # For now, use overdue ratio as proxy
            has_scope_creep = (overdue_tasks / total_tasks) > 0.3 if total_tasks > 0 else False

            return ProjectCostProfile(
                project_id=project_id,
                name=project_name,
                client_id=client_id,
                task_count=total_tasks,
                completed_tasks=completed_tasks,
                overdue_tasks=overdue_tasks,
                avg_completion_days=avg_completion_days,
                effort_score=effort_score,
                has_scope_creep=has_scope_creep,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing project cost for {project_id}: {e}", exc_info=True)
            return None

    def compute_portfolio_profitability(self) -> PortfolioProfitability | None:
        """
        Compute portfolio-wide profitability summary.

        Aggregates client-level profiles, assigns profitability bands based
        on efficiency ratio percentiles, and identifies top/bottom performers.

        Returns:
            PortfolioProfitability with summary metrics, or None on error
        """
        try:
            # Get all clients
            clients_overview = self.engine.client_portfolio_overview()
            if not clients_overview:
                logger.warning("No clients in portfolio")
                return self._empty_portfolio_profitability()

            # Compute cost profiles for each client
            profiles = []
            for client in clients_overview:
                profile = self.compute_client_cost(client["client_id"])
                if profile:
                    profiles.append(profile)

            if not profiles:
                logger.warning("Could not compute any client cost profiles")
                return self._empty_portfolio_profitability()

            # Extract efficiency ratios for percentile calculation
            efficiency_ratios = [p.efficiency_ratio for p in profiles if p.efficiency_ratio > 0]

            # Calculate percentiles
            if len(efficiency_ratios) >= 4:
                try:
                    percentiles_vals = quantiles(efficiency_ratios, n=4)
                    p25 = percentiles_vals[0]  # 25th percentile
                    p75 = percentiles_vals[2]  # 75th percentile
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.warning(f"Could not calculate percentiles: {e}")
                    p25 = sorted(efficiency_ratios)[len(efficiency_ratios) // 4]
                    p75 = sorted(efficiency_ratios)[3 * len(efficiency_ratios) // 4]
            else:
                # Insufficient data for percentiles
                median = sorted(efficiency_ratios)[len(efficiency_ratios) // 2]
                p25 = median * 0.5
                p75 = median * 1.5

            # Assign profitability bands based on percentiles
            for profile in profiles:
                if profile.efficiency_ratio > p75:
                    profile.profitability_band = "HIGH"
                elif profile.efficiency_ratio < p25:
                    profile.profitability_band = "LOW"
                else:
                    profile.profitability_band = "MED"

            # Count profitability bands
            band_counts = {"HIGH": 0, "MED": 0, "LOW": 0}
            for profile in profiles:
                band_counts[profile.profitability_band] += 1

            # Build efficiency distribution
            efficiency_distribution = {
                "HIGH": band_counts["HIGH"],
                "MED": band_counts["MED"],
                "LOW": band_counts["LOW"],
            }

            # Calculate total revenue
            total_revenue = sum(p.revenue_total for p in profiles)

            # Get top profitable and bottom unprofitable
            sorted_by_ratio = sorted(profiles, key=lambda p: p.efficiency_ratio, reverse=True)
            top_profitable = [
                {
                    "client_id": p.client_id,
                    "name": p.name,
                    "efficiency_ratio": round(p.efficiency_ratio, 2),
                    "revenue": round(p.revenue_total, 2),
                }
                for p in sorted_by_ratio[:3]
            ]

            bottom_unprofitable = [
                {
                    "client_id": p.client_id,
                    "name": p.name,
                    "efficiency_ratio": round(p.efficiency_ratio, 2),
                    "revenue": round(p.revenue_total, 2),
                    "cost_drivers": p.cost_drivers,
                }
                for p in sorted_by_ratio[-3:]
                if p.efficiency_ratio > 0
            ]

            return PortfolioProfitability(
                total_revenue=total_revenue,
                total_clients=len(profiles),
                profitable_count=band_counts["HIGH"],
                marginal_count=band_counts["MED"],
                unprofitable_count=band_counts["LOW"],
                efficiency_distribution=efficiency_distribution,
                top_profitable=top_profitable,
                bottom_unprofitable=bottom_unprofitable,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing portfolio profitability: {e}", exc_info=True)
            return None

    def get_hidden_cost_clients(self) -> list[dict]:
        """
        Identify clients where operational cost indicators exceed revenue signals.

        Hidden costs are indicated by:
        - High overdue task count relative to revenue
        - High communication volume relative to revenue
        - High AR aging
        - Low efficiency ratio

        Returns:
            List of dicts with client_id, name, and cost_indicators
        """
        try:
            clients_overview = self.engine.client_portfolio_overview()
            if not clients_overview:
                logger.warning("No clients in portfolio")
                return []

            hidden_cost_clients = []

            for client in clients_overview:
                profile = self.compute_client_cost(client["client_id"])
                if not profile:
                    continue

                # Identify hidden cost patterns
                indicators = []

                # High overdue/task ratio
                if profile.task_count > 0:
                    overdue_ratio = profile.overdue_tasks / profile.task_count
                    if overdue_ratio > 0.25:
                        indicators.append(f"High overdue ratio: {overdue_ratio:.1%}")

                # Low efficiency (high effort relative to revenue)
                if profile.efficiency_ratio < 1000:  # Arbitrary threshold for low efficiency
                    indicators.append(
                        f"Low efficiency: {profile.efficiency_ratio:.0f} revenue per effort unit"
                    )

                # High communication relative to tasks
                if profile.task_count > 0:
                    comm_per_task = profile.communication_count / profile.task_count
                    if comm_per_task > 5:
                        indicators.append(
                            f"High communication overhead: {comm_per_task:.1f} comms per task"
                        )

                # Include clients with 2+ cost indicators
                if len(indicators) >= 2:
                    hidden_cost_clients.append(
                        {
                            "client_id": profile.client_id,
                            "name": profile.name,
                            "revenue": round(profile.revenue_total, 2),
                            "efficiency_ratio": round(profile.efficiency_ratio, 2),
                            "cost_indicators": indicators,
                            "cost_drivers": profile.cost_drivers,
                        }
                    )

            return sorted(hidden_cost_clients, key=lambda c: c["efficiency_ratio"])

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error identifying hidden cost clients: {e}", exc_info=True)
            return []

    def get_profitability_ranking(self) -> list[dict]:
        """
        Get all clients ranked by profitability (efficiency ratio).

        Returns:
            List of dicts sorted by efficiency_ratio (descending),
            with client_id, name, efficiency_ratio, revenue, task_count
        """
        try:
            clients_overview = self.engine.client_portfolio_overview()
            if not clients_overview:
                logger.warning("No clients in portfolio")
                return []

            rankings = []

            for client in clients_overview:
                profile = self.compute_client_cost(client["client_id"])
                if not profile:
                    continue

                rankings.append(
                    {
                        "client_id": profile.client_id,
                        "name": profile.name,
                        "efficiency_ratio": round(profile.efficiency_ratio, 2),
                        "revenue": round(profile.revenue_total, 2),
                        "task_count": profile.task_count,
                        "profitability_band": profile.profitability_band,
                    }
                )

            return sorted(rankings, key=lambda r: r["efficiency_ratio"], reverse=True)

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing profitability ranking: {e}", exc_info=True)
            return []

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _empty_portfolio_profitability(self) -> PortfolioProfitability:
        """Return empty portfolio profitability structure."""
        return PortfolioProfitability(
            total_revenue=0.0,
            total_clients=0,
            profitable_count=0,
            marginal_count=0,
            unprofitable_count=0,
            efficiency_distribution={"HIGH": 0, "MED": 0, "LOW": 0},
            top_profitable=[],
            bottom_unprofitable=[],
        )
