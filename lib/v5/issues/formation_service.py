"""
Time OS V5 — Issue Formation Service

Forms issues from signal patterns.
"""

import json
import logging
from typing import Any

from ..database import Database
from ..models import generate_id, now_iso
from ..repositories.signal_repository import SignalRepository
from .patterns import ALL_PATTERNS, IssuePattern

logger = logging.getLogger(__name__)


class IssueFormationService:
    """
    Forms issues from signal patterns.

    Scans active signals, groups by scope, checks against patterns,
    and creates or updates issues when thresholds are met.
    """

    def __init__(self, db: Database):
        """
        Initialize formation service.

        Args:
            db: Database instance
        """
        self.db = db
        self.signal_repo = SignalRepository(db)

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    def run_formation(self) -> dict[str, int]:
        """
        Run issue formation for all patterns.

        Returns:
            Dict with stats (created, updated, unchanged)
        """
        stats = {"created": 0, "updated": 0, "unchanged": 0}

        logger.info("Starting issue formation...")

        for pattern in ALL_PATTERNS:
            pattern_stats = self._process_pattern(pattern)
            stats["created"] += pattern_stats["created"]
            stats["updated"] += pattern_stats["updated"]
            stats["unchanged"] += pattern_stats["unchanged"]

        logger.info(
            f"Issue formation complete: {stats['created']} created, "
            f"{stats['updated']} updated, {stats['unchanged']} unchanged"
        )

        return stats

    # =========================================================================
    # Pattern Processing
    # =========================================================================

    def _process_pattern(self, pattern: IssuePattern) -> dict[str, int]:
        """
        Process a single pattern across all scopes.

        Args:
            pattern: Pattern to process

        Returns:
            Dict with stats
        """
        stats = {"created": 0, "updated": 0, "unchanged": 0}

        # Get scope field based on pattern scope level
        scope_field = f"scope_{pattern.scope_level}_id"

        # Build signal type list
        all_types = pattern.required_signal_types + pattern.optional_signal_types

        if not all_types:
            # For relationship_at_risk, use any negative signal
            all_types = pattern.optional_signal_types or []
            if not all_types:
                return stats

        # Query signals grouped by scope
        signal_groups = self.signal_repo.find_for_issue_formation(
            signal_types=all_types,
            scope_column=scope_field,
            min_count=pattern.min_signal_count,
            min_magnitude=pattern.min_negative_magnitude,
        )

        for group in signal_groups:
            result = self._process_signal_group(pattern, group)
            stats[result] += 1

        return stats

    def _process_signal_group(
        self, pattern: IssuePattern, signal_group: dict[str, Any]
    ) -> str:
        """
        Process a signal group and create/update issue.

        Args:
            pattern: Pattern being matched
            signal_group: Grouped signal data

        Returns:
            'created', 'updated', or 'unchanged'
        """
        scope_id = signal_group["scope_id"]
        if not scope_id:
            return "unchanged"

        signal_ids = (
            signal_group["signal_ids"].split(",") if signal_group["signal_ids"] else []
        )

        # Check for existing issue
        existing = self.db.fetch_one(
            """
            SELECT id, signal_ids, balance_negative_magnitude, state, severity
            FROM issues_v5
            WHERE issue_subtype = ?
              AND scope_id = ?
              AND state NOT IN ('closed', 'resolved', 'monitoring')
        """,
            (pattern.issue_subtype, scope_id),
        )

        # Calculate balance
        negative_mag = signal_group["negative_magnitude"] or 0
        positive_mag = signal_group["positive_magnitude"] or 0
        net_score = positive_mag - negative_mag
        signal_group["category_count"] or 1

        # Determine severity
        severity = self._determine_severity(pattern, signal_group)

        # Get scope name
        scope_name = self._get_scope_name(pattern.scope_level, scope_id)

        # Build headline
        headline = self._build_headline(pattern, signal_group, scope_name)

        if existing:
            return self._update_existing_issue(
                existing,
                pattern,
                signal_group,
                severity,
                headline,
                negative_mag,
                positive_mag,
            )
        return self._create_new_issue(
            pattern,
            signal_group,
            scope_id,
            signal_ids,
            severity,
            headline,
            negative_mag,
            positive_mag,
            net_score,
        )

    # =========================================================================
    # Issue Creation
    # =========================================================================

    def _create_new_issue(
        self,
        pattern: IssuePattern,
        signal_group: dict[str, Any],
        scope_id: str,
        signal_ids: list[str],
        severity: str,
        headline: str,
        negative_mag: float,
        positive_mag: float,
        net_score: float,
    ) -> str:
        """Create a new issue."""

        issue_id = generate_id("iss")
        now = now_iso()

        # Determine if should surface immediately
        priority = self._calculate_priority(severity, negative_mag, pattern.scope_level)
        state = "surfaced" if priority > 50 else "detected"
        surfaced_at = now if state == "surfaced" else None

        self.db.insert(
            "issues_v5",
            {
                "id": issue_id,
                "issue_type": pattern.issue_type,
                "issue_subtype": pattern.issue_subtype,
                "scope_type": pattern.scope_level,
                "scope_id": scope_id,
                "scope_client_id": signal_group.get("scope_client_id"),
                "scope_brand_id": signal_group.get("scope_brand_id"),
                "scope_retainer_id": signal_group.get("scope_retainer_id"),
                "headline": headline,
                "severity": severity,
                "priority_score": priority,
                "trajectory": "stable",
                "signal_ids": json.dumps(signal_ids),
                "balance_negative_count": len(list(signal_ids)),
                "balance_negative_magnitude": negative_mag,
                "balance_neutral_count": 0,
                "balance_positive_count": 0,
                "balance_positive_magnitude": positive_mag,
                "balance_net_score": net_score,
                "recommended_action": pattern.recommended_action_template,
                "recommended_owner_role": pattern.recommended_owner_role,
                "recommended_urgency": pattern.recommended_urgency,
                "state": state,
                "detected_at": now,
                "surfaced_at": surfaced_at,
                "created_at": now,
                "updated_at": now,
            },
        )

        # Mark signals as consumed
        self.signal_repo.mark_consumed(signal_ids, issue_id)

        logger.info(f"Created issue {issue_id}: {pattern.issue_subtype} for {scope_id}")

        return "created"

    def _update_existing_issue(
        self,
        existing: dict[str, Any],
        pattern: IssuePattern,
        signal_group: dict[str, Any],
        severity: str,
        headline: str,
        negative_mag: float,
        positive_mag: float,
    ) -> str:
        """Update an existing issue."""

        issue_id = existing["id"]
        old_magnitude = existing["balance_negative_magnitude"] or 0

        # Determine trajectory
        if negative_mag > old_magnitude * 1.1:
            trajectory = "worsening"
        elif negative_mag < old_magnitude * 0.9:
            trajectory = "improving"
        else:
            trajectory = "stable"

        # Check if severity changed
        if severity != existing["severity"]:
            # Severity changed, might need to re-surface
            priority = self._calculate_priority(
                severity, negative_mag, pattern.scope_level
            )
        else:
            priority = self._calculate_priority(
                existing["severity"], negative_mag, pattern.scope_level
            )

        # Update signal IDs
        new_signal_ids = (
            signal_group["signal_ids"].split(",") if signal_group["signal_ids"] else []
        )

        self.db.update(
            "issues_v5",
            {
                "signal_ids": json.dumps(new_signal_ids),
                "balance_negative_count": len(new_signal_ids),
                "balance_negative_magnitude": negative_mag,
                "balance_positive_magnitude": positive_mag,
                "balance_net_score": positive_mag - negative_mag,
                "severity": severity,
                "priority_score": priority,
                "trajectory": trajectory,
                "headline": headline,
                "updated_at": now_iso(),
            },
            "id = ?",
            [issue_id],
        )

        logger.debug(f"Updated issue {issue_id}: trajectory={trajectory}")

        return "updated"

    # =========================================================================
    # Helpers
    # =========================================================================

    def _determine_severity(
        self, pattern: IssuePattern, signal_group: dict[str, Any]
    ) -> str:
        """Determine issue severity based on pattern rules."""

        magnitude = signal_group["negative_magnitude"] or 0
        signal_count = signal_group["signal_count"] or 0
        category_count = signal_group["category_count"] or 1

        for severity, rules in pattern.severity_rules.items():
            met = True

            if "magnitude" in rules and magnitude < rules["magnitude"]:
                met = False
            if "overdue_count" in rules and signal_count < rules["overdue_count"]:
                met = False
            if "categories" in rules and category_count < rules["categories"]:
                met = False
            if "count" in rules and signal_count < rules["count"]:
                met = False

            if met:
                return severity

        return "medium"

    def _calculate_priority(
        self, severity: str, magnitude: float, scope_level: str
    ) -> float:
        """Calculate priority score."""

        severity_base = {
            "critical": 100,
            "high": 70,
            "medium": 40,
            "low": 20,
        }

        scope_mult = {
            "task": 0.5,
            "project": 1.0,
            "retainer": 1.2,
            "brand": 1.5,
            "client": 2.0,
        }

        base = severity_base.get(severity, 40)
        mult = scope_mult.get(scope_level, 1.0)

        return base * mult * (1 + magnitude * 0.1)

    def _get_scope_name(self, scope_level: str, scope_id: str) -> str:
        """Get display name for scope."""

        table_map = {
            "task": ("tasks_v5", "title"),
            "project": ("projects_v5", "name"),
            "retainer": ("retainers", "name"),
            "brand": ("brands", "name"),
            "client": ("clients", "name"),
        }

        if scope_level not in table_map:
            return scope_id[:20]

        table, name_col = table_map[scope_level]

        row = self.db.fetch_one(
            f"SELECT {name_col} as name FROM {table} WHERE id = ?", (scope_id,)
        )

        return row["name"] if row else scope_id[:20]

    def _build_headline(
        self, pattern: IssuePattern, signal_group: dict[str, Any], scope_name: str
    ) -> str:
        """Build issue headline from template."""

        headline = pattern.headline_template

        # Calculate amount (for financial patterns)
        amount = signal_group.get("negative_magnitude", 0) * 10000
        amount_str = f"{amount:,.0f}"

        # Basic substitutions
        headline = headline.replace("{scope_name}", scope_name or "Unknown")
        headline = headline.replace(
            "{overdue_count}", str(signal_group.get("signal_count", 0))
        )
        headline = headline.replace("{approaching_count}", "0")
        headline = headline.replace(
            "{version_count}", str(signal_group.get("signal_count", 0))
        )
        headline = headline.replace("{gap_days}", "7")
        headline = headline.replace("{amount:,.0f}", amount_str)
        headline = headline.replace("{amount}", amount_str)
        headline = headline.replace("{currency}", "AED")
        return headline.replace("{bucket}", "30+")
