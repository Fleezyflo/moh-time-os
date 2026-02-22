# Original governance engine module
"""
Governance Engine - Controls autonomy levels and enforces policies.
THIS IS THE SAFETY LAYER - what the system can do automatically.
"""

import contextlib
import json
from collections import defaultdict
from datetime import datetime
from enum import Enum

import yaml

from lib import paths
from lib.state_store import StateStore, get_store


class DomainMode(Enum):
    """Autonomy levels for each domain."""

    OBSERVE = "observe"  # Only watch, never act
    PROPOSE = "propose"  # Propose actions, require approval for all
    AUTO_LOW = "auto_low"  # Auto low-risk, propose high-risk
    AUTO_HIGH = "auto_high"  # Auto most things, only critical needs approval


class GovernanceEngine:
    """
    Enforces governance policies on all system actions.

    This is WIRING POINT #6:
    Decisions → Governance Check → Execute or Queue for Approval
    """

    def __init__(self, config: dict = None, store: StateStore = None):
        self.store = store or get_store()
        self.config = config or self._load_config()

        self._action_counts: dict[str, int] = defaultdict(int)
        self._last_reset = datetime.now()
        self._emergency_brake_active = False

    def _load_config(self) -> dict:
        """Load governance configuration."""
        config_file = paths.config_dir() / "governance.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {"domains": {}, "approval_required": [], "rate_limits": {}}

    def get_mode(self, domain: str) -> DomainMode:
        """Get current mode for a domain."""
        mode_str = self.config.get("domains", {}).get(domain, {}).get("mode", "observe")
        try:
            return DomainMode(mode_str)
        except ValueError:
            return DomainMode.OBSERVE

    def get_domain_config(self, domain: str) -> dict:
        """Get full config for a domain including mode and threshold."""
        return self.config.get("domains", {}).get(
            domain, {"mode": "observe", "auto_threshold": 0.8}
        )

    def set_mode(self, domain: str, mode: DomainMode):
        """Set mode for a domain."""
        if "domains" not in self.config:
            self.config["domains"] = {}
        if domain not in self.config["domains"]:
            self.config["domains"][domain] = {}

        self.config["domains"][domain]["mode"] = mode.value

        # Persist to config file
        self._save_config()

    def _save_config(self):
        """Save config back to file."""
        config_file = paths.config_dir() / "governance.yaml"
        with open(config_file, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def can_execute(self, domain: str, action: str, context: dict = None) -> tuple[bool, str]:
        """
        Check if action can be executed automatically.
        Returns (can_execute, reason).
        """
        context = context or {}

        # Emergency brake check
        if self._emergency_brake_active:
            return False, "Emergency brake active"

        # Rate limit check
        if not self._check_rate_limit(domain, action):
            return False, "Rate limit exceeded"

        # Get domain mode
        mode = self.get_mode(domain)

        # OBSERVE mode - never execute
        if mode == DomainMode.OBSERVE:
            return False, f"Domain '{domain}' in OBSERVE mode"

        # Check specific approval rules
        for rule in self.config.get("approval_required", []):
            if rule.get("domain") == domain and rule.get("action") == action:
                condition = rule.get("condition", "always")

                if condition == "always":
                    return False, f"Action '{action}' always requires approval"

                if self._evaluate_condition(condition, context):
                    return False, f"Condition met: {condition}"

        # PROPOSE mode - always require approval
        if mode == DomainMode.PROPOSE:
            return False, f"Domain '{domain}' in PROPOSE mode"

        # AUTO_LOW - check confidence threshold
        if mode == DomainMode.AUTO_LOW:
            threshold = self.config.get("domains", {}).get(domain, {}).get("auto_threshold", 0.8)
            confidence = context.get("confidence", 0)

            if confidence < threshold:
                return False, f"Confidence {confidence:.2f} below threshold {threshold}"

        # AUTO_HIGH - most permissive, but still check for critical actions
        return True, "Approved for automatic execution"

    def requires_approval(self, domain: str, action: str) -> bool:
        """Quick check if action type requires approval."""
        mode = self.get_mode(domain)

        if mode in (DomainMode.OBSERVE, DomainMode.PROPOSE):
            return True

        for rule in self.config.get("approval_required", []):
            if rule.get("domain") == domain and rule.get("action") == action:
                return True

        return False

    def _check_rate_limit(self, domain: str, action: str) -> bool:
        """Check if action is within rate limits."""
        # Reset counts every hour
        if (datetime.now() - self._last_reset).total_seconds() > 3600:
            self._action_counts.clear()
            self._last_reset = datetime.now()

        rate_limits = self.config.get("rate_limits", {})

        # Check specific limit
        key = f"{domain}_{action}"
        limit_key = domain if domain in rate_limits else "total_actions"
        limit = rate_limits.get(limit_key, 100)

        if self._action_counts[key] >= limit:
            return False

        self._action_counts[key] += 1
        return True

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Evaluate a condition string against context."""
        if condition == "always":
            return True

        # Simple condition parsing
        # Format: "field operator value"
        parts = condition.split()
        if len(parts) != 3:
            return False

        field, op, value = parts
        context_value = context.get(field)

        if context_value is None:
            return False

        with contextlib.suppress(ValueError):
            value = float(value) if "." in value else int(value)

        if op == ">":
            return context_value > value
        if op == "<":
            return context_value < value
        if op == ">=":
            return context_value >= value
        if op == "<=":
            return context_value <= value
        if op == "==":
            return context_value == value
        if op == "!=":
            return context_value != value

        return False

    def emergency_brake(self, reason: str):
        """
        Activate emergency brake - stops all automatic actions.
        """
        self._emergency_brake_active = True

        # Set all domains to OBSERVE
        for domain in self.config.get("domains", {}):
            self.set_mode(domain, DomainMode.OBSERVE)

        # Log the event
        self.store.insert(
            "cycle_logs",
            {
                "id": f"emergency_{datetime.now().isoformat()}",
                "cycle_number": 0,
                "phase": "emergency_brake",
                "data": json.dumps({"reason": reason}),
                "created_at": datetime.now().isoformat(),
            },
        )

    def release_brake(self):
        """Release emergency brake."""
        self._emergency_brake_active = False

    def get_status(self) -> dict:
        """Get current governance status."""
        return {
            "emergency_brake": self._emergency_brake_active,
            "domains": {
                domain: {
                    "mode": cfg.get("mode", "observe"),
                    "auto_threshold": cfg.get("auto_threshold", 0.8),
                }
                for domain, cfg in self.config.get("domains", {}).items()
            },
            "rate_limits": self.config.get("rate_limits", {}),
            "current_counts": dict(self._action_counts),
        }

    def get_summary(self) -> dict:
        """
        Get a stable summary of governance state for API responses.

        Returns a JSON-serializable dict that is safe even if internals
        are empty or uninitialized.
        """
        try:
            domain_counts = {}
            domains_config = self.config.get("domains", {})
            for mode in DomainMode:
                count = sum(1 for d in domains_config.values() if d.get("mode") == mode.value)
                domain_counts[mode.value] = count

            return {
                "ok": not self._emergency_brake_active,
                "counts": {
                    "domains": len(domains_config),
                    "by_mode": domain_counts,
                    "actions_this_hour": sum(self._action_counts.values()),
                },
                "updated_at": self._last_reset.isoformat() if self._last_reset else None,
                "notes": ["Emergency brake active"] if self._emergency_brake_active else [],
            }
        except Exception:
            # Fallback if anything goes wrong - never raise
            return {
                "ok": False,
                "counts": {},
                "updated_at": None,
                "notes": ["Governance status unavailable"],
            }


# Singleton
_governance: GovernanceEngine | None = None


def get_governance(config: dict = None, store: StateStore = None) -> GovernanceEngine:
    """Get the singleton governance engine."""
    global _governance
    if _governance is None:
        _governance = GovernanceEngine(config, store)
    return _governance


# Convenience functions
def get_domain_mode(domain: str) -> DomainMode:
    """Get a domain's current governance mode."""
    return get_governance().get_mode(domain)


def can_write(domain: str) -> bool:
    """Check if writes are allowed for a domain."""
    gov = get_governance()
    if gov._emergency_brake_active:
        return False
    mode = gov.get_mode(domain)
    return mode in (DomainMode.AUTO_LOW, DomainMode.AUTO_HIGH)


def set_domain_mode(domain: str, mode: DomainMode):
    """Set a domain's governance mode."""
    get_governance().set_mode(domain, mode)


def emergency_brake(reason: str):
    """Activate emergency brake."""
    get_governance().emergency_brake(reason)


def release_brake():
    """Release emergency brake."""
    get_governance().release_brake()
