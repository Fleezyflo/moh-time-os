#!/usr/bin/env python3
"""
Spec→Contract Traceability Report Generator

Compares PAGE0_AGENCY_CONTROL_ROOM_SPEC.md locked JSON structure against
lib/contracts/schema.py to identify matches, mismatches, missing, and extra fields.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.contracts.schema import (
    SCHEMA_VERSION,
    AgencySnapshotContract,
)

# ============================================================================
# SPEC DEFINITION (from PAGE0_AGENCY_CONTROL_ROOM_SPEC.md lines 513-559)
# ============================================================================

SPEC_SCHEMA = {
    "meta": {
        "required": True,
        "fields": {
            "generated_at": {"type": "ISO8601", "required": True},
            "mode": {"type": "Ops Head|Co-Founder|Artist", "required": True},
            "horizon": {"type": "NOW|TODAY|THIS_WEEK", "required": True},
            "scope": {
                "type": "object",
                "required": True,
                "fields": {
                    "lanes": {"type": "array"},
                    "owners": {"type": "array"},
                    "clients": {"type": "array"},
                    "include_internal": {"type": "boolean"},
                },
            },
        },
    },
    "trust": {
        "required": True,
        "fields": {
            "data_integrity": {"type": "boolean", "required": True},
            "project_brand_required": {"type": "boolean", "required": True},
            "project_brand_consistency": {"type": "boolean", "required": True},
            "client_coverage_pct": {"type": "number", "required": True},
            "finance_ar_coverage_pct": {"type": "number", "required": True},
            "commitment_ready_pct": {"type": "number", "required": True},
            "collector_staleness": {"type": "object", "required": True},
            "last_refresh_at": {"type": "ISO8601", "required": True},
        },
    },
    "narrative": {
        "required": True,  # Per spec: "Minimum required structure (locked fields)"
        "fields": {
            "first_to_break": {
                "type": "object|null",
                "required": True,
                "fields": {
                    "entity_type": {"type": "project|client|lane|person|ar|thread"},
                    "entity_id": {"type": "string"},
                    "time_to_consequence_hours": {"type": "number"},
                    "top_driver": {"type": "string"},
                    "primary_action": {"type": "object"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "HIGH|MED|LOW"},
                    "why_low": {"type": "array"},
                },
            },
            "deltas": {"type": "array", "required": True, "max": 5},
        },
    },
    "tiles": {
        "required": True,  # Per spec: part of locked structure
        "fields": {
            "delivery": {
                "type": "object",
                "required": True,
                "fields": {
                    "badge": {"type": "GREEN|YELLOW|RED|PARTIAL"},
                    "summary": {"type": "string"},
                    "cta": {"type": "string"},
                },
            },
            "cash": {"type": "object", "required": True},
            "clients": {"type": "object", "required": True},
            "churn_x_money": {"type": "object", "required": True},
            "delivery_x_capacity": {"type": "object", "required": True},
        },
    },
    "heatstrip_projects": {
        "required": True,
        "type": "array",
        "max": 25,
        "item_fields": {
            "project_id": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "status": {"type": "GREEN|YELLOW|RED", "required": True},
            "time_to_slip_hours": {"type": "number", "required": True},
            "confidence": {"type": "HIGH|MED|LOW", "required": True},
        },
    },
    "constraints": {
        "required": True,  # Per spec: part of locked structure
        "type": "array",
        "max": 12,
        "item_fields": {
            "type": {"type": "person|lane", "required": True},
            "id": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "capacity_gap_hours": {"type": "number", "required": True},
            "time_to_consequence_hours": {"type": "number", "required": True},
            "confidence": {"type": "HIGH|MED|LOW", "required": True},
        },
    },
    "exceptions": {
        "required": True,  # Per spec: part of locked structure
        "type": "array",
        "max": 7,
        "item_fields": {
            "type": {
                "type": "delivery|money|churn|capacity|commitment|blocked|unknown",
                "required": True,
            },
            "id": {"type": "string", "required": True},
            "title": {"type": "string", "required": True},
            "score": {"type": "number", "required": True},
            "confidence": {"type": "HIGH|MED|LOW", "required": True},
            "primary_action": {"type": "object", "required": True},
            "drawer_ref": {"type": "string", "required": True},
        },
    },
    "drawers": {
        "required": True,  # Per spec: part of locked structure
        "type": "object",
    },
    # Extensions (not in Page 0 spec, but required for full dashboard Pages 1-5)
    # These are REQUIRED by our extended contract, not optional
    "delivery_command": {
        "required": True,
        "note": "Page 1 extension - required for full dashboard",
    },
    "client_360": {
        "required": True,
        "note": "Page 2 extension - required for full dashboard",
    },
    "cash_ar": {
        "required": True,
        "note": "Page 3 extension - required for full dashboard",
    },
    "comms_commitments": {
        "required": True,
        "note": "Page 4 extension - required for full dashboard",
    },
    "capacity_command": {
        "required": True,
        "note": "Page 5 extension - required for full dashboard",
    },
}

# ============================================================================
# CONTRACT EXTRACTION
# ============================================================================


def get_contract_fields():
    """Extract fields from Pydantic contract."""
    fields = {}
    for name, field in AgencySnapshotContract.model_fields.items():
        fields[name] = {
            "type": str(field.annotation),
            "required": field.is_required(),
        }
    return fields


def compare_spec_to_contract():
    """Generate traceability report."""
    contract_fields = get_contract_fields()

    report = []
    report.append("=" * 80)
    report.append("SPEC → CONTRACT TRACEABILITY REPORT")
    report.append("=" * 80)
    report.append("Spec Source: docs/PAGE0_AGENCY_CONTROL_ROOM_SPEC.md (v1 locked)")
    report.append("Contract: lib/contracts/schema.py")
    report.append(f"Contract Version: {SCHEMA_VERSION}")
    report.append("=" * 80)
    report.append("")

    mismatches = []
    matches = []
    missing_in_contract = []
    extra_in_contract = []

    # Check spec fields against contract
    for spec_path, spec_def in SPEC_SCHEMA.items():
        spec_required = spec_def.get("required", False)

        if spec_path in contract_fields:
            contract_required = contract_fields[spec_path]["required"]
            contract_type = contract_fields[spec_path]["type"]

            if spec_required != contract_required:
                mismatches.append(
                    {
                        "spec_path": spec_path,
                        "spec_required": spec_required,
                        "contract_required": contract_required,
                        "status": "MISMATCH (required)",
                        "notes": f"Spec says required={spec_required}, contract has required={contract_required}",
                    }
                )
            else:
                matches.append(
                    {
                        "spec_path": spec_path,
                        "spec_required": spec_required,
                        "contract_required": contract_required,
                        "contract_type": contract_type,
                        "status": "MATCH",
                    }
                )
        else:
            if spec_required:
                missing_in_contract.append(
                    {
                        "spec_path": spec_path,
                        "spec_required": spec_required,
                        "status": "MISSING",
                        "notes": "Required by spec but not in contract",
                    }
                )

    # Check for extra fields in contract not in spec
    for contract_path in contract_fields:
        if contract_path not in SPEC_SCHEMA:
            extra_in_contract.append(
                {
                    "contract_path": contract_path,
                    "contract_type": contract_fields[contract_path]["type"],
                    "contract_required": contract_fields[contract_path]["required"],
                    "status": "EXTRA",
                    "notes": "In contract but not in Page 0 spec (may be extension)",
                }
            )

    # Output report
    report.append("SECTION 1: MATCHES")
    report.append("-" * 40)
    for m in matches:
        report.append(
            f"✓ {m['spec_path']}: required={m['spec_required']} | type={m['contract_type']}"
        )

    report.append("")
    report.append("SECTION 2: MISMATCHES (MUST FIX)")
    report.append("-" * 40)
    if mismatches:
        for m in mismatches:
            report.append(f"✗ {m['spec_path']}: {m['notes']}")
    else:
        report.append("(none)")

    report.append("")
    report.append("SECTION 3: MISSING IN CONTRACT")
    report.append("-" * 40)
    if missing_in_contract:
        for m in missing_in_contract:
            report.append(f"! {m['spec_path']}: {m['notes']}")
    else:
        report.append("(none)")

    report.append("")
    report.append("SECTION 4: EXTRA IN CONTRACT (extensions)")
    report.append("-" * 40)
    for m in extra_in_contract:
        report.append(f"+ {m['contract_path']}: {m['notes']}")

    report.append("")
    report.append("=" * 80)
    report.append("SUMMARY")
    report.append("=" * 80)
    report.append(f"Matches: {len(matches)}")
    report.append(f"Mismatches: {len(mismatches)}")
    report.append(f"Missing: {len(missing_in_contract)}")
    report.append(f"Extra (extensions): {len(extra_in_contract)}")

    if mismatches or missing_in_contract or extra_in_contract:
        report.append("")
        report.append(
            "⚠️  SPEC COMPLIANCE: FAILED - Fix mismatches/missing/extras before proceeding"
        )
    else:
        report.append("")
        report.append("✓ SPEC COMPLIANCE: PASSED - All required fields present and correctly typed")

    return (
        "\n".join(report),
        len(mismatches),
        len(missing_in_contract),
        len(extra_in_contract),
    )


if __name__ == "__main__":
    report, mismatch_count, missing_count, extra_count = compare_spec_to_contract()
    print(report)

    # Exit non-zero if ANY violation (mismatches, missing, OR extras)
    if mismatch_count > 0 or missing_count > 0 or extra_count > 0:
        sys.exit(1)
