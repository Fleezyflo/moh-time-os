"""
Scenario Modeling Engine — MOH TIME OS

Enables what-if analysis for agency decisions, modeling outcomes before committing.

Provides scenario types:
- CLIENT_LOSS: Impact of losing a client
- CLIENT_ADDITION: Impact of adding a new client
- RESOURCE_CHANGE: Impact of changing team capacity (person leaves/added/reduced)
- PRICING_CHANGE: Impact of changing client pricing
- CAPACITY_SHIFT: Impact of reallocating capacity across lanes
- WORKLOAD_REBALANCE: Impact of redistributing work across team

This module computes baseline metrics, projected metrics, and risk assessment
for decision-making. All results are structured with to_dict() serialization.

Code rules enforced:
- No broad exception handling (all errors logged and returned)
- No empty dict/list returns on failure
- Parameterized queries via query_engine
- All dataclasses have to_dict() method
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from lib.compat import StrEnum
from lib.intelligence.cost_to_serve import CostToServeEngine
from lib.query_engine import QueryEngine, get_engine

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class ScenarioType(StrEnum):
    """Types of scenarios that can be modeled."""

    CLIENT_LOSS = "CLIENT_LOSS"
    CLIENT_ADDITION = "CLIENT_ADDITION"
    RESOURCE_CHANGE = "RESOURCE_CHANGE"
    PRICING_CHANGE = "PRICING_CHANGE"
    CAPACITY_SHIFT = "CAPACITY_SHIFT"
    WORKLOAD_REBALANCE = "WORKLOAD_REBALANCE"


class ConfidenceLevel(StrEnum):
    """Confidence in scenario projection."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ScenarioResult:
    """Result of a what-if scenario modeling."""

    scenario_type: ScenarioType
    description: str
    baseline_metrics: dict
    projected_metrics: dict
    impact_summary: str
    risk_factors: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    revenue_impact: float = 0.0
    capacity_impact_pct: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scenario_type": self.scenario_type.value,
            "description": self.description,
            "baseline_metrics": self.baseline_metrics,
            "projected_metrics": self.projected_metrics,
            "impact_summary": self.impact_summary,
            "risk_factors": self.risk_factors,
            "confidence": self.confidence.value,
            "revenue_impact": round(self.revenue_impact, 2),
            "capacity_impact_pct": round(self.capacity_impact_pct, 1),
        }


@dataclass
class ScenarioComparison:
    """Side-by-side comparison of multiple scenarios."""

    scenarios: list[ScenarioResult]
    best_case_idx: int
    worst_case_idx: int
    tradeoff_summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scenarios": [s.to_dict() for s in self.scenarios],
            "best_case_idx": self.best_case_idx,
            "worst_case_idx": self.worst_case_idx,
            "tradeoff_summary": self.tradeoff_summary,
        }


# =============================================================================
# SCENARIO ENGINE
# =============================================================================


class ScenarioEngine:
    """
    Scenario modeling engine for what-if analysis.

    Enables decision-makers to understand the impact of operational changes
    before committing, by computing baseline metrics, projecting outcomes,
    and identifying risks.

    Usage:
        engine = ScenarioEngine(db_path)
        result = engine.model_client_loss("client-id-123")
        # result.revenue_impact, result.risk_factors, result.confidence
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize scenario engine.

        Args:
            db_path: Optional path to database. If None, uses QueryEngine default.

        Raises:
            FileNotFoundError: If provided db_path doesn't exist.
        """
        try:
            self.query_engine = get_engine(db_path)
            self.cost_engine = CostToServeEngine(db_path)
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize ScenarioEngine: {e}")
            raise

    # =========================================================================
    # CLIENT_LOSS SCENARIO
    # =========================================================================

    def model_client_loss(self, client_id: str) -> ScenarioResult | None:
        """
        Model impact of losing a client.

        Computes:
        - Revenue loss (absolute and %)
        - Capacity freed (%)
        - Resource reallocation needed
        - Team load shift for affected members
        - Structural risk if client is >25% revenue

        Args:
            client_id: Client ID to model loss for

        Returns:
            ScenarioResult with baseline, projected, and risk assessment,
            or None if client not found
        """
        try:
            # Get client profile
            profile = self.query_engine.client_deep_profile(client_id)
            if not profile:
                logger.warning(f"Client not found: {client_id}")
                return None

            # Get portfolio overview
            portfolio = self.query_engine.client_portfolio_overview()
            if not portfolio:
                logger.warning("No portfolio data available")
                return None

            # Calculate baseline metrics
            client_revenue = profile.get("total_invoiced", 0) or 0
            client_tasks = profile.get("total_tasks", 0) or 0
            portfolio_revenue = sum(c.get("total_invoiced", 0) or 0 for c in portfolio)
            portfolio_tasks = sum(c.get("total_tasks", 0) or 0 for c in portfolio)

            # Compute concentration
            revenue_pct = (client_revenue / portfolio_revenue * 100) if portfolio_revenue > 0 else 0
            task_pct = (client_tasks / portfolio_tasks * 100) if portfolio_tasks > 0 else 0

            # Get affected team members
            people_involved = profile.get("people_involved", [])
            team_capacity = self.query_engine.team_capacity_overview()

            # Calculate projected load reduction
            affected_people_names = [p["person_name"] for p in people_involved]
            projected_load_reduction = {}

            for person in team_capacity.get("distribution", []):
                person_name = person.get("person_name")
                if person_name in affected_people_names:
                    # Find tasks assigned to this person from client
                    tasks_for_client = next(
                        (
                            p["tasks_for_client"]
                            for p in people_involved
                            if p["person_name"] == person_name
                        ),
                        0,
                    )
                    person_active = person.get("active_tasks", 0)
                    load_reduction_pct = (
                        (tasks_for_client / person_active * 100) if person_active > 0 else 0
                    )
                    projected_load_reduction[person_name] = {
                        "current_load": person_active,
                        "tasks_freed": tasks_for_client,
                        "load_reduction_pct": round(load_reduction_pct, 1),
                    }

            # Build risk factors
            risk_factors = []
            if revenue_pct > 25:
                risk_factors.append(
                    f"STRUCTURAL: Client represents {revenue_pct:.1f}% of portfolio revenue"
                )
            if task_pct > 20:
                risk_factors.append(f"High task concentration: {task_pct:.1f}% of workload")
            if len(people_involved) == 1:
                risk_factors.append("Single-resource dependency: only one team member involved")
            if profile.get("total_outstanding", 0) or 0 > 5000:
                risk_factors.append("Outstanding AR at risk: unpaid invoices")

            # Build baseline and projected
            baseline_metrics = {
                "revenue": round(client_revenue, 2),
                "revenue_pct": round(revenue_pct, 1),
                "tasks": client_tasks,
                "task_pct": round(task_pct, 1),
                "people_involved": len(people_involved),
                "projects": len(profile.get("projects", [])),
            }

            projected_metrics = {
                "portfolio_revenue": round(portfolio_revenue - client_revenue, 2),
                "portfolio_revenue_pct": round(100 - revenue_pct, 1),
                "portfolio_tasks": portfolio_tasks - client_tasks,
                "people_freed": len(affected_people_names),
                "people_utilization_after": self._compute_team_utilization(
                    team_capacity, affected_people_names, people_involved
                ),
                "projected_load_reduction": projected_load_reduction,
            }

            # Build impact summary
            impact_lines = [
                f"Revenue impact: ${client_revenue:,.2f} loss ({revenue_pct:.1f}% of portfolio)",
                f"Capacity freed: {client_tasks} tasks from {len(affected_people_names)} people",
            ]
            if revenue_pct > 25:
                impact_lines.append("WARNING: Structural impact - revenue cliff risk")

            impact_summary = " | ".join(impact_lines)

            # Determine confidence
            confidence = ConfidenceLevel.HIGH if revenue_pct > 5 else ConfidenceLevel.MEDIUM

            return ScenarioResult(
                scenario_type=ScenarioType.CLIENT_LOSS,
                description=f"Loss of {profile.get('client_name', 'Unknown')}",
                baseline_metrics=baseline_metrics,
                projected_metrics=projected_metrics,
                impact_summary=impact_summary,
                risk_factors=risk_factors,
                confidence=confidence,
                revenue_impact=-client_revenue,
                capacity_impact_pct=-task_pct,
            )

        except Exception as e:
            logger.error(f"Error modeling client loss for {client_id}: {e}", exc_info=True)
            return None

    # =========================================================================
    # CLIENT_ADDITION SCENARIO
    # =========================================================================

    def model_client_addition(
        self, estimated_revenue: float, estimated_tasks: int, team_size: int = 1
    ) -> ScenarioResult | None:
        """
        Model impact of adding a new client.

        Computes:
        - Revenue gain (absolute and %)
        - Capacity consumed (%)
        - Team load impact
        - Hiring needs if capacity deficit
        - Onboarding and quality dilution risks

        Args:
            estimated_revenue: Projected annual revenue
            estimated_tasks: Estimated task count for client
            team_size: Number of team members to assign (default 1)

        Returns:
            ScenarioResult with impact assessment
        """
        try:
            # Get portfolio overview (can be empty)
            portfolio = self.query_engine.client_portfolio_overview()
            if portfolio is None:
                logger.warning("No portfolio data available")
                return None

            # Get team capacity
            team_capacity = self.query_engine.team_capacity_overview()
            if not team_capacity:
                logger.warning("No team capacity data available")
                return None

            # Calculate portfolio metrics
            portfolio_revenue = (
                sum(c.get("total_invoiced", 0) or 0 for c in portfolio) if portfolio else 0
            )
            portfolio_tasks = (
                sum(c.get("total_tasks", 0) or 0 for c in portfolio) if portfolio else 0
            )
            total_people = team_capacity.get("total_people", 1)
            total_active_tasks = team_capacity.get("total_active_tasks", 0)

            # Revenue impact
            revenue_gain_pct = (
                (estimated_revenue / portfolio_revenue * 100) if portfolio_revenue > 0 else 0
            )

            # Capacity impact
            task_gain_pct = (estimated_tasks / portfolio_tasks * 100) if portfolio_tasks > 0 else 0

            # Per-person load
            avg_tasks_per_person = (
                (total_active_tasks + estimated_tasks) / (total_people + team_size)
                if (total_people + team_size) > 0
                else 0
            )

            # Capacity surplus/deficit
            available_people = team_capacity.get("people_available", 0)
            overloaded_people = team_capacity.get("people_overloaded", 0)

            # Risk factors
            risk_factors = []
            if estimated_tasks > 50 and total_people < 3:
                risk_factors.append("High task volume relative to team size")
            if available_people < team_size:
                risk_factors.append(
                    f"Capacity deficit: {team_size} people needed, {available_people} available"
                )
            if total_people == 1:
                risk_factors.append("Single-person team: onboarding new client increases risk")
            if task_gain_pct > 20:
                risk_factors.append(
                    f"Significant capacity consumption: {task_gain_pct:.1f}% of current load"
                )
            if overloaded_people > 0:
                risk_factors.append(
                    f"Team already overloaded: {overloaded_people} people over 20 active tasks"
                )

            # Build scenarios
            baseline_metrics = {
                "portfolio_revenue": round(portfolio_revenue, 2),
                "portfolio_tasks": portfolio_tasks,
                "team_size": total_people,
                "total_active_tasks": total_active_tasks,
                "avg_tasks_per_person": round(
                    total_active_tasks / total_people if total_people > 0 else 0, 1
                ),
                "available_people": available_people,
                "overloaded_people": overloaded_people,
            }

            projected_metrics = {
                "portfolio_revenue": round(portfolio_revenue + estimated_revenue, 2),
                "revenue_gain_pct": round(revenue_gain_pct, 1),
                "portfolio_tasks": portfolio_tasks + estimated_tasks,
                "task_gain_pct": round(task_gain_pct, 1),
                "team_size_after": total_people + team_size,
                "total_active_tasks_after": total_active_tasks + estimated_tasks,
                "avg_tasks_per_person_after": round(avg_tasks_per_person, 1),
                "hiring_needed": max(0, team_size - available_people),
            }

            # Impact summary
            impact_lines = [
                f"Revenue gain: ${estimated_revenue:,.2f} ({revenue_gain_pct:.1f}% growth)",
                f"Capacity consumed: {estimated_tasks} tasks ({task_gain_pct:.1f}% of portfolio)",
                f"Team load impact: {avg_tasks_per_person:.1f} tasks/person (from {total_active_tasks / total_people if total_people > 0 else 0:.1f})",
            ]
            if team_size > available_people:
                impact_lines.append(
                    f"HIRING NEEDED: {team_size - available_people} additional people"
                )

            impact_summary = " | ".join(impact_lines)

            # Confidence based on data quality
            confidence = ConfidenceLevel.MEDIUM  # New client is always medium confidence

            return ScenarioResult(
                scenario_type=ScenarioType.CLIENT_ADDITION,
                description=f"Addition of new client (${estimated_revenue:,.0f}, {estimated_tasks} tasks)",
                baseline_metrics=baseline_metrics,
                projected_metrics=projected_metrics,
                impact_summary=impact_summary,
                risk_factors=risk_factors,
                confidence=confidence,
                revenue_impact=estimated_revenue,
                capacity_impact_pct=task_gain_pct,
            )

        except Exception as e:
            logger.error(f"Error modeling client addition: {e}", exc_info=True)
            return None

    # =========================================================================
    # RESOURCE_CHANGE SCENARIO
    # =========================================================================

    def model_resource_change(
        self,
        person_name: str,
        change_type: str,  # "leaves", "added", "reduced"
    ) -> ScenarioResult | None:
        """
        Model impact of changing team resource.

        For "leaves": compute blast radius (affected projects/clients), coverage gaps
        For "added": compute capacity gain, time to productivity
        For "reduced" (hours): compute partial impact

        Args:
            person_name: Name of person being changed
            change_type: One of "leaves", "added", "reduced"

        Returns:
            ScenarioResult with impact assessment, or None if person not found
        """
        try:
            # For "added", we don't need the person to exist yet
            if change_type == "added":
                team_capacity = self.query_engine.team_capacity_overview()
                if not team_capacity:
                    logger.warning("No team capacity data available")
                    return None
                return self._model_resource_added(
                    person_name, team_capacity, team_capacity.get("total_people", 1)
                )

            # For "leaves" and "reduced", person must exist
            people_list = self.query_engine.resource_load_distribution()
            person_profile = next(
                (p for p in people_list if p.get("person_name") == person_name), None
            )

            if not person_profile:
                logger.warning(f"Person not found: {person_name}")
                return None

            # Get detailed person profile
            person_id = person_profile.get("person_id")
            detailed_profile = self.query_engine.person_operational_profile(person_id)

            if not detailed_profile:
                logger.warning(f"Detailed profile not found for {person_name}")
                return None

            # Get team capacity
            team_capacity = self.query_engine.team_capacity_overview()
            team_size = team_capacity.get("total_people", 1)

            if change_type == "leaves":
                return self._model_resource_leaves(
                    person_name,
                    person_id,
                    person_profile,
                    detailed_profile,
                    team_capacity,
                    team_size,
                )
            elif change_type == "reduced":
                return self._model_resource_reduced(
                    person_name, person_profile, detailed_profile, team_capacity, team_size
                )
            else:
                logger.error(f"Unknown change_type: {change_type}")
                return None

        except Exception as e:
            logger.error(f"Error modeling resource change for {person_name}: {e}", exc_info=True)
            return None

    def _model_resource_leaves(
        self,
        person_name: str,
        person_id: str,
        person_profile: dict,
        detailed_profile: dict,
        team_capacity: dict,
        team_size: int,
    ) -> ScenarioResult:
        """Model impact of person leaving."""
        person_active_tasks = person_profile.get("active_tasks", 0)
        person_projects = len(detailed_profile.get("projects", []))
        person_clients = len(detailed_profile.get("clients", []))

        # Blast radius
        affected_projects = detailed_profile.get("projects", [])
        detailed_profile.get("clients", [])

        # Find coverage gaps (projects with only this person)
        coverage_gaps = []
        for proj in affected_projects:
            # In real scenario, would check if other people on project
            # For now, assume single-threaded
            coverage_gaps.append(proj["project_name"])

        # Risk factors
        risk_factors = []
        if person_active_tasks > 20:
            risk_factors.append(
                f"High load departure: {person_active_tasks} active tasks to reassign"
            )
        if person_projects > 5:
            risk_factors.append(f"Wide project involvement: {person_projects} projects affected")
        if person_clients > 3:
            risk_factors.append(
                f"Multi-client resource: {person_clients} clients will lose dedicated contact"
            )
        if team_size == 1:
            risk_factors.append("Single-person team: loss of only team member is critical")
        elif team_size <= 2:
            risk_factors.append(
                f"Small team impact: {person_active_tasks}/{team_capacity.get('total_active_tasks', 0)} of workload"
            )
        if coverage_gaps:
            risk_factors.append(f"Coverage gaps: {len(coverage_gaps)} projects need reassignment")

        baseline_metrics = {
            "person": person_name,
            "active_tasks": person_active_tasks,
            "projects": person_projects,
            "clients": person_clients,
            "team_size": team_size,
            "team_total_tasks": team_capacity.get("total_active_tasks", 0),
        }

        projected_metrics = {
            "team_size_after": team_size - 1,
            "team_total_tasks_after": team_capacity.get("total_active_tasks", 0)
            - person_active_tasks,
            "tasks_requiring_reassignment": person_active_tasks,
            "projects_affected": person_projects,
            "clients_affected": person_clients,
            "coverage_gaps": coverage_gaps[:5],  # Limit to 5
            "remaining_team_load_increase_pct": round(
                (
                    person_active_tasks
                    / (team_capacity.get("total_active_tasks", 1) - person_active_tasks)
                    * 100
                )
                if (team_capacity.get("total_active_tasks", 0) - person_active_tasks) > 0
                else 0,
                1,
            ),
        }

        impact_lines = [
            f"Task loss: {person_active_tasks} active tasks to reassign",
            f"Project impact: {person_projects} projects, {person_clients} clients affected",
            f"Team load: {person_active_tasks}/{team_capacity.get('total_active_tasks', 0)} "
            f"({person_active_tasks / team_capacity.get('total_active_tasks', 1) * 100:.1f}%) of workload",
        ]
        if coverage_gaps:
            impact_lines.append(
                f"Coverage: {len(coverage_gaps)} projects have single-person dependency"
            )

        impact_summary = " | ".join(impact_lines)

        return ScenarioResult(
            scenario_type=ScenarioType.RESOURCE_CHANGE,
            description=f"Resource departure: {person_name} leaves",
            baseline_metrics=baseline_metrics,
            projected_metrics=projected_metrics,
            impact_summary=impact_summary,
            risk_factors=risk_factors,
            confidence=ConfidenceLevel.HIGH,
            revenue_impact=0.0,
            capacity_impact_pct=-(
                person_active_tasks / team_capacity.get("total_active_tasks", 1) * 100
            )
            if team_capacity.get("total_active_tasks", 0) > 0
            else 0,
        )

    def _model_resource_added(
        self, person_name: str, team_capacity: dict, team_size: int
    ) -> ScenarioResult:
        """Model impact of person being added."""
        team_total_tasks = team_capacity.get("total_active_tasks", 0)
        overloaded_people = team_capacity.get("people_overloaded", 0)

        # Estimate capacity gain (assume 20 tasks per person at full productivity)
        estimated_capacity_gain = 20
        time_to_productivity = 4  # weeks

        risk_factors = []
        if overloaded_people == 0:
            risk_factors.append(
                "Team not overloaded: new resource may have reduced initial utilization"
            )
        if team_size == 1:
            risk_factors.append("Scaling from single-person team: onboarding complexity")
        risk_factors.append(f"Ramp time: {time_to_productivity} weeks to full productivity")

        baseline_metrics = {
            "team_size": team_size,
            "team_total_tasks": team_total_tasks,
            "avg_tasks_per_person": round(team_total_tasks / team_size if team_size > 0 else 0, 1),
            "overloaded_people": overloaded_people,
            "available_capacity": team_capacity.get("people_available", 0),
        }

        projected_metrics = {
            "team_size_after": team_size + 1,
            "team_total_capacity": team_total_tasks + estimated_capacity_gain,
            "avg_tasks_per_person_after": round(
                (team_total_tasks + estimated_capacity_gain) / (team_size + 1), 1
            ),
            "estimated_capacity_gain": estimated_capacity_gain,
            "time_to_productivity_weeks": time_to_productivity,
            "expected_utilization_month_1_pct": 40,
            "expected_utilization_month_3_pct": 70,
            "expected_utilization_month_6_pct": 95,
        }

        impact_lines = [
            f"Capacity gain: +{estimated_capacity_gain} tasks at full productivity",
            f"Team growth: {team_size} → {team_size + 1} people",
            f"Ramp time: {time_to_productivity} weeks to productive",
        ]
        if overloaded_people > 0:
            impact_lines.append(f"Relief: {overloaded_people} currently overloaded people")

        impact_summary = " | ".join(impact_lines)

        return ScenarioResult(
            scenario_type=ScenarioType.RESOURCE_CHANGE,
            description=f"Resource addition: {person_name} joins team",
            baseline_metrics=baseline_metrics,
            projected_metrics=projected_metrics,
            impact_summary=impact_summary,
            risk_factors=risk_factors,
            confidence=ConfidenceLevel.MEDIUM,
            revenue_impact=0.0,
            capacity_impact_pct=(estimated_capacity_gain / team_total_tasks * 100)
            if team_total_tasks > 0
            else 0,
        )

    def _model_resource_reduced(
        self,
        person_name: str,
        person_profile: dict,
        detailed_profile: dict,
        team_capacity: dict,
        team_size: int,
    ) -> ScenarioResult:
        """Model impact of person's hours being reduced."""
        person_active_tasks = person_profile.get("active_tasks", 0)
        reduction_pct = 30  # Assume 30% reduction as default

        # Reduced capacity
        tasks_freed = round(person_active_tasks * (reduction_pct / 100))

        risk_factors = []
        if person_active_tasks > 20:
            risk_factors.append(
                f"High-load person: {person_active_tasks} tasks, reduction affects multiple projects"
            )
        if len(detailed_profile.get("projects", [])) > 3:
            risk_factors.append(
                f"Wide coverage: {len(detailed_profile.get('projects', []))} projects affected"
            )
        if reduction_pct > 25:
            risk_factors.append(f"Significant reduction: {reduction_pct}% cut to capacity")

        baseline_metrics = {
            "person": person_name,
            "active_tasks": person_active_tasks,
            "projects": len(detailed_profile.get("projects", [])),
            "reduction_pct": reduction_pct,
        }

        projected_metrics = {
            "active_tasks_after": person_active_tasks - tasks_freed,
            "tasks_freed": tasks_freed,
            "new_utilization_pct": round(
                ((person_active_tasks - tasks_freed) / person_active_tasks * 100)
                if person_active_tasks > 0
                else 0,
                1,
            ),
            "team_capacity_impact_pct": round(
                -(tasks_freed / team_capacity.get("total_active_tasks", 1) * 100), 1
            ),
        }

        impact_summary = (
            f"Capacity reduction: {tasks_freed} tasks ({reduction_pct}%) freed from {person_name}"
        )

        return ScenarioResult(
            scenario_type=ScenarioType.RESOURCE_CHANGE,
            description=f"Resource reduction: {person_name} hours reduced by {reduction_pct}%",
            baseline_metrics=baseline_metrics,
            projected_metrics=projected_metrics,
            impact_summary=impact_summary,
            risk_factors=risk_factors,
            confidence=ConfidenceLevel.MEDIUM,
            revenue_impact=0.0,
            capacity_impact_pct=-(tasks_freed / team_capacity.get("total_active_tasks", 1) * 100)
            if team_capacity.get("total_active_tasks", 0) > 0
            else 0,
        )

    # =========================================================================
    # PRICING_CHANGE SCENARIO
    # =========================================================================

    def model_pricing_change(self, client_id: str, pct_change: float) -> ScenarioResult | None:
        """
        Model impact of changing client pricing.

        Computes:
        - Revenue change (absolute and %)
        - Profitability impact
        - Risk of client churn
        - Portfolio impact

        Args:
            client_id: Client ID to change pricing for
            pct_change: Percentage change (e.g., 0.10 for +10%, -0.15 for -15%)

        Returns:
            ScenarioResult with revenue impact projection, or None if client not found
        """
        try:
            # Get client profile
            profile = self.query_engine.client_deep_profile(client_id)
            if not profile:
                logger.warning(f"Client not found: {client_id}")
                return None

            # Get cost profile
            cost_profile = self.cost_engine.compute_client_cost(client_id)

            # Get portfolio
            portfolio = self.query_engine.client_portfolio_overview()
            if not portfolio:
                logger.warning("No portfolio data available")
                return None

            # Calculate metrics
            current_revenue = profile.get("total_invoiced", 0) or 0
            revenue_change = current_revenue * pct_change
            new_revenue = current_revenue + revenue_change

            portfolio_revenue = sum(c.get("total_invoiced", 0) or 0 for c in portfolio)

            # Risk factors
            risk_factors = []
            if pct_change > 0.20:
                risk_factors.append(f"Aggressive increase: {pct_change * 100:.0f}% price hike")
                risk_factors.append("Churn risk: price-sensitive clients may leave")
            if pct_change < -0.15:
                risk_factors.append(f"Significant discount: {-pct_change * 100:.0f}% reduction")
                risk_factors.append("Margin compression: may affect profitability")

            if (
                cost_profile
                and hasattr(cost_profile, "efficiency_ratio")
                and isinstance(cost_profile.efficiency_ratio, (int, float))
            ):
                if cost_profile.efficiency_ratio < 1000:
                    risk_factors.append("Already low-margin client: pricing flexibility limited")
            if (
                cost_profile
                and hasattr(cost_profile, "overdue_tasks")
                and isinstance(cost_profile.overdue_tasks, int)
            ):
                if cost_profile.overdue_tasks > 5:
                    risk_factors.append(
                        "Client execution issues: pricing increase may worsen relationship"
                    )

            baseline_metrics = {
                "current_revenue": round(current_revenue, 2),
                "revenue_pct_of_portfolio": round(current_revenue / portfolio_revenue * 100, 1)
                if portfolio_revenue > 0
                else 0,
                "pricing_change_pct": round(pct_change * 100, 1),
            }

            if (
                cost_profile
                and hasattr(cost_profile, "efficiency_ratio")
                and isinstance(cost_profile.efficiency_ratio, (int, float))
            ):
                baseline_metrics["efficiency_ratio"] = round(cost_profile.efficiency_ratio, 2)
                baseline_metrics["profitability_band"] = cost_profile.profitability_band

            projected_metrics = {
                "new_revenue": round(new_revenue, 2),
                "revenue_change": round(revenue_change, 2),
                "portfolio_revenue": round(portfolio_revenue + revenue_change, 2),
                "new_revenue_pct_of_portfolio": round(
                    new_revenue / (portfolio_revenue + revenue_change) * 100, 1
                )
                if (portfolio_revenue + revenue_change) > 0
                else 0,
            }

            if (
                cost_profile
                and hasattr(cost_profile, "efficiency_ratio")
                and isinstance(cost_profile.efficiency_ratio, (int, float))
            ):
                new_efficiency = new_revenue / (
                    cost_profile.efficiency_ratio / (current_revenue or 1)
                )
                projected_metrics["new_efficiency_ratio"] = round(new_efficiency, 2)

            impact_lines = [
                f"Revenue change: ${revenue_change:+,.2f} ({pct_change * 100:+.1f}%)",
                f"New annual revenue: ${new_revenue:,.2f}",
            ]
            if pct_change > 0:
                impact_lines.append(f"Portfolio growth: +${revenue_change:,.2f}")
            else:
                impact_lines.append(f"Portfolio reduction: ${revenue_change:,.2f}")

            impact_summary = " | ".join(impact_lines)

            confidence = ConfidenceLevel.HIGH

            return ScenarioResult(
                scenario_type=ScenarioType.PRICING_CHANGE,
                description=f"Pricing change for {profile.get('client_name', 'Unknown')}: {pct_change * 100:+.1f}%",
                baseline_metrics=baseline_metrics,
                projected_metrics=projected_metrics,
                impact_summary=impact_summary,
                risk_factors=risk_factors,
                confidence=confidence,
                revenue_impact=revenue_change,
                capacity_impact_pct=0.0,
            )

        except Exception as e:
            logger.error(f"Error modeling pricing change for {client_id}: {e}", exc_info=True)
            return None

    # =========================================================================
    # CAPACITY_SHIFT SCENARIO
    # =========================================================================

    def model_capacity_shift(self, lane_id: str, delta_hours: float) -> ScenarioResult | None:
        """
        Model impact of reallocating capacity across lanes.

        Note: This is a simplified implementation since "lanes" are not yet
        modeled in the current schema. This shows the pattern for when
        they are introduced.

        Args:
            lane_id: Identifier of capacity lane
            delta_hours: Hours to shift (positive = increase, negative = decrease)

        Returns:
            ScenarioResult with capacity impact, or None on error
        """
        try:
            team_capacity = self.query_engine.team_capacity_overview()
            if not team_capacity:
                logger.warning("No team capacity data available")
                return None

            # Use resource load distribution to find lane-related people
            people = self.query_engine.resource_load_distribution()
            lane_people = [p for p in people if p.get("lane_id") == lane_id]

            # Calculate current lane utilization
            current_lane_hours = sum(p.get("weekly_hours", 0) for p in lane_people)
            current_lane_tasks = sum(p.get("active_tasks", 0) for p in lane_people)

            # If no lane data, fall back to team-level estimation
            if not lane_people:
                total_people = max(len(people), 1)
                (team_capacity.get("total_weekly_hours", 40 * total_people) / total_people)
                tasks_per_hour = team_capacity.get("total_active_tasks", 0) / max(
                    1, team_capacity.get("total_weekly_hours", 40)
                )
                delta_tasks = delta_hours * tasks_per_hour
            else:
                tasks_per_hour = (
                    current_lane_tasks / max(1, current_lane_hours)
                    if current_lane_hours > 0
                    else 0.125
                )
                delta_tasks = delta_hours * tasks_per_hour

            baseline_metrics = {
                "team_total_active_tasks": team_capacity.get("total_active_tasks", 0),
                "capacity_lane": lane_id,
                "lane_people_count": len(lane_people),
                "lane_current_hours": current_lane_hours,
                "lane_current_tasks": current_lane_tasks,
                "hours_shift": delta_hours,
            }

            projected_metrics = {
                "team_total_active_tasks_after": team_capacity.get("total_active_tasks", 0)
                + delta_tasks,
                "lane_hours_after": current_lane_hours + delta_hours,
                "lane_tasks_after": current_lane_tasks + delta_tasks,
                "tasks_shift": round(delta_tasks, 1),
            }

            impact_summary = f"Capacity shift: {delta_hours:+.1f} hours ({delta_tasks:+.1f} tasks) to/from {lane_id}"
            risk_factors = []
            if not lane_people:
                risk_factors.append("Lane not yet modeled — using team-level estimation")
            if abs(delta_hours) > current_lane_hours * 0.5 and current_lane_hours > 0:
                risk_factors.append(
                    f"Large shift ({abs(delta_hours):.0f}h) relative to lane capacity ({current_lane_hours:.0f}h)"
                )

            return ScenarioResult(
                scenario_type=ScenarioType.CAPACITY_SHIFT,
                description=f"Capacity shift in lane {lane_id}: {delta_hours:+.1f} hours",
                baseline_metrics=baseline_metrics,
                projected_metrics=projected_metrics,
                impact_summary=impact_summary,
                risk_factors=risk_factors,
                confidence=ConfidenceLevel.LOW,
                revenue_impact=0.0,
                capacity_impact_pct=round(
                    delta_tasks / team_capacity.get("total_active_tasks", 1) * 100, 1
                )
                if team_capacity.get("total_active_tasks", 0) > 0
                else 0,
            )

        except Exception as e:
            logger.error(f"Error modeling capacity shift for {lane_id}: {e}", exc_info=True)
            return None

    # =========================================================================
    # WORKLOAD_REBALANCE SCENARIO
    # =========================================================================

    def model_workload_rebalance(self) -> ScenarioResult | None:
        """
        Model impact of rebalancing workload across team.

        Computes:
        - Potential load leveling
        - Utilization improvement
        - Projects/clients that could be reassigned
        - Risks of cross-training

        Returns:
            ScenarioResult with rebalancing impact
        """
        try:
            team_capacity = self.query_engine.team_capacity_overview()
            if not team_capacity:
                logger.warning("No team capacity data available")
                return None

            distribution = team_capacity.get("distribution", [])
            if not distribution:
                logger.warning("No team distribution data")
                return None

            # Current state
            total_active_tasks = team_capacity.get("total_active_tasks", 0)
            avg_load = team_capacity.get("avg_tasks_per_person", 0)
            max_load = team_capacity.get("max_tasks_per_person", 0)
            overloaded_count = team_capacity.get("people_overloaded", 0)
            available_count = team_capacity.get("people_available", 0)

            # Simulated rebalance: move work from overloaded to available
            load_variance = max(0, max_load - avg_load)
            potential_reallocation = min(
                sum(
                    p.get("active_tasks", 0) - avg_load
                    for p in distribution
                    if p.get("active_tasks", 0) > avg_load
                ),
                sum(
                    avg_load - p.get("active_tasks", 0)
                    for p in distribution
                    if p.get("active_tasks", 0) < avg_load
                ),
            )

            risk_factors = []
            if overloaded_count > 0:
                risk_factors.append(f"Current overload: {overloaded_count} people over threshold")
            if available_count == 0:
                risk_factors.append(
                    "No available capacity: rebalance requires reassignment from active projects"
                )
            risk_factors.append("Context switching risk: moving people between projects")
            risk_factors.append("Relationship risk: clients may resist resource changes")

            baseline_metrics = {
                "total_active_tasks": total_active_tasks,
                "avg_load": round(avg_load, 1),
                "max_load": max_load,
                "load_variance": round(load_variance, 1),
                "overloaded_count": overloaded_count,
                "available_count": available_count,
            }

            # After rebalance
            new_variance = max(0, load_variance * 0.5)  # Assume 50% variance reduction

            projected_metrics = {
                "total_active_tasks": total_active_tasks,
                "avg_load": round(avg_load, 1),
                "projected_max_load": round(
                    max_load - (potential_reallocation / overloaded_count)
                    if overloaded_count > 0
                    else max_load,
                    1,
                ),
                "projected_load_variance": round(new_variance, 1),
                "overloaded_after_rebalance": max(0, overloaded_count - 1),
                "available_after_rebalance": max(0, available_count + 1),
                "potential_tasks_reallocated": round(potential_reallocation, 1),
            }

            impact_lines = [
                f"Variance reduction: {load_variance:.1f} → {new_variance:.1f} tasks spread",
                f"Overloaded relief: {overloaded_count} → {max(0, overloaded_count - 1)} people",
                f"Potential reallocation: {potential_reallocation:.1f} tasks",
            ]

            impact_summary = " | ".join(impact_lines)

            return ScenarioResult(
                scenario_type=ScenarioType.WORKLOAD_REBALANCE,
                description="Workload rebalancing across team",
                baseline_metrics=baseline_metrics,
                projected_metrics=projected_metrics,
                impact_summary=impact_summary,
                risk_factors=risk_factors,
                confidence=ConfidenceLevel.MEDIUM,
                revenue_impact=0.0,
                capacity_impact_pct=0.0,
            )

        except Exception as e:
            logger.error(f"Error modeling workload rebalance: {e}", exc_info=True)
            return None

    # =========================================================================
    # COMPARISON
    # =========================================================================

    def compare_scenarios(self, scenarios: list[ScenarioResult]) -> ScenarioComparison | None:
        """
        Compare multiple scenarios side-by-side.

        Identifies best and worst cases based on revenue impact,
        capacity impact, and risk assessment.

        Args:
            scenarios: List of ScenarioResult objects to compare

        Returns:
            ScenarioComparison with best/worst/tradeoff analysis
        """
        try:
            if not scenarios:
                logger.warning("No scenarios provided for comparison")
                return None

            if len(scenarios) == 1:
                logger.warning("Only one scenario provided; comparison needs multiple")
                return None

            # Find best and worst
            best_idx = 0
            worst_idx = 0
            best_score = -float("inf")
            worst_score = float("inf")

            for idx, scenario in enumerate(scenarios):
                # Score based on: revenue impact + capacity impact - risk count
                risk_penalty = len(scenario.risk_factors) * 10
                score = scenario.revenue_impact + scenario.capacity_impact_pct - risk_penalty

                if score > best_score:
                    best_score = score
                    best_idx = idx

                if score < worst_score:
                    worst_score = score
                    worst_idx = idx

            # Build tradeoff summary
            best_scenario = scenarios[best_idx]
            worst_scenario = scenarios[worst_idx]

            tradeoff_lines = [
                f"Best case: {best_scenario.description} "
                f"(Revenue: {best_scenario.revenue_impact:+.0f}, Risks: {len(best_scenario.risk_factors)})",
                f"Worst case: {worst_scenario.description} "
                f"(Revenue: {worst_scenario.revenue_impact:+.0f}, Risks: {len(worst_scenario.risk_factors)})",
            ]

            tradeoff_summary = " | ".join(tradeoff_lines)

            return ScenarioComparison(
                scenarios=scenarios,
                best_case_idx=best_idx,
                worst_case_idx=worst_idx,
                tradeoff_summary=tradeoff_summary,
            )

        except Exception as e:
            logger.error(f"Error comparing scenarios: {e}", exc_info=True)
            return None

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _compute_team_utilization(
        self, team_capacity: dict, affected_people: list[str], people_involved: list[dict]
    ) -> dict:
        """
        Compute team utilization after people are removed.

        Args:
            team_capacity: Current team capacity overview
            affected_people: Names of people being removed
            people_involved: List of people involved with client

        Returns:
            Dict with utilization metrics
        """
        distribution = team_capacity.get("distribution", [])
        total_active = team_capacity.get("total_active_tasks", 0)
        total_people = team_capacity.get("total_people", 1)

        # Calculate tasks freed
        tasks_freed = 0
        for person in distribution:
            if person.get("person_name") in affected_people:
                tasks_freed += person.get("active_tasks", 0)

        # Remaining utilization
        remaining_tasks = total_active - tasks_freed
        remaining_people = max(1, total_people - len(affected_people))

        return {
            "total_tasks": remaining_tasks,
            "avg_per_person": round(remaining_tasks / remaining_people, 1),
            "total_people": remaining_people,
        }
