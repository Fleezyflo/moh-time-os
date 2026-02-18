#!/usr/bin/env python3
"""
Remove Orphaned Modules for MOH TIME OS.
Task: SYSPREP 1.1 — Remove Orphaned Modules

GUARDRAILS: Document before delete. Every change observable.
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"


def load_orphans() -> list:
    """Load orphaned modules from dead code audit."""
    # Find latest audit
    audits = list(DATA_DIR.glob("dead_code_audit_*.md"))
    if not audits:
        raise FileNotFoundError("No dead code audit found")

    latest = max(audits, key=lambda p: p.stat().st_mtime)
    print(f"Loading orphans from: {latest}")

    content = latest.read_text()

    # Parse ORPHANED section
    orphans = []
    in_orphan_section = False

    for line in content.split("\n"):
        if "## ORPHANED Modules" in line:
            in_orphan_section = True
            continue
        if in_orphan_section and line.startswith("## "):
            break
        if in_orphan_section and line.startswith("|") and "`" in line:
            # Parse table row: | module | `path` | lines | description |
            parts = line.split("|")
            if len(parts) >= 5:
                path_match = re.search(r'`([^`]+)`', parts[2])
                if path_match:
                    path = path_match.group(1)
                    try:
                        lines = int(parts[3].strip())
                    except:
                        lines = 0
                    desc = parts[4].strip() if len(parts) > 4 else ""
                    orphans.append({
                        "path": path,
                        "lines": lines,
                        "description": desc
                    })

    return orphans


def grep_check(filename: str) -> list:
    """Check if filename is referenced anywhere in codebase."""
    refs = []
    stem = Path(filename).stem

    # Skip __init__ files in grep (too generic)
    if stem == "__init__":
        return []

    try:
        result = subprocess.run(
            ["grep", "-rl", stem, str(REPO_ROOT),
             "--include=*.py", "--exclude-dir=.venv", "--exclude-dir=__pycache__"],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.strip().split("\n"):
            if line and line != filename:
                refs.append(line)
    except Exception:
        pass

    return refs[:5]


def run_tests() -> tuple:
    """Run test suite and return (passed, total, output)."""
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120
        )

        output = result.stdout + result.stderr

        # Parse output
        match = re.search(r'(\d+)\s+passed', output)
        passed = int(match.group(1)) if match else 0

        match = re.search(r'(\d+)\s+failed', output)
        failed = int(match.group(1)) if match else 0

        return (passed, failed, output)
    except Exception as e:
        return (0, 1, str(e))


def main():
    print("Starting Orphan Module Removal...")
    print("=" * 60)

    # Load orphans
    orphans = load_orphans()
    print(f"Found {len(orphans)} orphaned modules\n")

    # Verify tests pass before starting
    print("Verifying tests pass before starting...")
    passed, failed, _ = run_tests()
    if failed > 0:
        print(f"ERROR: Tests already failing ({failed} failed). Cannot proceed.")
        return
    print(f"✓ Tests passing: {passed}\n")

    # Track results
    removed = []
    skipped = []
    total_lines = 0

    # Process each orphan
    for i, orphan in enumerate(orphans):
        path = orphan["path"]
        full_path = REPO_ROOT / path

        print(f"[{i+1}/{len(orphans)}] {path}")

        # Check if file exists
        if not full_path.exists():
            print("  ⚠️  File not found, skipping")
            skipped.append({**orphan, "reason": "File not found"})
            continue

        # Final grep check
        refs = grep_check(path)
        if refs:
            print(f"  ⚠️  Still referenced by: {refs[:2]}")
            skipped.append({**orphan, "reason": f"Referenced by: {', '.join(refs[:2])}"})
            continue

        # Read file content for backup
        try:
            backup_content = full_path.read_text()
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
            skipped.append({**orphan, "reason": f"Read error: {e}"})
            continue

        # Delete file
        try:
            full_path.unlink()
            print("  Deleted. Running tests...")
        except Exception as e:
            print(f"  ⚠️  Could not delete: {e}")
            skipped.append({**orphan, "reason": f"Delete error: {e}"})
            continue

        # Run tests
        passed, failed, output = run_tests()

        if failed > 0:
            # Revert!
            print("  ❌ Tests failed! Reverting...")
            full_path.write_text(backup_content)
            skipped.append({**orphan, "reason": "Tests failed after removal"})
            continue

        # Success
        print(f"  ✅ Removed. Tests: {passed} passing")
        removed.append({**orphan, "tests_after": passed})
        total_lines += orphan.get("lines", 0)

    # Generate report
    date_str = datetime.now().strftime("%Y%m%d")
    report_lines = [
        f"# Module Removal Log — {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Summary",
        f"- Attempted: {len(orphans)}",
        f"- Removed: {len(removed)}",
        f"- Skipped: {len(skipped)}",
        f"- Lines of code removed: {total_lines:,}",
        f"- Test suite: {passed} passing after all removals",
        "",
        "---",
        "",
        "## Removed",
        "| Path | Lines | Purpose | Tests After |",
        "|------|-------|---------|-------------|",
    ]

    for r in removed:
        desc = r.get("description", "")[:40]
        report_lines.append(f"| `{r['path']}` | {r.get('lines', 0)} | {desc} | ✅ {r.get('tests_after', 0)} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## Skipped (could not safely remove)",
        "| Path | Lines | Reason |",
        "|------|-------|--------|",
    ])

    for s in skipped:
        reason = s.get("reason", "")[:50]
        report_lines.append(f"| `{s['path']}` | {s.get('lines', 0)} | {reason} |")

    report = "\n".join(report_lines)
    output_file = DATA_DIR / f"module_removal_log_{date_str}.md"
    output_file.write_text(report)

    print("\n" + "=" * 60)
    print(f"✓ Report saved to: {output_file}")
    print("\n=== REMOVAL SUMMARY ===")
    print(f"Attempted:    {len(orphans)}")
    print(f"Removed:      {len(removed)}")
    print(f"Skipped:      {len(skipped)}")
    print(f"Lines removed: {total_lines:,}")


if __name__ == "__main__":
    main()
