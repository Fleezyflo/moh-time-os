"""
Feature Flags Tests.
"""

import os

import pytest

from lib.features import (
    REGISTRY,
    FlagDefinition,
    FlagRegistry,
    FlagType,
    get_flag,
    is_enabled,
    set_flag,
)


class TestFlagRegistry:
    """Test the flag registry."""

    def test_get_default_value(self):
        """Flags return their default value."""
        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="test_flag",
                description="Test flag",
                default=True,
            )
        )

        assert registry.get("test_flag") is True

    def test_unknown_flag_raises(self):
        """Accessing unknown flag raises ValueError."""
        registry = FlagRegistry()

        with pytest.raises(ValueError, match="Unknown flag"):
            registry.get("nonexistent")

    def test_runtime_override(self):
        """Runtime overrides take precedence."""
        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="test_flag",
                description="Test",
                default=False,
            )
        )

        registry.set_override("test_flag", True)
        assert registry.get("test_flag") is True

        registry.clear_override("test_flag")
        assert registry.get("test_flag") is False

    def test_env_override(self, monkeypatch):
        """Environment variables override defaults."""
        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="env_test",
                description="Test",
                default=False,
            )
        )

        monkeypatch.setenv("MOH_FLAG_ENV_TEST", "true")
        assert registry.get("env_test") is True

    def test_kill_switch_wins(self, monkeypatch):
        """Kill switch flags always use env value."""
        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="maintenance",
                description="Maintenance mode",
                default=False,
                kill_switch=True,
            )
        )

        # Set runtime override
        registry.set_override("maintenance", True)
        assert registry.get("maintenance") is True

        # Env override wins for kill switch
        monkeypatch.setenv("MOH_FLAG_MAINTENANCE", "false")
        assert registry.get("maintenance") is False

    def test_number_flag(self, monkeypatch):
        """Number flags are parsed correctly."""
        registry = FlagRegistry()
        registry.register(
            FlagDefinition(
                name="limit",
                description="Limit",
                default=10,
                flag_type=FlagType.NUMBER,
            )
        )

        assert registry.get("limit") == 10

        monkeypatch.setenv("MOH_FLAG_LIMIT", "50")
        assert registry.get("limit") == 50

    def test_get_all_flags(self):
        """get_all returns all flag values."""
        registry = FlagRegistry()
        registry.register(FlagDefinition(name="a", description="A", default=True))
        registry.register(FlagDefinition(name="b", description="B", default=False))

        all_flags = registry.get_all()
        assert all_flags == {"a": True, "b": False}


class TestGlobalRegistry:
    """Test the global registry and convenience functions."""

    def test_is_enabled(self):
        """is_enabled returns boolean value."""
        # offline_mode is True by default
        assert is_enabled("offline_mode") is True

    def test_get_flag(self):
        """get_flag returns flag value."""
        result = get_flag("max_proposals_per_page")
        assert result == 20

    def test_set_flag(self):
        """set_flag sets override."""
        original = get_flag("new_inbox_ui")
        set_flag("new_inbox_ui", True)
        assert get_flag("new_inbox_ui") is True

        # Cleanup
        REGISTRY.clear_override("new_inbox_ui")
        assert get_flag("new_inbox_ui") == original


class TestFlagDefinitions:
    """Test that required flags are defined."""

    def test_maintenance_mode_is_kill_switch(self):
        """maintenance_mode is a kill switch."""
        definitions = REGISTRY.get_definitions()
        maintenance = next(d for d in definitions if d["name"] == "maintenance_mode")
        assert maintenance["kill_switch"] is True

    def test_all_flags_have_descriptions(self):
        """All flags have descriptions."""
        definitions = REGISTRY.get_definitions()
        for d in definitions:
            assert d["description"], f"{d['name']} has no description"
