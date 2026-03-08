"""
Calibration Reporter — Weekly/effectiveness/history reports for threshold tuning.

Integrates ThresholdAdjuster results with CalibrationEngine data to produce
reports suitable for morning briefing and API consumption.

GAP-10-03: Calibration reporting
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from lib.calibration import CalibrationEngine
from lib.intelligence.threshold_adjuster import ThresholdAdjuster
from lib.state_store import StateStore, get_store

logger = logging.getLogger(__name__)


@dataclass
class CalibrationReport:
    """Structured calibration report for API and briefing consumption."""

    report_type: str  # "weekly" | "effectiveness" | "history"
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    calibration_data: dict = field(default_factory=dict)
    threshold_data: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type,
            "generated_at": self.generated_at,
            "calibration_data": self.calibration_data,
            "threshold_data": self.threshold_data,
            "recommendations": self.recommendations,
            "summary": self.summary,
        }


class CalibrationReporter:
    """
    Generates calibration reports combining weekly calibration and threshold data.

    Usage:
        reporter = CalibrationReporter()
        report = reporter.weekly_report()
        briefing = reporter.format_for_briefing(report)
    """

    def __init__(
        self,
        store: StateStore | None = None,
        adjuster: ThresholdAdjuster | None = None,
    ):
        self._store = store or get_store()
        self._calibration = CalibrationEngine(self._store)
        self._adjuster = adjuster or ThresholdAdjuster()

    def weekly_report(self, feedback: list[dict] | None = None) -> CalibrationReport:
        """
        Generate a weekly calibration report.

        Combines CalibrationEngine weekly analysis with ThresholdAdjuster
        effectiveness data.

        Args:
            feedback: Signal feedback data for threshold adjustment.
                If None, runs calibration only (no threshold adjustments).

        Returns:
            CalibrationReport with combined data.
        """
        # Run weekly calibration
        try:
            cal_report = self._calibration.run_weekly_calibration()
        except (ValueError, OSError) as e:
            logger.error("Weekly calibration failed: %s", e)
            cal_report = {"error": str(e)}

        # Run threshold adjustment if feedback provided
        threshold_data = {}
        if feedback:
            try:
                threshold_data = self._adjuster.run_adjustment_cycle(feedback)
            except (ValueError, OSError) as e:
                logger.error("Threshold adjustment cycle failed: %s", e)
                threshold_data = {"error": str(e)}

        # Combine recommendations
        recommendations = list(cal_report.get("recommendations", []))
        if threshold_data.get("frozen_signals"):
            frozen_count = len(threshold_data["frozen_signals"])
            recommendations.append(
                f"{frozen_count} signal(s) frozen due to oscillation -- review manually"
            )
        if threshold_data.get("applied_count", 0) > 0:
            recommendations.append(
                f"{threshold_data['applied_count']} threshold(s) adjusted this cycle"
            )

        # Build summary
        summary_parts = []
        satisfaction = cal_report.get("feedback_analysis", {}).get("satisfaction_rate")
        if satisfaction is not None:
            summary_parts.append(f"Satisfaction: {satisfaction:.0%}")
        completed = cal_report.get("completion_patterns", {}).get("total", 0)
        summary_parts.append(f"Tasks completed this week: {completed}")
        if threshold_data.get("applied_count", 0) > 0:
            summary_parts.append(f"Thresholds adjusted: {threshold_data['applied_count']}")

        report = CalibrationReport(
            report_type="weekly",
            calibration_data=cal_report,
            threshold_data=threshold_data,
            recommendations=recommendations,
            summary=". ".join(summary_parts),
        )

        # Persist report
        self._store_report(report)

        return report

    def effectiveness_report(self, feedback: list[dict]) -> CalibrationReport:
        """
        Generate a signal effectiveness report.

        Focuses on threshold adjustment data without running full weekly calibration.

        Args:
            feedback: Signal feedback data.

        Returns:
            CalibrationReport with effectiveness analysis.
        """
        try:
            threshold_data = self._adjuster.run_adjustment_cycle(feedback)
        except (ValueError, OSError) as e:
            logger.error("Effectiveness report failed: %s", e)
            threshold_data = {"error": str(e)}

        effectiveness = threshold_data.get("effectiveness", [])
        high_fpr = [
            e
            for e in effectiveness
            if e.get("true_positive_rate", 1.0) < 0.5 and e.get("total_fires", 0) >= 10
        ]
        low_action = [
            e
            for e in effectiveness
            if e.get("action_rate", 1.0) < 0.2 and e.get("total_fires", 0) >= 10
        ]

        recommendations = []
        for e in high_fpr:
            recommendations.append(
                f"Signal {e['signal_id']} has low TPR ({e['true_positive_rate']:.0%}) "
                f"-- threshold may need manual review"
            )
        for e in low_action:
            recommendations.append(
                f"Signal {e['signal_id']} has low action rate ({e['action_rate']:.0%}) "
                f"-- may be too noisy"
            )

        return CalibrationReport(
            report_type="effectiveness",
            threshold_data=threshold_data,
            recommendations=recommendations,
            summary=f"Analyzed {len(effectiveness)} signals, "
            f"{len(high_fpr)} with low TPR, {len(low_action)} with low action rate",
        )

    def history_report(self, signal_id: str | None = None) -> CalibrationReport:
        """
        Generate a threshold adjustment history report.

        Args:
            signal_id: Optional signal to filter history. None = all signals.

        Returns:
            CalibrationReport with adjustment history.
        """
        history = self._adjuster.get_history(signal_id)
        current = self._adjuster.get_current_thresholds()
        seasonal = self._adjuster.get_seasonal_modifiers()

        return CalibrationReport(
            report_type="history",
            threshold_data={
                "current_thresholds": current,
                "seasonal_context": seasonal,
                "adjustment_history": history,
            },
            summary=f"Threshold history for {signal_id or 'all signals'}, {len(history)} record(s)",
        )

    def format_for_briefing(self, report: CalibrationReport) -> dict:
        """
        Format a calibration report for morning briefing integration.

        Returns a compact dict suitable for inclusion in generate_daily_briefing().
        """
        cal = report.calibration_data
        threshold = report.threshold_data

        briefing = {
            "type": "calibration_update",
            "section": "calibration",
            "headline": report.summary or "Calibration report available",
            "recommendations": report.recommendations[:3],  # Top 3 only
        }

        # Add key metrics if available
        satisfaction = cal.get("feedback_analysis", {}).get("satisfaction_rate")
        if satisfaction is not None:
            briefing["satisfaction_rate"] = satisfaction

        accuracy = cal.get("priority_accuracy", {}).get("accuracy_estimate")
        if accuracy is not None:
            briefing["priority_accuracy"] = accuracy

        if threshold.get("applied_count"):
            briefing["thresholds_adjusted"] = threshold["applied_count"]

        if threshold.get("frozen_signals"):
            briefing["frozen_signals"] = len(threshold["frozen_signals"])

        return briefing

    def _store_report(self, report: CalibrationReport) -> None:
        """Persist report to insights table."""
        try:
            self._store.insert(
                "insights",
                {
                    "id": f"calibration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "type": "calibration_report",
                    "domain": "system",
                    "title": f"Calibration Report ({report.report_type})",
                    "data": json.dumps(report.to_dict()),
                    "confidence": 1.0,
                    "actionable": 1 if report.recommendations else 0,
                    "created_at": datetime.now().isoformat(),
                },
            )
        except (ValueError, OSError) as e:
            logger.error("Failed to store calibration report: %s", e)
