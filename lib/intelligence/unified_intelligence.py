"""
Unified Intelligence Layer for MOH TIME OS.

Consolidates parallel V4 and V5 architectures into a single interface without
modifying either system. Provides a facade that orchestrates all intelligence
capabilities from the intelligence layer modules:
- Pattern detection (lib.intelligence.patterns)
- Correlation analysis (lib.intelligence.correlation_engine)
- Cost analysis (lib.intelligence.cost_to_serve)
- Trajectory analysis (lib.intelligence.trajectory)
- Scenario modeling (lib.intelligence.scenario_engine)

Usage:
    layer = IntelligenceLayer()
    result = layer.run_intelligence_cycle()

    client_intel = layer.get_client_intelligence("client-123")
    dashboard = layer.get_portfolio_dashboard()

    scenario = layer.run_scenario("CLIENT_LOSS", client_id="client-456")
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from lib.intelligence.correlation_engine import CorrelationEngine, HealthGrade
from lib.intelligence.cost_to_serve import CostToServeEngine
from lib.intelligence.patterns import detect_all_patterns
from lib.intelligence.scenario_engine import ScenarioEngine
from lib.intelligence.trajectory import TrajectoryEngine

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class IntelligenceCycleResult:
    """Complete result of a unified intelligence cycle."""

    timestamp: str
    pattern_results: dict = field(default_factory=dict)
    correlation_brief: dict = field(default_factory=dict)
    portfolio_profitability: dict = field(default_factory=dict)
    trajectory_results: list = field(default_factory=list)
    health_grade: str = "B"
    executive_summary: str = ""
    cycle_duration_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "pattern_results": self.pattern_results,
            "correlation_brief": self.correlation_brief,
            "portfolio_profitability": self.portfolio_profitability,
            "trajectory_results": self.trajectory_results,
            "health_grade": self.health_grade,
            "executive_summary": self.executive_summary,
            "cycle_duration_ms": self.cycle_duration_ms,
        }


@dataclass
class ClientIntelligence:
    """Complete intelligence for a single client."""

    client_id: str
    name: str = ""
    cost_profile: dict = field(default_factory=dict)
    trajectory: dict = field(default_factory=dict)
    patterns_affecting: list = field(default_factory=list)
    risk_factors: list = field(default_factory=list)
    overall_score: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "client_id": self.client_id,
            "name": self.name,
            "cost_profile": self.cost_profile,
            "trajectory": self.trajectory,
            "patterns_affecting": self.patterns_affecting,
            "risk_factors": self.risk_factors,
            "overall_score": round(self.overall_score, 2),
            "recommendation": self.recommendation,
        }


@dataclass
class PortfolioDashboard:
    """Portfolio-level dashboard data."""

    total_clients: int = 0
    health_grade: str = "B"
    revenue_total: float = 0.0
    profitable_count: int = 0
    at_risk_count: int = 0
    declining_count: int = 0
    top_risks: list = field(default_factory=list)
    top_opportunities: list = field(default_factory=list)
    compound_risks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_clients": self.total_clients,
            "health_grade": self.health_grade,
            "revenue_total": round(self.revenue_total, 2),
            "profitable_count": self.profitable_count,
            "at_risk_count": self.at_risk_count,
            "declining_count": self.declining_count,
            "top_risks": self.top_risks,
            "top_opportunities": self.top_opportunities,
            "compound_risks": self.compound_risks,
        }


# =============================================================================
# INTELLIGENCE LAYER FACADE
# =============================================================================


class IntelligenceLayer:
    """
    Unified intelligence facade orchestrating all intelligence capabilities.

    Lazy-initializes sub-engines to avoid circular imports.
    Runs full intelligence cycles and provides targeted intelligence for clients
    and the portfolio.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize IntelligenceLayer with optional database path.

        Sub-engines are lazy-initialized on first use.
        """
        self.db_path = db_path
        self._correlation_engine: CorrelationEngine | None = None
        self._cost_engine: CostToServeEngine | None = None
        self._trajectory_engine: TrajectoryEngine | None = None
        self._scenario_engine: ScenarioEngine | None = None
        self.logger = logger

    # =========================================================================
    # LAZY INITIALIZATION
    # =========================================================================

    def _get_correlation_engine(self) -> CorrelationEngine:
        """Lazy-initialize correlation engine."""
        if self._correlation_engine is None:
            try:
                self._correlation_engine = CorrelationEngine(self.db_path)
            except Exception as e:
                self.logger.error(f"Failed to initialize CorrelationEngine: {e}")
                raise
        return self._correlation_engine

    def _get_cost_engine(self) -> CostToServeEngine:
        """Lazy-initialize cost engine."""
        if self._cost_engine is None:
            try:
                self._cost_engine = CostToServeEngine(self.db_path)
            except Exception as e:
                self.logger.error(f"Failed to initialize CostToServeEngine: {e}")
                raise
        return self._cost_engine

    def _get_trajectory_engine(self) -> TrajectoryEngine:
        """Lazy-initialize trajectory engine."""
        if self._trajectory_engine is None:
            try:
                self._trajectory_engine = TrajectoryEngine(self.db_path)
            except Exception as e:
                self.logger.error(f"Failed to initialize TrajectoryEngine: {e}")
                raise
        return self._trajectory_engine

    def _get_scenario_engine(self) -> ScenarioEngine:
        """Lazy-initialize scenario engine."""
        if self._scenario_engine is None:
            try:
                self._scenario_engine = ScenarioEngine(self.db_path)
            except Exception as e:
                self.logger.error(f"Failed to initialize ScenarioEngine: {e}")
                raise
        return self._scenario_engine

    # =========================================================================
    # MAIN INTELLIGENCE CYCLE
    # =========================================================================

    def run_intelligence_cycle(self) -> IntelligenceCycleResult:
        """
        Execute complete intelligence cycle.

        Steps:
        1. Pattern detection (detect_all_patterns)
        2. Correlation analysis (CorrelationEngine.run_full_scan)
        3. Cost analysis (CostToServeEngine.compute_portfolio_profitability)
        4. Trajectory analysis (TrajectoryEngine.portfolio_health_trajectory)
        5. Combine all into unified result

        Returns:
            IntelligenceCycleResult with all intelligence components
        """
        cycle_start = time.time()
        timestamp = datetime.now().isoformat()

        try:
            # Step 1: Pattern detection
            pattern_results = {}
            try:
                pattern_results = detect_all_patterns(self.db_path)
                self.logger.info(
                    f"Pattern detection: {pattern_results.get('total_detected', 0)} "
                    f"patterns detected"
                )
            except Exception as e:
                self.logger.error(f"Error in pattern detection: {e}")
                pattern_results = {"error": str(e), "patterns": []}

            # Step 2: Correlation analysis
            correlation_brief = {}
            try:
                correlation_engine = self._get_correlation_engine()
                brief = correlation_engine.run_full_scan()
                correlation_brief = {
                    "generated_at": brief.generated_at,
                    "pattern_results": brief.pattern_results,
                    "signal_results": brief.signal_results,
                    "compound_risks": [r.to_dict() for r in brief.compound_risks],
                    "cross_domain_correlations": [
                        c.to_dict() for c in brief.cross_domain_correlations
                    ],
                    "priority_actions": [a.to_dict() for a in brief.priority_actions],
                    "executive_summary": brief.executive_summary,
                    "health_grade": brief.health_grade.value,
                }
                self.logger.info(
                    f"Correlation analysis: {len(brief.compound_risks)} compound risks identified"
                )
            except Exception as e:
                self.logger.error(f"Error in correlation analysis: {e}")
                correlation_brief = {"error": str(e)}

            # Step 3: Cost analysis
            portfolio_profitability = {}
            try:
                cost_engine = self._get_cost_engine()
                profitability = cost_engine.compute_portfolio_profitability()
                if profitability:
                    portfolio_profitability = profitability.to_dict()
                    self.logger.info(
                        f"Cost analysis: {profitability.total_clients} clients, "
                        f"{profitability.profitable_count} profitable"
                    )
                else:
                    portfolio_profitability = {"error": "Could not compute profitability"}
            except Exception as e:
                self.logger.error(f"Error in cost analysis: {e}")
                portfolio_profitability = {"error": str(e)}

            # Step 4: Trajectory analysis
            trajectory_results = []
            try:
                trajectory_engine = self._get_trajectory_engine()
                trajectories = trajectory_engine.portfolio_health_trajectory()
                trajectory_results = [t.to_dict() for t in trajectories]
                self.logger.info(f"Trajectory analysis: {len(trajectories)} entities analyzed")
            except Exception as e:
                self.logger.error(f"Error in trajectory analysis: {e}")
                trajectory_results = []

            # Step 5: Determine health grade from correlation brief
            health_grade = correlation_brief.get("health_grade", "B")

            # Step 6: Build executive summary
            executive_summary = self._build_cycle_summary(
                pattern_results,
                correlation_brief,
                portfolio_profitability,
                health_grade,
            )

            cycle_duration_ms = int((time.time() - cycle_start) * 1000)

            return IntelligenceCycleResult(
                timestamp=timestamp,
                pattern_results=pattern_results,
                correlation_brief=correlation_brief,
                portfolio_profitability=portfolio_profitability,
                trajectory_results=trajectory_results,
                health_grade=health_grade,
                executive_summary=executive_summary,
                cycle_duration_ms=cycle_duration_ms,
            )

        except Exception as e:
            self.logger.error(f"Critical error in intelligence cycle: {e}", exc_info=True)
            cycle_duration_ms = int((time.time() - cycle_start) * 1000)
            return IntelligenceCycleResult(
                timestamp=timestamp,
                health_grade="F",
                executive_summary=f"Intelligence cycle failed: {str(e)}",
                cycle_duration_ms=cycle_duration_ms,
            )

    # =========================================================================
    # CLIENT INTELLIGENCE
    # =========================================================================

    def get_client_intelligence(self, client_id: str) -> ClientIntelligence:
        """
        Get complete intelligence for a single client.

        Combines:
        - Cost profile from CostToServeEngine
        - Trajectory from TrajectoryEngine
        - Patterns that mention this client
        - Risk factors based on cost + trajectory + patterns
        - Overall score: weighted average of efficiency, trend, patterns

        Args:
            client_id: Client ID to analyze

        Returns:
            ClientIntelligence with complete profile
        """
        intel = ClientIntelligence(client_id=client_id)

        try:
            # Get cost profile
            cost_engine = self._get_cost_engine()
            client_cost = cost_engine.compute_client_cost(client_id)
            if client_cost:
                intel.cost_profile = client_cost.to_dict()
                intel.name = client_cost.name

            # Get trajectory
            trajectory_engine = self._get_trajectory_engine()
            try:
                trajectory = trajectory_engine.client_full_trajectory(client_id)
                if trajectory:
                    intel.trajectory = trajectory.to_dict()
            except Exception as e:
                self.logger.warning(f"Could not get trajectory for client {client_id}: {e}")

            # Find patterns affecting this client
            try:
                pattern_results = detect_all_patterns(self.db_path)
                patterns = pattern_results.get("patterns", [])

                for pattern in patterns:
                    entities = pattern.get("entities_involved", [])
                    for entity in entities:
                        if entity.get("type") == "client" and entity.get("id") == client_id:
                            intel.patterns_affecting.append(
                                {
                                    "pattern_id": pattern.get("pattern_id"),
                                    "pattern_name": pattern.get("pattern_name"),
                                    "severity": pattern.get("severity"),
                                }
                            )
            except Exception as e:
                self.logger.warning(f"Could not detect patterns for client {client_id}: {e}")

            # Compute risk factors
            intel.risk_factors = self._compute_client_risk_factors(
                intel.cost_profile,
                intel.trajectory,
                intel.patterns_affecting,
            )

            # Compute overall score
            intel.overall_score = self._compute_client_score(
                intel.cost_profile,
                intel.trajectory,
                intel.patterns_affecting,
            )

            # Generate recommendation
            intel.recommendation = self._generate_client_recommendation(
                intel.cost_profile,
                intel.trajectory,
                intel.risk_factors,
                intel.overall_score,
            )

        except Exception as e:
            self.logger.error(f"Error getting client intelligence for {client_id}: {e}")

        return intel

    # =========================================================================
    # PORTFOLIO DASHBOARD
    # =========================================================================

    def get_portfolio_dashboard(self) -> PortfolioDashboard:
        """
        Get portfolio-level dashboard data.

        Combines:
        - Client count and health grade from correlation
        - Revenue and profitability metrics from cost engine
        - Top risks and opportunities
        - Compound risks from correlation

        Returns:
            PortfolioDashboard with portfolio overview
        """
        dashboard = PortfolioDashboard()

        try:
            # Get profitability data
            cost_engine = self._get_cost_engine()
            profitability = cost_engine.compute_portfolio_profitability()

            if profitability:
                dashboard.total_clients = profitability.total_clients
                dashboard.revenue_total = profitability.total_revenue
                dashboard.profitable_count = profitability.profitable_count

                # Count at-risk and declining
                try:
                    trajectory_engine = self._get_trajectory_engine()
                    trajectories = trajectory_engine.portfolio_health_trajectory()

                    for traj in trajectories:
                        if traj.overall_health == "DECLINING":
                            dashboard.declining_count += 1
                        elif traj.overall_health == "CRITICAL":
                            dashboard.at_risk_count += 1
                except Exception as e:
                    self.logger.warning(f"Could not compute trajectory for dashboard: {e}")

            # Get correlation data
            correlation_engine = self._get_correlation_engine()
            brief = correlation_engine.run_full_scan()

            dashboard.health_grade = brief.health_grade.value

            # Extract top risks
            dashboard.compound_risks = [r.to_dict() for r in brief.compound_risks[:5]]

            # Extract priority actions as top risks/opportunities
            for action in brief.priority_actions[:3]:
                if action.urgency == "IMMEDIATE":
                    dashboard.top_risks.append(
                        {
                            "action_id": action.action_id,
                            "description": action.description,
                            "domains": [d.value for d in action.domains],
                        }
                    )
                else:
                    dashboard.top_opportunities.append(
                        {
                            "action_id": action.action_id,
                            "description": action.description,
                            "domains": [d.value for d in action.domains],
                        }
                    )

        except Exception as e:
            self.logger.error(f"Error generating portfolio dashboard: {e}")

        return dashboard

    # =========================================================================
    # SCENARIO MODELING
    # =========================================================================

    def run_scenario(self, scenario_type: str, **kwargs) -> dict:
        """
        Run a what-if scenario through ScenarioEngine.

        Delegates to ScenarioEngine methods based on scenario_type:
        - CLIENT_LOSS: model_client_loss(client_id)
        - CLIENT_ADDITION: model_client_addition(...)
        - RESOURCE_CHANGE: model_resource_change(...)
        - PRICING_CHANGE: model_pricing_change(...)
        - CAPACITY_SHIFT: model_capacity_shift()
        - WORKLOAD_REBALANCE: model_workload_rebalance()

        Args:
            scenario_type: Type of scenario to model
            **kwargs: Scenario-specific parameters

        Returns:
            Dictionary with scenario result
        """
        try:
            scenario_engine = self._get_scenario_engine()

            if scenario_type == "CLIENT_LOSS":
                client_id = kwargs.get("client_id")
                if not client_id:
                    return {"error": "client_id required for CLIENT_LOSS scenario"}
                result = scenario_engine.model_client_loss(client_id)
                return result.to_dict() if result else {"error": "Could not model scenario"}

            elif scenario_type == "CLIENT_ADDITION":
                result = scenario_engine.model_client_addition(
                    name=kwargs.get("name"),
                    revenue=kwargs.get("revenue"),
                    task_count=kwargs.get("task_count", 0),
                )
                return result.to_dict() if result else {"error": "Could not model scenario"}

            elif scenario_type == "RESOURCE_CHANGE":
                result = scenario_engine.model_resource_change(
                    person_id=kwargs.get("person_id"),
                    change_type=kwargs.get("change_type"),  # leaves, added, reduced
                    person_name=kwargs.get("person_name"),
                    reduction_pct=kwargs.get("reduction_pct", 0),
                )
                return result.to_dict() if result else {"error": "Could not model scenario"}

            elif scenario_type == "PRICING_CHANGE":
                result = scenario_engine.model_pricing_change(
                    client_id=kwargs.get("client_id"),
                    new_rate=kwargs.get("new_rate"),
                )
                return result.to_dict() if result else {"error": "Could not model scenario"}

            elif scenario_type == "CAPACITY_SHIFT":
                result = scenario_engine.model_capacity_shift(
                    from_lane=kwargs.get("from_lane"),
                    to_lane=kwargs.get("to_lane"),
                    pct_shift=kwargs.get("pct_shift", 0),
                )
                return result.to_dict() if result else {"error": "Could not model scenario"}

            elif scenario_type == "WORKLOAD_REBALANCE":
                result = scenario_engine.model_workload_rebalance()
                return result.to_dict() if result else {"error": "Could not model scenario"}

            else:
                return {"error": f"Unknown scenario type: {scenario_type}"}

        except Exception as e:
            self.logger.error(f"Error running scenario {scenario_type}: {e}")
            return {"error": str(e)}

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _build_cycle_summary(
        self,
        pattern_results: dict,
        correlation_brief: dict,
        portfolio_profitability: dict,
        health_grade: str,
    ) -> str:
        """Build executive summary for intelligence cycle."""
        try:
            patterns_detected = pattern_results.get("total_detected", 0)
            compound_risks = len(correlation_brief.get("compound_risks", []))
            profitable = portfolio_profitability.get("profitable_count", 0)
            total_clients = portfolio_profitability.get("total_clients", 0)

            summary = (
                f"Intelligence cycle complete. "
                f"Detected {patterns_detected} patterns, {compound_risks} compound risks. "
                f"Portfolio health: {health_grade}. "
            )

            if total_clients > 0:
                summary += f"{profitable}/{total_clients} clients profitable."

            return summary
        except Exception as e:
            self.logger.warning(f"Could not build cycle summary: {e}")
            return f"Intelligence cycle complete. Health grade: {health_grade}."

    def _compute_client_risk_factors(
        self,
        cost_profile: dict,
        trajectory: dict,
        patterns_affecting: list,
    ) -> list:
        """Compute risk factors for a client."""
        risks = []

        # Risk from efficiency
        if cost_profile:
            efficiency = cost_profile.get("efficiency_ratio", 1.0)
            if efficiency < 0.5:
                risks.append("LOW_EFFICIENCY")

            profitability = cost_profile.get("profitability_band")
            if profitability == "LOW":
                risks.append("LOW_PROFITABILITY")

        # Risk from trajectory
        if trajectory:
            health = trajectory.get("overall_health")
            if health == "DECLINING":
                risks.append("DECLINING_TREND")
            elif health == "CRITICAL":
                risks.append("CRITICAL_HEALTH")

        # Risk from patterns
        for pattern in patterns_affecting:
            severity = pattern.get("severity")
            if severity == "structural":
                risks.append(f"STRUCTURAL_RISK_{pattern.get('pattern_id')}")

        return list(set(risks))

    def _compute_client_score(
        self,
        cost_profile: dict,
        trajectory: dict,
        patterns_affecting: list,
    ) -> float:
        """Compute overall score for a client (0-100)."""
        scores = []

        # Score from efficiency
        if cost_profile:
            efficiency = cost_profile.get("efficiency_ratio", 0.5)
            scores.append(min(efficiency * 100, 100))

        # Score from trajectory health
        if trajectory:
            health = trajectory.get("overall_health", "STABLE")
            health_scores = {
                "IMPROVING": 85,
                "STABLE": 70,
                "DECLINING": 40,
                "CRITICAL": 10,
            }
            scores.append(health_scores.get(health, 50))

        # Reduce score based on patterns
        pattern_score = 100
        for pattern in patterns_affecting:
            severity = pattern.get("severity")
            if severity == "structural":
                pattern_score -= 25
            elif severity == "operational":
                pattern_score -= 10
        scores.append(max(pattern_score, 0))

        return sum(scores) / len(scores) if scores else 50.0

    def _generate_client_recommendation(
        self,
        cost_profile: dict,
        trajectory: dict,
        risk_factors: list,
        overall_score: float,
    ) -> str:
        """Generate recommendation for client."""
        if overall_score >= 80:
            return "MAINTAIN_RELATIONSHIP"
        elif overall_score >= 60:
            if "DECLINING_TREND" in risk_factors:
                return "MONITOR_CLOSELY"
            return "OPTIMIZE_DELIVERY"
        elif overall_score >= 40:
            return "IMPROVE_PROFITABILITY"
        else:
            return "REVIEW_ENGAGEMENT"
