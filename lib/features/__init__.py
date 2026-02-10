"""
Feature Flags System.

Production-grade feature flag management:
- Typed flag registry with defaults
- Environment override support
- Kill switch capability
- Runtime toggle for dev
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================================
# Flag Definitions
# ============================================================================


class FlagType(Enum):
    """Type of feature flag."""

    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"


@dataclass
class FlagDefinition:
    """Definition of a feature flag."""

    name: str
    description: str
    default: Any
    flag_type: FlagType = FlagType.BOOLEAN
    kill_switch: bool = False  # If True, env override always wins


# ============================================================================
# Flag Registry
# ============================================================================


@dataclass
class FlagRegistry:
    """
    Central registry of all feature flags.

    Flags are defined here with defaults and can be overridden via:
    1. Environment variables (MOH_FLAG_<NAME>)
    2. Runtime overrides (for dev/testing)
    3. Kill switch (env override always wins)
    """

    _definitions: dict[str, FlagDefinition] = field(default_factory=dict)
    _overrides: dict[str, Any] = field(default_factory=dict)

    def register(self, definition: FlagDefinition) -> None:
        """Register a flag definition."""
        self._definitions[definition.name] = definition

    def get(self, name: str) -> Any:
        """Get a flag value with full resolution."""
        if name not in self._definitions:
            raise ValueError(f"Unknown flag: {name}")

        definition = self._definitions[name]

        # 1. Check kill switch (env always wins)
        if definition.kill_switch:
            env_value = self._get_env_value(name, definition)
            if env_value is not None:
                return env_value

        # 2. Check runtime override
        if name in self._overrides:
            return self._overrides[name]

        # 3. Check environment
        env_value = self._get_env_value(name, definition)
        if env_value is not None:
            return env_value

        # 4. Return default
        return definition.default

    def _get_env_value(self, name: str, definition: FlagDefinition) -> Any | None:
        """Get value from environment variable."""
        env_name = f"MOH_FLAG_{name.upper()}"
        value = os.environ.get(env_name)

        if value is None:
            return None

        # Parse based on type
        if definition.flag_type == FlagType.BOOLEAN:
            return value.lower() in ("true", "1", "yes", "on")
        elif definition.flag_type == FlagType.NUMBER:
            try:
                return float(value) if "." in value else int(value)
            except ValueError:
                return definition.default
        elif definition.flag_type == FlagType.JSON:
            import json

            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return definition.default
        else:
            return value

    def set_override(self, name: str, value: Any) -> None:
        """Set a runtime override (for dev/testing)."""
        if name not in self._definitions:
            raise ValueError(f"Unknown flag: {name}")
        self._overrides[name] = value

    def clear_override(self, name: str) -> None:
        """Clear a runtime override."""
        self._overrides.pop(name, None)

    def clear_all_overrides(self) -> None:
        """Clear all runtime overrides."""
        self._overrides.clear()

    def get_all(self) -> dict[str, Any]:
        """Get all flag values."""
        return {name: self.get(name) for name in self._definitions}

    def get_definitions(self) -> list[dict]:
        """Get all flag definitions for API response."""
        return [
            {
                "name": d.name,
                "description": d.description,
                "type": d.flag_type.value,
                "default": d.default,
                "current": self.get(d.name),
                "kill_switch": d.kill_switch,
            }
            for d in self._definitions.values()
        ]


# ============================================================================
# Global Registry
# ============================================================================

REGISTRY = FlagRegistry()

# Register default flags
REGISTRY.register(
    FlagDefinition(
        name="new_inbox_ui",
        description="Enable new inbox UI design",
        default=False,
    )
)

REGISTRY.register(
    FlagDefinition(
        name="ai_suggestions",
        description="Enable AI-powered suggestions",
        default=False,
    )
)

REGISTRY.register(
    FlagDefinition(
        name="offline_mode",
        description="Enable offline mode support",
        default=True,
    )
)

REGISTRY.register(
    FlagDefinition(
        name="maintenance_mode",
        description="Enable maintenance mode (kill switch)",
        default=False,
        kill_switch=True,
    )
)

REGISTRY.register(
    FlagDefinition(
        name="max_proposals_per_page",
        description="Maximum proposals per page",
        default=20,
        flag_type=FlagType.NUMBER,
    )
)


# ============================================================================
# Convenience Functions
# ============================================================================


def is_enabled(name: str) -> bool:
    """Check if a boolean flag is enabled."""
    return bool(REGISTRY.get(name))


def get_flag(name: str) -> Any:
    """Get a flag value."""
    return REGISTRY.get(name)


def set_flag(name: str, value: Any) -> None:
    """Set a flag override (for dev/testing)."""
    REGISTRY.set_override(name, value)
