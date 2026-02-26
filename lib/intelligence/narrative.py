"""
Narrative Builder — MOH TIME OS

Generates human-readable narratives from intelligence profiles.
Template-driven, no LLM required. Produces 2-3 sentence summaries
and actionable recommendations.

Brief 18 (ID), Task ID-3.1
"""

import logging

logger = logging.getLogger(__name__)


class NarrativeBuilder:
    """Generates human-readable narratives from intelligence profiles."""

    def build_narrative(
        self,
        entity_type: str,
        entity_name: str,
        health_score: float,
        health_classification: str,
        active_signals: list[dict],
        active_patterns: list[dict],
        compound_risks: list[dict],
        cost_profile: dict,
        trajectory_direction: str,
        projected_score_30d: float,
    ) -> str:
        """
        Generate 2-3 sentence summary of entity intelligence.

        Sentence 1: Health status.
        Sentence 2: Key findings.
        Sentence 3: Cost context (if relevant).
        """
        sentences = []

        # Sentence 1: Health status
        s1 = f"{entity_name} is {health_classification} with a health score of {health_score:.0f}."
        if trajectory_direction == "toward_risk":
            s1 += f" Score trending downward (projected {projected_score_30d:.0f} in 30 days)."
        elif trajectory_direction == "toward_health":
            s1 += f" Score improving (projected {projected_score_30d:.0f} in 30 days)."
        sentences.append(s1)

        # Sentence 2: Key findings
        critical_signals = [s for s in active_signals if s.get("severity") == "CRITICAL"]
        warning_signals = [s for s in active_signals if s.get("severity") == "WARNING"]
        high_conf_risks = [r for r in compound_risks if r.get("confidence", 0) > 0.7]
        worsening_patterns = [p for p in active_patterns if p.get("direction") == "worsening"]

        if critical_signals:
            s2 = f"Critical: {self._format_signal_summary(critical_signals)}."
        elif high_conf_risks:
            s2 = f"Cross-domain risk: {high_conf_risks[0].get('title', 'compound risk detected')}."
        elif warning_signals:
            s2 = f"Warning: {self._format_signal_summary(warning_signals)}."
        elif worsening_patterns:
            s2 = f"Pattern detected: {self._format_pattern_summary(worsening_patterns)}."
        else:
            s2 = "No significant issues detected."
        sentences.append(s2)

        # Sentence 3: Cost context (only if relevant)
        band = cost_profile.get("profitability_band", "unknown")
        if band in ("breakeven", "unprofitable"):
            drivers = cost_profile.get("cost_drivers", [])
            top_driver = drivers[0] if drivers else "multiple factors"
            s3 = f"Cost-to-serve {band}: driven by {top_driver}."
            sentences.append(s3)

        return " ".join(sentences)

    def build_action_recommendations(
        self,
        health_classification: str,
        attention_level: str,
        active_signals: list[dict],
        compound_risks: list[dict],
        cost_profile: dict,
        trajectory_direction: str,
    ) -> list[str]:
        """
        Generate 2-3 recommended next actions based on intelligence.
        """
        actions = []

        # Rule 1: URGENT attention
        if attention_level == "urgent":
            critical = [s for s in active_signals if s.get("severity") == "CRITICAL"]
            if critical:
                actions.append(
                    f"Immediate review needed: {critical[0].get('signal_type', 'critical signal')}"
                )
            elif compound_risks:
                actions.append(
                    f"Immediate review needed: {compound_risks[0].get('title', 'compound risk')}"
                )

        # Rule 2: Trajectory risk
        if trajectory_direction == "toward_risk":
            actions.append("Schedule check-in: health trending downward")

        # Rule 3: Overdue tasks
        overdue_signals = [
            s for s in active_signals if "overdue" in s.get("signal_type", "").lower()
        ]
        if overdue_signals:
            actions.append("Review and prioritize overdue tasks")

        # Rule 4: Communication drop
        comm_signals = [s for s in active_signals if "comm" in s.get("signal_type", "").lower()]
        if comm_signals:
            actions.append("Re-engage: communication volume declining")

        # Rule 5: Unprofitable
        if cost_profile.get("profitability_band") == "unprofitable":
            actions.append("Review pricing: cost-to-serve exceeds revenue")

        # Rule 6: No issues
        if not actions:
            actions.append("Continue monitoring — no action needed")

        # Return top 3, deduplicated
        seen = set()
        unique = []
        for a in actions:
            if a not in seen:
                seen.add(a)
                unique.append(a)
        return unique[:3]

    def build_cross_domain_summary(
        self,
        signals_by_domain: dict[str, list[dict]],
        patterns_by_domain: dict[str, list[dict]],
        compound_risks: list[dict],
    ) -> list[str]:
        """
        Identify and describe issues spanning multiple domains.
        """
        issues = []

        # Domains with both signals and patterns
        all_domains = set(signals_by_domain.keys()) | set(patterns_by_domain.keys())
        affected = [d for d in all_domains if d in signals_by_domain and d in patterns_by_domain]

        for domain in affected:
            sig_count = len(signals_by_domain.get(domain, []))
            pat_count = len(patterns_by_domain.get(domain, []))
            if sig_count > 0 and pat_count > 0:
                issues.append(
                    f"{domain.title()} domain under pressure: "
                    f"{sig_count} active signal(s) and {pat_count} pattern(s) detected"
                )

        # Compound risks are cross-domain by definition
        for risk in compound_risks:
            domains = risk.get("domains_affected", [])
            if len(domains) >= 2:
                domain_str = " and ".join(d if isinstance(d, str) else d.value for d in domains[:2])
                issues.append(f"{risk.get('title', 'Risk')}: spanning {domain_str} domains")

        return issues[:5]

    def _format_signal_summary(self, signals: list[dict]) -> str:
        """Convert signal list to sentence fragment."""
        if not signals:
            return "no signals"
        if len(signals) == 1:
            s = signals[0]
            return f"{s.get('signal_type', 'signal')} ({s.get('severity', 'unknown')})"
        if len(signals) == 2:
            return (
                f"{signals[0].get('signal_type', 'signal')} "
                f"and {signals[1].get('signal_type', 'signal')}"
            )
        return (
            f"{signals[0].get('signal_type', 'signal')}, "
            f"{signals[1].get('signal_type', 'signal')}, "
            f"and {len(signals) - 2} more"
        )

    def _format_pattern_summary(self, patterns: list[dict]) -> str:
        """Convert pattern list to sentence fragment."""
        if not patterns:
            return "no patterns"
        if len(patterns) == 1:
            p = patterns[0]
            return f"{p.get('pattern_type', 'pattern')} ({p.get('direction', 'detected')})"
        return f"{len(patterns)} patterns detected"

    def _format_risk_summary(self, risks: list[dict]) -> str:
        """Convert compound risk list to sentence fragment."""
        if not risks:
            return "no compound risks"
        if len(risks) == 1:
            return risks[0].get("title", "compound risk")
        return f"{len(risks)} compound risks"
