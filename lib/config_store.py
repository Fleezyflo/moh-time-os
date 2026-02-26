#!/usr/bin/env python3
"""
MOH Time OS — Configuration Store

Persistent configuration with all configurable fields from specs:
- Sensitivity flags & risk taxonomy
- Lanes with capacity budgets
- Priority scoring weights
- Enrollment parameters
- Routing rules
- Reporting cadences
- Scheduling preferences
- Delegation parameters
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)

CONFIG_DIR = paths.data_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_HISTORY_FILE = CONFIG_DIR / "config_history.json"


def _default_config() -> dict:
    """
    Default configuration based on specs.
    All values are conservative/observe-mode safe.
    """
    return {
        "version": 1,
        "schema_version": "0.1",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        # ===== A) Sensitivity flags & risk taxonomy =====
        "sensitivity": {
            "categories": [
                "financial",
                "legal",
                "reputation",
                "privacy",
                "security",
                "execCritical",
                "clientVIP",
            ],
            "detection_signals": {
                "financial": {
                    "keywords": [
                        "invoice",
                        "payment",
                        "wire",
                        "budget",
                        "revenue",
                        "expense",
                        "billing",
                    ],
                    "domains": [],
                    "senders": [],
                },
                "legal": {
                    "keywords": [
                        "contract",
                        "agreement",
                        "nda",
                        "lawsuit",
                        "compliance",
                        "legal",
                    ],
                    "domains": [],
                    "senders": [],
                },
                "reputation": {
                    "keywords": ["press", "media", "public", "crisis", "complaint"],
                    "domains": [],
                    "senders": [],
                },
                "privacy": {
                    "keywords": ["confidential", "private", "personal", "gdpr", "pii"],
                    "domains": [],
                    "senders": [],
                },
                "security": {
                    "keywords": [
                        "breach",
                        "hack",
                        "vulnerability",
                        "password",
                        "access",
                    ],
                    "domains": [],
                    "senders": [],
                },
                "execCritical": {
                    "keywords": [
                        "urgent",
                        "asap",
                        "critical",
                        "immediately",
                        "emergency",
                    ],
                    "domains": [],
                    "senders": [],
                },
                "clientVIP": {
                    "keywords": [],
                    "domains": [],
                    "senders": [],
                },
            },
            "escalation_rules": {
                "immediate_push": [
                    "financial",
                    "legal",
                    "security",
                    "clientVIP",
                    "execCritical",
                ],
                "min_confidence": "medium",
                "require_time_sensitivity": True,
            },
        },
        # ===== B) Lanes =====
        "lanes": {
            "ops": {
                "id": "ops",
                "display_name": "Operations",
                "description": "Core business and system operations",
                "priority_multiplier": 1.0,
                "capacity_budget": {"daily_minutes": 120, "weekly_minutes": 480},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60, 90],
            },
            "client": {
                "id": "client",
                "display_name": "Client Work",
                "description": "Tasks related to external clients and projects",
                "priority_multiplier": 1.2,
                "capacity_budget": {"daily_minutes": 180, "weekly_minutes": 720},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60, 90, 120],
            },
            "growth": {
                "id": "growth",
                "display_name": "Growth & Sales",
                "description": "Business development and marketing",
                "priority_multiplier": 0.9,
                "capacity_budget": {"daily_minutes": 60, "weekly_minutes": 240},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60],
            },
            "admin": {
                "id": "admin",
                "display_name": "Administrative",
                "description": "General administrative tasks and paperwork",
                "priority_multiplier": 0.7,
                "capacity_budget": {"daily_minutes": 45, "weekly_minutes": 180},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [15, 30],
            },
            "personal": {
                "id": "personal",
                "display_name": "Personal",
                "description": "Personal tasks and errands",
                "priority_multiplier": 0.5,
                "capacity_budget": {"daily_minutes": 30, "weekly_minutes": 120},
                "scheduling_hours": {"start": 7, "end": 22, "timezone": "Asia/Dubai"},
                "block_templates": [15, 30, 60],
            },
            "people": {
                "id": "people",
                "display_name": "People",
                "description": "Team and department management",
                "priority_multiplier": 1.1,
                "capacity_budget": {"daily_minutes": 60, "weekly_minutes": 240},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60],
            },
            "governance": {
                "id": "governance",
                "display_name": "Governance",
                "description": "Reviews, audits, reports",
                "priority_multiplier": 0.8,
                "capacity_budget": {"daily_minutes": 30, "weekly_minutes": 120},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60],
            },
            "music": {
                "id": "music",
                "display_name": "Music",
                "description": "Moh Flow music work",
                "priority_multiplier": 0.6,
                "capacity_budget": {"daily_minutes": 60, "weekly_minutes": 240},
                "scheduling_hours": {"start": 18, "end": 24, "timezone": "Asia/Dubai"},
                "block_templates": [60, 120, 180],
            },
            "finance": {
                "id": "finance",
                "display_name": "Finance",
                "description": "Finance, money, billing, invoices",
                "priority_multiplier": 1.3,
                "capacity_budget": {"daily_minutes": 45, "weekly_minutes": 180},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [15, 30, 60],
            },
            "cream": {
                "id": "cream",
                "display_name": "CREAM",
                "description": "Moh's ice cream brand launch",
                "priority_multiplier": 0.8,
                "capacity_budget": {"daily_minutes": 30, "weekly_minutes": 120},
                "scheduling_hours": {"start": 9, "end": 18, "timezone": "Asia/Dubai"},
                "block_templates": [30, 60],
            },
        },
        # ===== C) Priority scoring =====
        "priority": {
            "weights": {
                "urgency": 0.25,
                "impact": 0.25,
                "deadline_proximity": 0.20,
                "sensitivity": 0.15,
                "stakeholder_tier": 0.10,
                "waiting_aging": 0.05,
            },
            "urgency_levels": {
                "critical": 5,
                "high": 4,
                "medium": 3,
                "low": 2,
                "none": 1,
            },
            "impact_levels": {
                "critical": 5,
                "high": 4,
                "medium": 3,
                "low": 2,
                "none": 1,
            },
            "deadline_thresholds": {
                "overdue": 5,
                "today": 4,
                "tomorrow": 3,
                "this_week": 2,
                "later": 1,
            },
            "thresholds": {
                "immediate_alert": 4.5,
                "propose_scheduling": 3.5,
                "propose_delegation": 3.0,
            },
        },
        # ===== D) Enrollment parameters =====
        "enrollment": {
            "evidence_requirements": {
                "time_window_days": 14,
                "min_distinct_threads": 3,
                "min_distinct_participants": 2,
                "min_artifacts": 1,
            },
            "rate_limits": {
                "max_proposals_per_day": 3,
                "max_proposals_per_week": 10,
            },
            "snooze_days_default": 7,
            "ignore_patterns": [],
        },
        # ===== E) Routing rules =====
        "routing": {
            "task_lists": {
                "inbox": "Inbox",
                "unknowns": "Unknowns",
                "waiting_for": "Waiting For",
            },
            "lane_to_list_mapping": {
                # Default: route to lane-specific list
                "default": "{lane_display_name}",
            },
            "status_prefixes": {
                "waitingFor": "[WF]",
                "review": "[REV]",
                "blocked": "[BLOCKED]",
            },
        },
        # ===== F) Reporting cadences =====
        "reporting": {
            "briefs": {
                "morning": {"time": "09:00", "timezone": "Asia/Dubai", "enabled": True},
                "midday": {"time": "13:00", "timezone": "Asia/Dubai", "enabled": True},
                "evening": {"time": "19:30", "timezone": "Asia/Dubai", "enabled": True},
            },
            "always_include": ["unknowns", "conflicts", "overdue"],
            "rate_limits": {
                "max_alerts_per_hour": 5,
                "batch_threshold_minutes": 15,
            },
        },
        # ===== G) Scheduling preferences =====
        "scheduling": {
            "planning_horizon_days": 7,
            "min_block_minutes": 15,
            "max_block_minutes": 180,
            "buffer_minutes": 10,
            "protection": {
                "deep_work_blocks": True,
                "meeting_buffer_minutes": 10,
                "max_context_switches_per_day": 6,
            },
            "fragmentation": {
                "min_gap_minutes": 15,
                "max_blocks_per_day": 8,
            },
        },
        # ===== H) Delegation parameters =====
        "delegation": {
            "enabled": False,
            "delegation_first_bias": True,
            "packet_completeness_required": True,
            "least_disclosure": True,
            "follow_up_cadence_days": 3,
            "escalation_threshold_days": 5,
            "turnaround_norms": {
                "default_days": 3,
                "urgent_days": 1,
            },
        },
        # ===== I) Staleness thresholds =====
        "staleness": {
            "waiting_for_days": 5,
            "review_days": 3,
            "blocked_days": 3,
            "in_progress_days": 2,
        },
        # ===== J) VIP configuration =====
        "vip": {
            "senders": [],
            "domains": [],
            "clients": [],
        },
    }


def load_config() -> dict:
    """Load configuration from disk."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            return _default_config()

    # Initialize with defaults
    config = _default_config()
    save_config(config, "Initial config creation")
    return config


def save_config(config: dict, reason: str = None) -> None:
    """Save configuration to disk with history."""
    config["updated_at"] = datetime.now(UTC).isoformat()

    # Log change
    _log_config_change(config, reason)

    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get(path: str, default: Any = None) -> Any:
    """
    Get a config value by dot-separated path.

    Example: get("lanes.ops.priority_multiplier")
    """
    config = load_config()
    parts = path.split(".")
    value = config

    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default

    return value


def set(path: str, value: Any, reason: str = None) -> dict:
    """
    Set a config value by dot-separated path.

    Example: set("lanes.ops.priority_multiplier", 1.5)
    """
    config = load_config()
    parts = path.split(".")

    # Navigate to parent
    current = config
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    # Set value
    current[parts[-1]] = value

    save_config(config, reason or f"Set {path}")
    return config


def get_lane(lane_id: str) -> dict | None:
    """Get lane configuration by ID."""
    return get(f"lanes.{lane_id}")


def get_all_lanes() -> dict:
    """Get all lane configurations."""
    return get("lanes", {})


def get_sensitivity_signals(category: str) -> dict:
    """Get detection signals for a sensitivity category."""
    return get(f"sensitivity.detection_signals.{category}", {})


def _log_config_change(config: dict, reason: str = None) -> None:
    """Log config changes for audit."""
    history = []
    if CONFIG_HISTORY_FILE.exists():
        try:
            history = json.loads(CONFIG_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not load config history: {e}")
            history = []

    history.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "reason": reason,
            "config_hash": hash(json.dumps(config, sort_keys=True)),
        }
    )

    # Keep last 500 entries
    history = history[-500:]

    CONFIG_HISTORY_FILE.write_text(json.dumps(history, indent=2))


def validate_config(config: dict) -> tuple[bool, list[str]]:
    """Validate configuration structure and values."""
    errors = []

    # Check required top-level keys
    required = [
        "sensitivity",
        "lanes",
        "priority",
        "enrollment",
        "routing",
        "reporting",
        "scheduling",
        "delegation",
    ]
    for key in required:
        if key not in config:
            errors.append(f"Missing required key: {key}")

    # Validate lanes have required fields
    for lane_id, lane in config.get("lanes", {}).items():
        if "capacity_budget" not in lane:
            errors.append(f"Lane {lane_id} missing capacity_budget")
        if "priority_multiplier" not in lane:
            errors.append(f"Lane {lane_id} missing priority_multiplier")

    # Validate priority weights sum to ~1.0
    weights = config.get("priority", {}).get("weights", {})
    if weights:
        total = sum(weights.values())
        if not (0.95 <= total <= 1.05):
            errors.append(f"Priority weights sum to {total}, expected ~1.0")

    return len(errors) == 0, errors


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: config_store.py <command> [args]")
        logger.info("Commands: show, get <path>, set <path> <value>, validate, lanes")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "show":
        config = load_config()
        logger.info(json.dumps(config, indent=2))
    elif cmd == "get" and len(sys.argv) >= 3:
        path = sys.argv[2]
        value = get(path)
        logger.info(json.dumps(value, indent=2) if isinstance(value, dict | list) else value)
    elif cmd == "set" and len(sys.argv) >= 4:
        path = sys.argv[2]
        raw_value = sys.argv[3]
        if raw_value.startswith(("{", "[")):
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON value: {e}")
                sys.exit(1)
        else:
            value = raw_value
        set(path, value)
        logger.info(f"Set {path} = {value}")
    elif cmd == "validate":
        config = load_config()
        valid, errors = validate_config(config)
        if valid:
            logger.info("Configuration is valid")
        else:
            logger.info("Configuration errors:")
            for e in errors:
                logger.info(f"  - {e}")
    elif cmd == "lanes":
        lanes = get_all_lanes()
        for lane_id, lane in lanes.items():
            logger.info(
                f"{lane_id}: {lane.get('display_name')} (priority: {lane.get('priority_multiplier')})"
            )
    else:
        logger.info(f"Unknown command: {cmd}")
        sys.exit(1)
