"""
Safe JSON parsing with trust tracking.

Instead of silently defaulting to {} or [], this module:
1. Catches only JSONDecodeError (not bare except)
2. Logs errors with item id and snippet length
3. Sets trust failure indicators
4. Preserves raw data for debugging
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of a safe JSON parse operation."""

    value: Any  # Parsed value or default
    success: bool = True
    error: str | None = None
    raw_value: str | None = None  # Preserved for debugging


@dataclass
class TrustMeta:
    """Trust metadata for an API response item."""

    data_integrity: bool = True
    errors: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    def add_parse_error(self, field_name: str, error: str, raw_length: int = 0):
        """Record a parse error."""
        self.data_integrity = False
        self.errors.append(f"{field_name}: {error}")
        if raw_length > 0:
            self.debug[f"{field_name}_raw_length"] = raw_length

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {"data_integrity": self.data_integrity}
        if self.errors:
            result["errors"] = self.errors
        if self.debug:
            result["debug"] = self.debug
        return result


def safe_json_loads(
    raw: str | None,
    default: Any,
    item_id: str | None = None,
    field_name: str = "unknown",
) -> ParseResult:
    """
    Safely parse JSON with proper error handling.

    Args:
        raw: Raw JSON string to parse
        default: Default value if parsing fails
        item_id: Optional item ID for logging
        field_name: Field name for error messages

    Returns:
        ParseResult with parsed value or default + error info
    """
    if raw is None or raw == "":
        return ParseResult(value=default, success=True)

    try:
        value = json.loads(raw)
        return ParseResult(value=value, success=True)
    except json.JSONDecodeError as e:
        # Log with item ID and snippet length (not full content for security)
        raw_length = len(raw) if raw else 0
        log_id = item_id or "unknown"
        logger.error(
            f"JSONDecodeError in {field_name} for item {log_id}: "
            f"{e.msg} at pos {e.pos}, raw_length={raw_length}"
        )
        return ParseResult(
            value=default,
            success=False,
            error=f"JSONDecodeError: {e.msg} at position {e.pos}",
            raw_value=raw[:100] + "..." if raw and len(raw) > 100 else raw,
        )
    except TypeError as e:
        # Handle cases where raw is not a string
        logger.error(f"TypeError in {field_name} for item {item_id or 'unknown'}: {e}")
        return ParseResult(
            value=default,
            success=False,
            error=f"TypeError: {str(e)}",
            raw_value=str(raw)[:100] if raw else None,
        )


def parse_json_field(
    item: dict,
    field_name: str,
    default: Any,
    trust: TrustMeta | None = None,
    item_id_field: str = "id",
) -> Any:
    """
    Parse a JSON field from a dict item with trust tracking.

    Args:
        item: Dictionary containing the field
        field_name: Name of the field to parse
        default: Default value if parsing fails
        trust: Optional TrustMeta to update on failure
        item_id_field: Field name to use for item ID in logs

    Returns:
        Parsed value or default
    """
    raw = item.get(field_name)
    item_id = item.get(item_id_field)

    result = safe_json_loads(raw, default, item_id=item_id, field_name=field_name)

    if not result.success and trust is not None:
        trust.add_parse_error(
            field_name,
            result.error or "Parse failed",
            raw_length=len(raw) if raw else 0,
        )
        # Store raw value for debugging
        if result.raw_value:
            trust.debug[f"{field_name}_raw"] = result.raw_value

    return result.value
