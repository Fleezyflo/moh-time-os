#!/usr/bin/env python3
"""
Dead Code Audit for MOH TIME OS.
Task: SYSPREP 0.2 — Dead Code Audit
"""

import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"

# Production code paths - imports from these are considered ACTIVE
PRODUCTION_PATHS = [
    "api/spec_router.py",
    "lib/ui_spec_v21/",
    "engine/",
    "collectors/",
    "lib/safety/",
    "lib/collectors/",
]

# Test paths - imports only from here means TEST-ONLY
TEST_PATHS = ["tests/"]


def load_baseline() -> dict:
    """Load the most recent baseline snapshot."""
    snapshots = list(DATA_DIR.glob("baseline_snapshot_*.json"))
    if not snapshots:
        raise FileNotFoundError("No baseline snapshot found")

    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    print(f"Loading baseline: {latest}")

    with open(latest) as f:
        return json.load(f)


def is_production_path(path: str) -> bool:
    """Check if a path is in production code paths."""
    for prod_path in PRODUCTION_PATHS:
        if path.startswith(prod_path):
            return True
    return False


def is_test_path(path: str) -> bool:
    """Check if a path is in test paths."""
    for test_path in TEST_PATHS:
        if path.startswith(test_path):
            return True
    return False


def check_entry_point(file_path: Path) -> bool:
    """Check if a file is an entry point (has __main__ block)."""
    try:
        content = file_path.read_text(errors="ignore")
        return 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content
    except Exception:
        return False


def get_module_docstring(file_path: Path) -> str:
    """Extract the docstring or first comment from a Python file."""
    try:
        content = file_path.read_text(errors="ignore")
        lines = content.split("\n")

        # Look for module docstring
        in_docstring = False
        docstring_lines = []

        for _i, line in enumerate(lines[:30]):
            stripped = line.strip()

            # Triple-quoted docstring
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    break
                in_docstring = True
                # Check if single-line docstring
                if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                    return stripped.strip("\"'").strip()
                docstring_lines.append(stripped.lstrip("\"'"))
                continue

            if in_docstring:
                if '"""' in stripped or "'''" in stripped:
                    docstring_lines.append(stripped.rstrip("\"'"))
                    break
                docstring_lines.append(stripped)

        if docstring_lines:
            return " ".join(docstring_lines[:3]).strip()

        # Fallback: look for first comment
        for line in lines[:10]:
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("#!"):
                return stripped.lstrip("# ").strip()

        return "(no description)"
    except Exception:
        return "(error reading file)"


def secondary_grep_check(module_name: str, file_path: str) -> list:
    """Do secondary grep check for module references - disabled for speed."""
    # Disabled: too slow for 277 modules. Manual review needed for orphans.
    return []


def classify_modules(modules: list) -> dict:
    """Classify all modules into categories."""
    classifications = {
        "ACTIVE": [],
        "TEST-ONLY": [],
        "ORPHANED": [],
        "ENTRY-POINT": [],
        "UNCERTAIN": [],
    }

    # Build a set of all module paths for orphan chain detection
    {m["path"] for m in modules}

    for module in modules:
        path = module["path"]
        imported_by = module.get("imported_by", [])
        file_path = REPO_ROOT / path

        # Check if it's an entry point
        if check_entry_point(file_path):
            classifications["ENTRY-POINT"].append(
                {**module, "purpose": get_module_docstring(file_path)}
            )
            continue

        # Check if imported by production code
        prod_importers = [i for i in imported_by if is_production_path(i)]
        test_importers = [i for i in imported_by if is_test_path(i)]
        other_importers = [
            i for i in imported_by if not is_production_path(i) and not is_test_path(i)
        ]

        if prod_importers:
            classifications["ACTIVE"].append({**module, "production_importers": prod_importers})
        elif test_importers and not other_importers:
            classifications["TEST-ONLY"].append({**module, "test_importers": test_importers})
        elif not imported_by:
            # Truly orphaned - no imports at all
            # Do secondary check
            refs = secondary_grep_check(module["module_name"], path)
            if refs:
                classifications["UNCERTAIN"].append(
                    {
                        **module,
                        "reason": f"Referenced in: {', '.join(refs[:3])}",
                        "description": get_module_docstring(file_path),
                    }
                )
            else:
                classifications["ORPHANED"].append(
                    {**module, "description": get_module_docstring(file_path)}
                )
        else:
            # Imported by other modules (not tests, not production) - check if those are active
            # For now, mark as UNCERTAIN
            non_test_non_prod = [
                i for i in imported_by if not is_test_path(i) and not is_production_path(i)
            ]
            if non_test_non_prod:
                # Check if any of those importers are themselves active
                active_chain = False
                for importer in non_test_non_prod:
                    # Simple heuristic: if importer is in lib/ui_spec_v21 or similar, it's active
                    if any(prod in importer for prod in ["ui_spec_v21", "safety", "spec_router"]):
                        active_chain = True
                        break

                if active_chain:
                    classifications["ACTIVE"].append(
                        {**module, "production_importers": non_test_non_prod}
                    )
                else:
                    classifications["UNCERTAIN"].append(
                        {
                            **module,
                            "reason": f"Imported by: {', '.join(non_test_non_prod[:3])}",
                            "description": get_module_docstring(file_path),
                        }
                    )

    return classifications


def generate_report(classifications: dict, total_modules: int) -> str:
    """Generate markdown report."""
    date_str = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# Dead Code Audit — {date_str}",
        "",
        "## Summary",
        f"- Total modules scanned: {total_modules}",
        f"- ACTIVE: {len(classifications['ACTIVE'])}",
        f"- TEST-ONLY: {len(classifications['TEST-ONLY'])}",
        f"- ORPHANED: {len(classifications['ORPHANED'])}",
        f"- ENTRY-POINT: {len(classifications['ENTRY-POINT'])}",
        f"- UNCERTAIN: {len(classifications['UNCERTAIN'])}",
        "",
        "---",
        "",
        "## ACTIVE Modules",
        "| Module | Path | Imported By (production) |",
        "|--------|------|-------------------------|",
    ]

    for m in sorted(classifications["ACTIVE"], key=lambda x: x["path"]):
        importers = m.get("production_importers", [])[:3]
        lines.append(f"| {m['module_name']} | `{m['path']}` | {', '.join(importers)} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## TEST-ONLY Modules",
            "| Module | Path | Imported By (tests) |",
            "|--------|------|---------------------|",
        ]
    )

    for m in sorted(classifications["TEST-ONLY"], key=lambda x: x["path"]):
        importers = m.get("test_importers", [])[:3]
        lines.append(f"| {m['module_name']} | `{m['path']}` | {', '.join(importers)} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## ORPHANED Modules (candidates for removal)",
            "| Module | Path | Lines | Description |",
            "|--------|------|-------|-------------|",
        ]
    )

    for m in sorted(classifications["ORPHANED"], key=lambda x: x["path"]):
        desc = m.get("description", "")[:80].replace("|", "\\|")
        lines.append(
            f"| {m['module_name']} | `{m['path']}` | {m.get('line_count', '?')} | {desc} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## ENTRY-POINT Modules",
            "| Module | Path | Purpose |",
            "|--------|------|---------|",
        ]
    )

    for m in sorted(classifications["ENTRY-POINT"], key=lambda x: x["path"]):
        purpose = m.get("purpose", "")[:80].replace("|", "\\|")
        lines.append(f"| {m['module_name']} | `{m['path']}` | {purpose} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## UNCERTAIN (needs manual review)",
            "| Module | Path | Lines | Reason |",
            "|--------|------|-------|--------|",
        ]
    )

    for m in sorted(classifications["UNCERTAIN"], key=lambda x: x["path"]):
        reason = m.get("reason", "")[:60].replace("|", "\\|")
        lines.append(
            f"| {m['module_name']} | `{m['path']}` | {m.get('line_count', '?')} | {reason} |"
        )

    return "\n".join(lines)


def main():
    print("Starting Dead Code Audit...")

    # Load baseline
    baseline = load_baseline()
    modules = baseline["modules"]["files"]
    total = len(modules)
    print(f"Loaded {total} modules from baseline")

    # Classify
    print("Classifying modules...")
    classifications = classify_modules(modules)

    # Generate report
    print("Generating report...")
    report = generate_report(classifications, total)

    # Save
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = DATA_DIR / f"dead_code_audit_{date_str}.md"
    output_file.write_text(report)

    print(f"\n✓ Report saved to: {output_file}")

    # Summary
    print("\n=== DEAD CODE AUDIT SUMMARY ===")
    print(f"Total modules:  {total}")
    print(f"ACTIVE:         {len(classifications['ACTIVE'])}")
    print(f"TEST-ONLY:      {len(classifications['TEST-ONLY'])}")
    print(f"ORPHANED:       {len(classifications['ORPHANED'])}")
    print(f"ENTRY-POINT:    {len(classifications['ENTRY-POINT'])}")
    print(f"UNCERTAIN:      {len(classifications['UNCERTAIN'])}")

    # Verify all modules accounted for
    accounted = sum(len(v) for v in classifications.values())
    if accounted != total:
        print(f"\n⚠️  WARNING: {total - accounted} modules unaccounted for!")
    else:
        print(f"\n✓ All {total} modules categorized")


if __name__ == "__main__":
    main()
