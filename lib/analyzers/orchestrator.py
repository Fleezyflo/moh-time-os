"""
Analyzer Orchestrator - Coordinates all analysis modules.

Runs analyzers in sequence, aggregates results, and produces
unified insights for the autonomous loop.
"""

import json
from datetime import datetime

from .anomaly import AnomalyDetector
from .patterns import PatternAnalyzer
from .priority import PriorityAnalyzer
from .time import TimeAnalyzer


class AnalyzerOrchestrator:
    """Coordinates all analyzers and produces unified insights."""

    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: Combined config for all analyzers
        """
        self.store = store
        self.config = config or {}

        # Initialize analyzers
        self.time_analyzer = TimeAnalyzer(store, self.config.get("lanes", {}))
        self.pattern_analyzer = PatternAnalyzer(store, self.config.get("patterns", {}))
        self.anomaly_detector = AnomalyDetector(store, self.config.get("anomalies", {}))
        self.priority_analyzer = PriorityAnalyzer(store=store)

    def analyze_all(self) -> dict:
        """
        Compatibility method - runs quick check for cycle.
        Use run_full_analysis() for complete analysis.
        """
        quick = self.run_quick_check()

        # Get priority queue
        priority_queue = self.priority_analyzer.analyze()
        top_items = sorted(priority_queue, key=lambda x: x["score"], reverse=True)[:10]

        # Return format expected by autonomous_loop
        return {
            "priority": {"total_items": len(priority_queue), "top_items": top_items},
            "anomalies": {
                "total": quick["anomaly_count"],
                "critical": len(quick["critical_anomalies"]),
                "items": quick["critical_anomalies"],
            },
            "time": {
                "utilization": quick["today_utilization"],
                "conflicts": quick["conflicts"],
            },
            "needs_attention": quick["needs_attention"] or len(priority_queue) > 0,
        }

    def run_full_analysis(self) -> dict:
        """
        Run complete analysis across all dimensions.

        Returns:
            {
                'timestamp': str,
                'time_analysis': {...},
                'patterns': {...},
                'anomalies': [...],
                'insights': [...],
                'recommendations': [...]
            }
        """
        now = datetime.now()

        # Run time analysis
        time_today = self.time_analyzer.analyze_day()
        time_week = self.time_analyzer.analyze_week()
        capacity = self.time_analyzer.get_capacity_forecast(7)

        # Run pattern analysis
        task_patterns = self.pattern_analyzer.analyze_task_patterns(30)
        comm_patterns = self.pattern_analyzer.analyze_communication_patterns(14)
        meeting_patterns = self.pattern_analyzer.analyze_meeting_patterns(30)

        # Run anomaly detection
        anomalies = self.anomaly_detector.run_all_checks()

        # Generate insights
        insights = self._generate_insights(
            time_today,
            time_week,
            capacity,
            task_patterns,
            comm_patterns,
            meeting_patterns,
            anomalies,
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            time_today, capacity, task_patterns, anomalies
        )

        return {
            "timestamp": now.isoformat(),
            "time_analysis": {
                "today": time_today,
                "week": time_week,
                "capacity_forecast": capacity,
            },
            "patterns": {
                "tasks": task_patterns,
                "communications": comm_patterns,
                "meetings": meeting_patterns,
            },
            "anomalies": anomalies,
            "insights": insights,
            "recommendations": recommendations,
        }

    def run_quick_check(self) -> dict:
        """
        Run quick health check (for frequent cycle runs).

        Returns minimal analysis for fast cycles.
        """
        now = datetime.now()

        # Only anomalies and today's time
        anomalies = self.anomaly_detector.run_all_checks()
        time_today = self.time_analyzer.analyze_day()

        # Critical anomalies only
        critical = [a for a in anomalies if a["severity"] in ("critical", "high")]

        return {
            "timestamp": now.isoformat(),
            "today_utilization": time_today["utilization_pct"],
            "conflicts": len(time_today["conflicts"]),
            "critical_anomalies": critical,
            "anomaly_count": len(anomalies),
            "needs_attention": len(critical) > 0,
        }

    def _generate_insights(
        self,
        time_today: dict,
        time_week: dict,
        capacity: dict,
        task_patterns: dict,
        comm_patterns: dict,
        meeting_patterns: dict,
        anomalies: list[dict],
    ) -> list[dict]:
        """Generate actionable insights from analysis."""
        insights = []

        # Capacity insight
        if time_today["utilization_pct"] > 80:
            insights.append(
                {
                    "type": "capacity",
                    "priority": "high",
                    "message": f"Today is {time_today['utilization_pct']}% scheduled. Consider protecting buffer time.",
                    "data": {"utilization": time_today["utilization_pct"]},
                }
            )
        elif time_today["utilization_pct"] < 30:
            insights.append(
                {
                    "type": "capacity",
                    "priority": "info",
                    "message": f"Light schedule today ({time_today['utilization_pct']}%). Good day for deep work.",
                    "data": {"utilization": time_today["utilization_pct"]},
                }
            )

        # Lane budget insights
        for lane, status in time_week.get("budget_status", {}).items():
            if status["pct_used"] > 100:
                insights.append(
                    {
                        "type": "lane_overrun",
                        "priority": "medium",
                        "message": f"{lane} lane is {status['pct_used']}% of weekly budget",
                        "data": {"lane": lane, **status},
                    }
                )

        # Completion rate insight
        if task_patterns["completion_rate"] < 30:
            insights.append(
                {
                    "type": "productivity",
                    "priority": "medium",
                    "message": f"Task completion rate is {task_patterns['completion_rate']}% this month",
                    "data": {"rate": task_patterns["completion_rate"]},
                }
            )

        # Pending responses insight
        if comm_patterns["pending_count"] > 5:
            insights.append(
                {
                    "type": "communications",
                    "priority": "high",
                    "message": f"{comm_patterns['pending_count']} emails need response",
                    "data": {"count": comm_patterns["pending_count"]},
                }
            )

        # Meeting load insight
        if meeting_patterns["avg_meetings_per_day"] > 4:
            insights.append(
                {
                    "type": "meetings",
                    "priority": "medium",
                    "message": f"Averaging {meeting_patterns['avg_meetings_per_day']} meetings/day. Consider consolidation.",
                    "data": {"avg": meeting_patterns["avg_meetings_per_day"]},
                }
            )

        return insights

    def _generate_recommendations(
        self,
        time_today: dict,
        capacity: dict,
        task_patterns: dict,
        anomalies: list[dict],
    ) -> list[dict]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # If conflicts exist
        if time_today["conflicts"]:
            recommendations.append(
                {
                    "type": "scheduling",
                    "action": "resolve_conflicts",
                    "message": f"Resolve {len(time_today['conflicts'])} scheduling conflicts",
                    "priority": "high",
                }
            )

        # If stale tasks exist
        stale = task_patterns.get("stale_tasks", [])
        if len(stale) > 5:
            recommendations.append(
                {
                    "type": "task_hygiene",
                    "action": "review_stale_tasks",
                    "message": f"Review {len(stale)} stale tasks - archive or reactivate",
                    "priority": "medium",
                }
            )

        # If tomorrow has good capacity
        tomorrow = list(capacity.values())[1] if len(capacity) > 1 else None
        if tomorrow and tomorrow["available"] > 180:
            recommendations.append(
                {
                    "type": "planning",
                    "action": "schedule_deep_work",
                    "message": f"Tomorrow has {tomorrow['available']} min available - good for deep work",
                    "priority": "info",
                }
            )

        # Based on critical anomalies
        critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
        if critical_anomalies:
            recommendations.append(
                {
                    "type": "urgent",
                    "action": "address_critical",
                    "message": f"Address {len(critical_anomalies)} critical issues first",
                    "priority": "critical",
                }
            )

        return recommendations

    def save_analysis(self, analysis: dict):
        """Save analysis results to database."""
        self.store.insert(
            "insights",
            {
                "id": f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": "full_analysis",
                "source": "orchestrator",
                "title": "Periodic Analysis",
                "data": json.dumps(analysis),
                "priority": 50,
                "status": "active",
                "created_at": datetime.now().isoformat(),
            },
        )
