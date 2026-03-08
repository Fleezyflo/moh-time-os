"""
Adaptive Threshold Engine — Adjusts signal thresholds based on effectiveness.

Analyzes signal feedback (true positive rate, action rate) and proposes
threshold changes. Seasonal/contextual modifiers apply adjustments driven
by BusinessCalendar (Ramadan, Q4, summer).

Constraints:
- Maximum +-30% change per adjustment cycle
- Cooldown period between adjustments (default 7 days)
- Oscillation detection: if a threshold flip-flops 3+ times, freeze it
- All adjustments logged to adjustment_history for audit

GAP-10-01 (threshold adjustment engine)
GAP-10-02 (seasonal/contextual modifiers)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from lib import paths
from lib.intelligence.temporal import BusinessCalendar

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

MAX_CHANGE_PER_CYCLE = 0.30  # +-30% cap
DEFAULT_COOLDOWN_DAYS = 7
OSCILLATION_THRESHOLD = 3  # Freeze after 3 flip-flops
MIN_FEEDBACK_SAMPLES = 10  # Need at least 10 samples to adjust

# Seasonal modifier presets: season_name -> signal_prefix -> multiplier
# > 1.0 = relax threshold (higher value needed to trigger)
# < 1.0 = tighten threshold (lower value triggers sooner)
SEASONAL_MODIFIERS: dict[str, dict[str, float]] = {
    "ramadan": {
        "sig_client_comm_drop": 1.25,  # Relax communication expectations
        "sig_person_overloaded": 1.20,  # Relax workload thresholds
        "sig_project_stalled": 1.30,  # Relax stalled detection
    },
    "q4_close": {
        "sig_client_invoice_aging": 0.80,  # Tighten AR monitoring
        "sig_portfolio_revenue_concentration": 0.85,  # Tighten concentration watch
        "sig_client_score_critical": 0.90,  # Tighten health monitoring
    },
    "summer_slowdown": {
        "sig_client_comm_drop": 1.20,  # Relax communication expectations
        "sig_person_overloaded": 1.15,  # Relax workload thresholds
        "sig_project_stalled": 1.20,  # Relax stalled detection
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SignalEffectiveness:
    """Effectiveness metrics for a single signal."""

    signal_id: str
    total_fires: int = 0
    true_positives: int = 0
    false_positives: int = 0
    actions_taken: int = 0
    true_positive_rate: float = 0.0
    action_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "total_fires": self.total_fires,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "actions_taken": self.actions_taken,
            "true_positive_rate": self.true_positive_rate,
            "action_rate": self.action_rate,
        }


@dataclass
class ThresholdAdjustment:
    """A proposed or applied threshold adjustment."""

    signal_id: str
    field: str  # "value" or "threshold_ratio"
    old_value: float
    new_value: float
    reason: str
    adjustment_type: str  # "effectiveness" | "seasonal" | "manual"
    applied: bool = False
    applied_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "adjustment_type": self.adjustment_type,
            "applied": self.applied,
            "applied_at": self.applied_at,
        }


@dataclass
class AdjustmentHistory:
    """History of all adjustments for a signal."""

    signal_id: str
    adjustments: list[ThresholdAdjustment] = field(default_factory=list)
    last_adjusted_at: str | None = None
    frozen: bool = False
    freeze_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "last_adjusted_at": self.last_adjusted_at,
            "frozen": self.frozen,
            "freeze_reason": self.freeze_reason,
        }


# =============================================================================
# THRESHOLD ADJUSTER
# =============================================================================


class ThresholdAdjuster:
    """
    Adjusts signal thresholds based on effectiveness data and seasonal context.

    Reads thresholds.yaml, computes effectiveness from signal feedback,
    proposes bounded changes, applies seasonal modifiers, and writes back.

    Usage:
        adjuster = ThresholdAdjuster()
        report = adjuster.run_adjustment_cycle(feedback_data)
    """

    def __init__(
        self,
        thresholds_path: Path | None = None,
        calendar: BusinessCalendar | None = None,
        cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    ):
        if thresholds_path is None:
            thresholds_path = paths.project_root() / "lib" / "intelligence" / "thresholds.yaml"
        self._thresholds_path = thresholds_path
        self._calendar = calendar or BusinessCalendar()
        self._cooldown_days = cooldown_days

        # Load current thresholds
        self._thresholds = self._load_thresholds()

        # In-memory adjustment history (persisted via run results)
        self._history: dict[str, AdjustmentHistory] = {}

    def run_adjustment_cycle(
        self,
        feedback: list[dict],
        reference_date: date | None = None,
    ) -> dict:
        """
        Run a full adjustment cycle: analyze effectiveness, apply modifiers, propose changes.

        Args:
            feedback: List of signal feedback dicts with keys:
                signal_id, was_true_positive (bool), action_taken (bool)
            reference_date: Date for seasonal context. Defaults to today.

        Returns:
            dict with keys: effectiveness, seasonal_modifiers, adjustments,
            frozen_signals, applied_count, skipped_count
        """
        ref_date = reference_date or date.today()

        # 1. Compute signal effectiveness
        effectiveness = self._compute_effectiveness(feedback)

        # 2. Get active seasonal modifiers
        season = self._calendar.get_season(ref_date)
        active_modifiers = SEASONAL_MODIFIERS.get(season, {})

        # Check Ramadan separately (it's not a "season" in the config sense)
        day_ctx = self._calendar.day_context(ref_date)
        if day_ctx.is_ramadan and "ramadan" not in season:
            active_modifiers = {**active_modifiers, **SEASONAL_MODIFIERS.get("ramadan", {})}

        # 3. Generate adjustments
        adjustments: list[ThresholdAdjustment] = []
        applied_count = 0
        skipped_count = 0

        # Effectiveness-based adjustments
        for eff in effectiveness:
            adj = self._propose_effectiveness_adjustment(eff)
            if adj is None:
                continue
            if self._can_adjust(adj.signal_id):
                adjustments.append(adj)
            else:
                skipped_count += 1

        # Seasonal adjustments
        for signal_id, multiplier in active_modifiers.items():
            adj = self._propose_seasonal_adjustment(signal_id, multiplier, season)
            if adj is not None and self._can_adjust(signal_id):
                adjustments.append(adj)

        # 4. Apply adjustments (capped)
        for adj in adjustments:
            self._apply_adjustment(adj)
            applied_count += 1

        # 5. Build report
        frozen_signals = [h.to_dict() for h in self._history.values() if h.frozen]

        return {
            "timestamp": datetime.now().isoformat(),
            "reference_date": ref_date.isoformat(),
            "season": season,
            "effectiveness": [e.to_dict() for e in effectiveness],
            "seasonal_modifiers": active_modifiers,
            "adjustments": [a.to_dict() for a in adjustments],
            "frozen_signals": frozen_signals,
            "applied_count": applied_count,
            "skipped_count": skipped_count,
        }

    def get_seasonal_modifiers(self, reference_date: date | None = None) -> dict:
        """Get active seasonal modifiers for a date."""
        ref_date = reference_date or date.today()
        season = self._calendar.get_season(ref_date)
        modifiers = dict(SEASONAL_MODIFIERS.get(season, {}))

        day_ctx = self._calendar.day_context(ref_date)
        if day_ctx.is_ramadan and "ramadan" not in season:
            modifiers.update(SEASONAL_MODIFIERS.get("ramadan", {}))

        return {
            "season": season,
            "is_ramadan": day_ctx.is_ramadan,
            "modifiers": modifiers,
        }

    def get_history(self, signal_id: str | None = None) -> list[dict]:
        """Get adjustment history, optionally filtered by signal."""
        if signal_id:
            hist = self._history.get(signal_id)
            return [hist.to_dict()] if hist else []
        return [h.to_dict() for h in self._history.values()]

    def get_current_thresholds(self) -> dict:
        """Return current threshold configuration."""
        return dict(self._thresholds)

    # -------------------------------------------------------------------------
    # Effectiveness computation
    # -------------------------------------------------------------------------

    def _compute_effectiveness(self, feedback: list[dict]) -> list[SignalEffectiveness]:
        """Aggregate feedback into per-signal effectiveness metrics."""
        by_signal: dict[str, SignalEffectiveness] = {}

        for entry in feedback:
            sig_id = entry.get("signal_id", "")
            if not sig_id:
                continue

            if sig_id not in by_signal:
                by_signal[sig_id] = SignalEffectiveness(signal_id=sig_id)

            eff = by_signal[sig_id]
            eff.total_fires += 1

            if entry.get("was_true_positive"):
                eff.true_positives += 1
            else:
                eff.false_positives += 1

            if entry.get("action_taken"):
                eff.actions_taken += 1

        # Compute rates
        for eff in by_signal.values():
            if eff.total_fires > 0:
                eff.true_positive_rate = eff.true_positives / eff.total_fires
                eff.action_rate = eff.actions_taken / eff.total_fires

        return list(by_signal.values())

    # -------------------------------------------------------------------------
    # Adjustment proposals
    # -------------------------------------------------------------------------

    def _propose_effectiveness_adjustment(
        self, eff: SignalEffectiveness
    ) -> ThresholdAdjustment | None:
        """Propose adjustment based on effectiveness metrics."""
        if eff.total_fires < MIN_FEEDBACK_SAMPLES:
            return None

        signal_config = self._thresholds.get("signals", {}).get(eff.signal_id)
        if not signal_config:
            return None

        # Determine which field to adjust
        if "value" in signal_config:
            field_name = "value"
            current = float(signal_config["value"])
        elif "threshold_ratio" in signal_config:
            field_name = "threshold_ratio"
            current = float(signal_config["threshold_ratio"])
        else:
            return None

        # High false positive rate -> relax threshold (increase value)
        if eff.true_positive_rate < 0.5:
            change = min(MAX_CHANGE_PER_CYCLE, 0.5 - eff.true_positive_rate)
            new_value = current * (1 + change)
            reason = (
                f"Low true positive rate ({eff.true_positive_rate:.1%}), "
                f"relaxing threshold by {change:.1%}"
            )
        # Low action rate -> may be too sensitive, relax slightly
        elif eff.action_rate < 0.2 and eff.true_positive_rate > 0.7:
            change = 0.10  # Modest relaxation
            new_value = current * (1 + change)
            reason = (
                f"High TPR ({eff.true_positive_rate:.1%}) but low action rate "
                f"({eff.action_rate:.1%}), slight relaxation"
            )
        # High action rate + high TPR -> tighten to catch more
        elif eff.action_rate > 0.8 and eff.true_positive_rate > 0.8:
            change = 0.10
            new_value = current * (1 - change)
            reason = (
                f"High effectiveness (TPR={eff.true_positive_rate:.1%}, "
                f"action={eff.action_rate:.1%}), tightening to catch more"
            )
        else:
            return None

        # Apply cap
        max_new = current * (1 + MAX_CHANGE_PER_CYCLE)
        min_new = current * (1 - MAX_CHANGE_PER_CYCLE)
        new_value = max(min_new, min(max_new, new_value))

        return ThresholdAdjustment(
            signal_id=eff.signal_id,
            field=field_name,
            old_value=current,
            new_value=round(new_value, 4),
            reason=reason,
            adjustment_type="effectiveness",
        )

    def _propose_seasonal_adjustment(
        self, signal_id: str, multiplier: float, season: str
    ) -> ThresholdAdjustment | None:
        """Propose seasonal modifier adjustment."""
        signal_config = self._thresholds.get("signals", {}).get(signal_id)
        if not signal_config:
            return None

        if "value" in signal_config:
            field_name = "value"
            current = float(signal_config["value"])
        elif "threshold_ratio" in signal_config:
            field_name = "threshold_ratio"
            current = float(signal_config["threshold_ratio"])
        else:
            return None

        new_value = current * multiplier

        # Cap to +-30%
        max_new = current * (1 + MAX_CHANGE_PER_CYCLE)
        min_new = current * (1 - MAX_CHANGE_PER_CYCLE)
        new_value = max(min_new, min(max_new, new_value))

        if abs(new_value - current) < 0.001:
            return None

        direction = "relaxing" if multiplier > 1.0 else "tightening"
        return ThresholdAdjustment(
            signal_id=signal_id,
            field=field_name,
            old_value=current,
            new_value=round(new_value, 4),
            reason=f"Seasonal modifier ({season}): {direction} by {abs(multiplier - 1):.0%}",
            adjustment_type="seasonal",
        )

    # -------------------------------------------------------------------------
    # Adjustment application
    # -------------------------------------------------------------------------

    def _can_adjust(self, signal_id: str) -> bool:
        """Check cooldown and oscillation freeze."""
        hist = self._history.get(signal_id)
        if hist is None:
            return True
        if hist.frozen:
            return False

        # Check cooldown
        if hist.last_adjusted_at:
            last = datetime.fromisoformat(hist.last_adjusted_at)
            if datetime.now() - last < timedelta(days=self._cooldown_days):
                return False

        return True

    def _apply_adjustment(self, adj: ThresholdAdjustment) -> None:
        """Apply adjustment to in-memory thresholds and record in history."""
        signals = self._thresholds.get("signals", {})
        if adj.signal_id in signals:
            signals[adj.signal_id][adj.field] = adj.new_value

        adj.applied = True
        adj.applied_at = datetime.now().isoformat()

        # Update history
        if adj.signal_id not in self._history:
            self._history[adj.signal_id] = AdjustmentHistory(signal_id=adj.signal_id)

        hist = self._history[adj.signal_id]
        hist.adjustments.append(adj)
        hist.last_adjusted_at = adj.applied_at

        # Check for oscillation (value goes up then down then up = 3 direction changes)
        self._check_oscillation(hist)

        logger.info(
            "Threshold adjusted: %s.%s %.4f -> %.4f (%s)",
            adj.signal_id,
            adj.field,
            adj.old_value,
            adj.new_value,
            adj.reason,
        )

    def _check_oscillation(self, hist: AdjustmentHistory) -> None:
        """Freeze signal if threshold oscillates too many times."""
        if len(hist.adjustments) < OSCILLATION_THRESHOLD:
            return

        direction_changes = 0
        recent = hist.adjustments[-OSCILLATION_THRESHOLD:]
        for i in range(1, len(recent)):
            prev_direction = recent[i - 1].new_value - recent[i - 1].old_value
            curr_direction = recent[i].new_value - recent[i].old_value
            if (prev_direction > 0 and curr_direction < 0) or (
                prev_direction < 0 and curr_direction > 0
            ):
                direction_changes += 1

        if direction_changes >= OSCILLATION_THRESHOLD - 1:
            hist.frozen = True
            hist.freeze_reason = (
                f"Oscillation detected: {direction_changes} direction changes "
                f"in last {OSCILLATION_THRESHOLD} adjustments"
            )
            logger.warning("Signal %s frozen due to oscillation", hist.signal_id)

    # -------------------------------------------------------------------------
    # I/O
    # -------------------------------------------------------------------------

    def _load_thresholds(self) -> dict:
        """Load thresholds from YAML file."""
        if not self._thresholds_path.exists():
            logger.warning("Thresholds file not found: %s", self._thresholds_path)
            return {"signals": {}}
        try:
            with open(self._thresholds_path) as f:
                data = yaml.safe_load(f) or {}
            return data
        except (ValueError, OSError) as e:
            logger.error("Failed to load thresholds: %s", e)
            return {"signals": {}}

    def save_thresholds(self) -> bool:
        """Write current thresholds back to YAML file."""
        try:
            with open(self._thresholds_path, "w") as f:
                yaml.dump(self._thresholds, f, default_flow_style=False, sort_keys=False)
            logger.info("Thresholds saved to %s", self._thresholds_path)
            return True
        except OSError as e:
            logger.error("Failed to save thresholds: %s", e)
            return False
