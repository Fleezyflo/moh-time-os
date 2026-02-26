"""
Advanced Trajectory and Trend Computation Module.

Provides comprehensive time-series analysis for entity trajectories including:
- Velocity: rate of change over a period
- Acceleration: change in velocity over time
- Trend detection: directional analysis with confidence metrics
- Seasonality: detection of recurring patterns
- Projection: forward-looking forecasts with confidence intervals
- Full trajectory: comprehensive multi-metric analysis

All computations use pure Python; no external dependencies beyond stdlib.
"""

import logging
import sqlite3
import statistics
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from lib.query_engine import get_engine

logger = logging.getLogger(__name__)


# =====================================================================
# ENUMS
# =====================================================================


class TrendDirection(Enum):
    """Enumeration of trend directions."""

    ACCELERATING_UP = "accelerating_up"
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    ACCELERATING_DOWN = "accelerating_down"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"

    def __str__(self) -> str:
        return self.value


# =====================================================================
# DATA CLASSES
# =====================================================================


@dataclass
class VelocityResult:
    """Velocity: rate of change per period."""

    current_velocity: float
    avg_velocity: float
    direction: str  # 'positive', 'negative', 'zero'
    period_days: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AccelerationResult:
    """Acceleration: rate of velocity change."""

    current_acceleration: float
    is_accelerating: bool
    direction_change: bool  # Changed direction since last period

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrendAnalysis:
    """Comprehensive trend analysis."""

    direction: TrendDirection
    slope: float  # Linear regression slope
    r_squared: float  # Goodness of fit (0-1)
    confidence: str  # 'high', 'medium', 'low'
    volatility: float  # Coefficient of variation (std/mean)
    turning_point_idx: int | None  # Index of local min/max, if any
    summary: str  # Human-readable summary

    def to_dict(self) -> dict:
        data = asdict(self)
        data["direction"] = self.direction.value
        return data


@dataclass
class SeasonalityResult:
    """Seasonality detection results."""

    has_seasonality: bool
    period_length: int | None  # Detected period in number of points
    seasonal_strength: float  # Autocorrelation coefficient
    peak_period_idx: int | None  # Index where peak occurs

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectionResult:
    """Forward projection with confidence bounds."""

    projected_values: list[float]
    upper_bound: list[float]
    lower_bound: list[float]
    confidence_pct: float
    method: str  # 'linear_extrapolation', etc.

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FullTrajectory:
    """Comprehensive trajectory analysis for an entity."""

    entity_id: str
    entity_name: str
    entity_type: str  # 'client', 'person', 'project'
    metrics: dict[str, TrendAnalysis]  # metric_name -> TrendAnalysis
    projections: dict[str, ProjectionResult]  # metric_name -> ProjectionResult
    velocity: VelocityResult | None
    acceleration: AccelerationResult | None
    overall_health: str  # 'IMPROVING', 'STABLE', 'DECLINING', 'CRITICAL'
    summary: str

    def to_dict(self) -> dict:
        data = {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "projections": {k: v.to_dict() for k, v in self.projections.items()},
            "velocity": self.velocity.to_dict() if self.velocity else None,
            "acceleration": self.acceleration.to_dict() if self.acceleration else None,
            "overall_health": self.overall_health,
            "summary": self.summary,
        }
        return data


# =====================================================================
# PURE PYTHON MATH UTILITIES
# =====================================================================


def _mean(values: list[float]) -> float:
    """Compute arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    try:
        return statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0


def _linear_regression(
    values: list[float],
) -> tuple[float, float, float]:
    """
    Compute linear regression: y = mx + b.

    Returns: (slope, intercept, r_squared)
    """
    if len(values) < 2:
        return (0.0, 0.0, 0.0)

    n = len(values)
    x_values = list(range(n))

    # Compute means
    x_mean = _mean(x_values)
    y_mean = _mean(values)

    # Compute slope
    numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return (0.0, y_mean, 0.0)

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Compute R^2
    y_pred = [slope * x + intercept for x in x_values]
    ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))

    if ss_tot == 0:
        r_squared = 1.0 if ss_res == 0 else 0.0
    else:
        r_squared = max(0.0, 1.0 - (ss_res / ss_tot))

    return (slope, intercept, r_squared)


def _autocorrelation(values: list[float], lag: int) -> float:
    """
    Compute autocorrelation at a given lag.

    Returns correlation coefficient between values[:-lag] and values[lag:].
    """
    if len(values) < lag + 1:
        return 0.0

    v1 = values[:-lag]
    v2 = values[lag:]

    if len(v1) < 2 or len(v2) < 2:
        return 0.0

    mean1 = _mean(v1)
    mean2 = _mean(v2)

    numerator = sum((v1[i] - mean1) * (v2[i] - mean2) for i in range(len(v1)))
    denom1 = sum((v1[i] - mean1) ** 2 for i in range(len(v1)))
    denom2 = sum((v2[i] - mean2) ** 2 for i in range(len(v2)))

    if denom1 == 0 or denom2 == 0:
        return 0.0

    return numerator / (denom1 * denom2) ** 0.5


def _find_local_extremum(values: list[float]) -> int | None:
    """
    Find index of a local minimum or maximum.

    Returns index of the turning point, or None if no clear extremum.
    """
    if len(values) < 3:
        return None

    for i in range(1, len(values) - 1):
        # Local minimum
        if values[i] < values[i - 1] and values[i] < values[i + 1]:
            return i
        # Local maximum
        if values[i] > values[i - 1] and values[i] > values[i + 1]:
            return i

    return None


# =====================================================================
# TRAJECTORY ENGINE
# =====================================================================


class TrajectoryEngine:
    """Advanced trajectory analysis engine."""

    def __init__(self, db_path: Path | None = None):
        """Initialize with optional database path."""
        self.db_path = db_path
        try:
            self.engine = get_engine(db_path)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.warning(f"Could not initialize query engine: {e}")
            self.engine = None

    # =====================================================================
    # VELOCITY COMPUTATION
    # =====================================================================

    def compute_velocity(self, values: list[float], period_days: int = 30) -> VelocityResult:
        """
        Compute rate of change per period.

        Args:
            values: List of metric values (oldest first)
            period_days: Number of days between measurements

        Returns:
            VelocityResult with current and average velocity
        """
        clean_values = [v for v in values if v is not None]

        if len(clean_values) < 2:
            return VelocityResult(
                current_velocity=0.0,
                avg_velocity=0.0,
                direction="zero",
                period_days=period_days,
            )

        # Current velocity: (last - second-to-last) / period
        current_velocity = (clean_values[-1] - clean_values[-2]) / period_days

        # Average velocity: slope from linear regression
        slope, _, _ = _linear_regression(clean_values)
        avg_velocity = slope / period_days

        # Direction
        if current_velocity > 0.001:
            direction = "positive"
        elif current_velocity < -0.001:
            direction = "negative"
        else:
            direction = "zero"

        return VelocityResult(
            current_velocity=current_velocity,
            avg_velocity=avg_velocity,
            direction=direction,
            period_days=period_days,
        )

    # =====================================================================
    # ACCELERATION COMPUTATION
    # =====================================================================

    def compute_acceleration(
        self, values: list[float], period_days: int = 30
    ) -> AccelerationResult:
        """
        Compute rate of velocity change.

        Args:
            values: List of metric values (oldest first)
            period_days: Number of days between measurements

        Returns:
            AccelerationResult with acceleration and direction change
        """
        clean_values = [v for v in values if v is not None]

        if len(clean_values) < 3:
            return AccelerationResult(
                current_acceleration=0.0,
                is_accelerating=False,
                direction_change=False,
            )

        # Compute velocities for consecutive pairs
        velocities = [
            (clean_values[i + 1] - clean_values[i]) / period_days
            for i in range(len(clean_values) - 1)
        ]

        if len(velocities) < 2:
            return AccelerationResult(
                current_acceleration=0.0,
                is_accelerating=False,
                direction_change=False,
            )

        # Current acceleration: change in velocity
        current_accel = velocities[-1] - velocities[-2]
        is_accel = abs(current_accel) > 0.001

        # Direction change: did velocity sign change?
        dir_change = velocities[-2] * velocities[-1] < 0

        return AccelerationResult(
            current_acceleration=current_accel,
            is_accelerating=is_accel,
            direction_change=dir_change,
        )

    # =====================================================================
    # TREND DETECTION
    # =====================================================================

    def detect_trend(self, values: list[float]) -> TrendAnalysis:
        """
        Comprehensive trend detection.

        Args:
            values: List of metric values (oldest first)

        Returns:
            TrendAnalysis with direction, slope, R^2, confidence
        """
        clean_values = [v for v in values if v is not None]

        # Insufficient data
        if len(clean_values) < 2:
            return TrendAnalysis(
                direction=TrendDirection.INSUFFICIENT_DATA,
                slope=0.0,
                r_squared=0.0,
                confidence="low",
                volatility=0.0,
                turning_point_idx=None,
                summary="Insufficient data for trend analysis",
            )

        # Linear regression
        slope, _, r_squared = _linear_regression(clean_values)

        # Volatility: coefficient of variation
        mean_val = _mean(clean_values)
        std_val = _std(clean_values)
        volatility = (std_val / mean_val) if mean_val != 0 else 0.0

        # Find turning point
        turning_point = _find_local_extremum(clean_values)

        # Determine direction
        if volatility > 0.5:
            direction = TrendDirection.VOLATILE
        elif slope > 0.01:
            # Accelerating vs rising
            if slope > 0.05 or len(clean_values) >= 4:
                direction = TrendDirection.ACCELERATING_UP
            else:
                direction = TrendDirection.RISING
        elif slope < -0.01:
            # Accelerating vs declining
            if slope < -0.05 or len(clean_values) >= 4:
                direction = TrendDirection.ACCELERATING_DOWN
            else:
                direction = TrendDirection.DECLINING
        else:
            direction = TrendDirection.STABLE

        # Confidence based on R^2 and data completeness
        if r_squared > 0.7:
            confidence = "high"
        elif r_squared > 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        # Summary
        summary = f"{direction.value.replace('_', ' ').title()}: slope={slope:.4f}, R²={r_squared:.2f}, volatility={volatility:.2f}"

        return TrendAnalysis(
            direction=direction,
            slope=slope,
            r_squared=r_squared,
            confidence=confidence,
            volatility=volatility,
            turning_point_idx=turning_point,
            summary=summary,
        )

    # =====================================================================
    # SEASONALITY DETECTION
    # =====================================================================

    def detect_seasonality(self, values: list[float], min_periods: int = 4) -> SeasonalityResult:
        """
        Detect recurring patterns (seasonality).

        Args:
            values: List of metric values (oldest first)
            min_periods: Minimum periodicity to consider

        Returns:
            SeasonalityResult with detected period and strength
        """
        clean_values = [v for v in values if v is not None]

        if len(clean_values) < min_periods * 2:
            return SeasonalityResult(
                has_seasonality=False,
                period_length=None,
                seasonal_strength=0.0,
                peak_period_idx=None,
            )

        # Test for seasonality at different lags
        best_lag = None
        best_correlation = 0.0

        for lag in range(min_periods, len(clean_values) // 2):
            corr = _autocorrelation(clean_values, lag)
            if corr > best_correlation:
                best_correlation = corr
                best_lag = lag

        # Threshold for seasonality detection
        has_seasonality = best_correlation > 0.4

        # Find peak period
        peak_idx = None
        if has_seasonality and best_lag:
            # Find highest value in first period
            period_values = clean_values[: best_lag + 1]
            peak_idx = period_values.index(max(period_values))

        return SeasonalityResult(
            has_seasonality=has_seasonality,
            period_length=best_lag,
            seasonal_strength=best_correlation,
            peak_period_idx=peak_idx,
        )

    # =====================================================================
    # PROJECTION
    # =====================================================================

    def project_forward(self, values: list[float], periods_ahead: int = 3) -> ProjectionResult:
        """
        Project forward using linear extrapolation.

        Args:
            values: List of metric values (oldest first)
            periods_ahead: Number of periods to project

        Returns:
            ProjectionResult with projections and confidence bounds
        """
        clean_values = [v for v in values if v is not None]

        if len(clean_values) < 2:
            return ProjectionResult(
                projected_values=[],
                upper_bound=[],
                lower_bound=[],
                confidence_pct=0.0,
                method="none",
            )

        # Linear regression
        slope, intercept, r_squared = _linear_regression(clean_values)

        # Project forward
        n = len(clean_values)
        projected = []
        for i in range(n, n + periods_ahead):
            projected.append(slope * i + intercept)

        # Confidence bounds: ±1.96*std for 95% CI
        std_val = _std(clean_values)
        confidence_95 = 1.96 * std_val

        upper = [v + confidence_95 for v in projected]
        lower = [max(0, v - confidence_95) for v in projected]

        confidence_pct = r_squared * 100

        return ProjectionResult(
            projected_values=projected,
            upper_bound=upper,
            lower_bound=lower,
            confidence_pct=confidence_pct,
            method="linear_extrapolation",
        )

    # =====================================================================
    # FULL TRAJECTORY
    # =====================================================================

    def client_full_trajectory(self, client_id: str, windows: int = 12) -> FullTrajectory | None:
        """
        Comprehensive trajectory analysis for a client.

        Args:
            client_id: Client ID
            windows: Number of time windows to analyze

        Returns:
            FullTrajectory or None if client not found
        """
        if not self.engine:
            logger.error("Query engine not initialized")
            return None

        try:
            # Get client info
            profile = self.engine.client_deep_profile(client_id)
            if not profile:
                return None

            client_name = profile.get("client_name", client_id)

            # Get trajectory from query engine
            traj = self.engine.client_trajectory(
                client_id, window_size_days=30, num_windows=windows
            )

            # Analyze each metric
            metrics = {}
            projections = {}

            for metric_name in [
                "tasks_created",
                "tasks_completed",
                "invoices_issued",
                "amount_invoiced",
                "communications_count",
            ]:
                values = [w["metrics"].get(metric_name, 0) or 0 for w in traj["windows"]]

                # Trend
                trend = self.detect_trend(values)
                metrics[metric_name] = trend

                # Projection
                if sum(values) > 0:
                    proj = self.project_forward(values, periods_ahead=3)
                    projections[metric_name] = proj

            # Compute overall health
            revenue_trend = metrics.get(
                "amount_invoiced",
                TrendAnalysis(
                    direction=TrendDirection.STABLE,
                    slope=0.0,
                    r_squared=0.0,
                    confidence="low",
                    volatility=0.0,
                    turning_point_idx=None,
                    summary="No data",
                ),
            )

            task_trend = metrics.get(
                "tasks_completed",
                TrendAnalysis(
                    direction=TrendDirection.STABLE,
                    slope=0.0,
                    r_squared=0.0,
                    confidence="low",
                    volatility=0.0,
                    turning_point_idx=None,
                    summary="No data",
                ),
            )

            if (
                revenue_trend.direction == TrendDirection.ACCELERATING_UP
                or task_trend.direction == TrendDirection.ACCELERATING_UP
            ):
                overall_health = "IMPROVING"
            elif revenue_trend.direction in (
                TrendDirection.DECLINING,
                TrendDirection.ACCELERATING_DOWN,
            ) or task_trend.direction in (
                TrendDirection.DECLINING,
                TrendDirection.ACCELERATING_DOWN,
            ):
                overall_health = "DECLINING"
            elif (
                revenue_trend.direction == TrendDirection.VOLATILE
                or task_trend.direction == TrendDirection.VOLATILE
            ):
                overall_health = "CRITICAL"
            else:
                overall_health = "STABLE"

            # Velocity and acceleration
            revenue_values = [w["metrics"].get("amount_invoiced", 0) or 0 for w in traj["windows"]]
            velocity = self.compute_velocity(revenue_values, period_days=30)
            acceleration = self.compute_acceleration(revenue_values, period_days=30)

            summary = f"Client {client_name}: {overall_health.lower()}. "
            summary += (
                f"Revenue {revenue_trend.direction.value}, Tasks {task_trend.direction.value}. "
            )
            summary += f"Velocity: {velocity.direction}, Acceleration: {'increasing' if acceleration.is_accelerating else 'stable'}"

            return FullTrajectory(
                entity_id=client_id,
                entity_name=client_name,
                entity_type="client",
                metrics=metrics,
                projections=projections,
                velocity=velocity,
                acceleration=acceleration,
                overall_health=overall_health,
                summary=summary,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing client trajectory: {e}", exc_info=True)
            return None

    def portfolio_health_trajectory(self) -> list[FullTrajectory]:
        """
        Trajectory for all clients in portfolio.

        Returns:
            List of FullTrajectory objects
        """
        if not self.engine:
            logger.error("Query engine not initialized")
            return []

        try:
            clients = self.engine.client_portfolio_overview()
            results = []

            for client in clients:
                traj = self.client_full_trajectory(client["client_id"], windows=12)
                if traj:
                    results.append(traj)

            return results

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error computing portfolio trajectory: {e}", exc_info=True)
            return []
