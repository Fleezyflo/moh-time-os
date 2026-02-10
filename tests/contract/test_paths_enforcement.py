r"""
Contract Test — Forbidden Pathing Patterns Enforcement.

Fails the build if runtime code reintroduces:
1. sys.path.insert anywhere
2. Path(__file__) composing paths to data/config/out/output
3. Hardcoded absolute home paths (/Users/, C:\, /home/)

Scans: lib/, api/, cli/, collectors/, engine/
Excludes: tests/, scripts/, docs/, data/, *.md, *.txt, *.sql
"""

import re
from pathlib import Path

# Directories to scan
SCAN_DIRS = ["lib", "api", "cli", "collectors", "engine"]

# Extensions to scan
SCAN_EXTENSIONS = {".py"}

# Directories to exclude (anywhere in path)
EXCLUDE_DIRS = {"tests", "scripts", "docs", "data", "__pycache__", ".git"}

# Extensions to exclude
EXCLUDE_EXTENSIONS = {".md", ".txt", ".sql"}


# Forbidden patterns with descriptions
FORBIDDEN_PATTERNS = [
    (
        re.compile(r"sys\.path\.insert"),
        "sys.path.insert (use proper package imports)",
    ),
    (
        re.compile(
            r'Path\(__file__\)\.parent(?:\.parent)*\s*/\s*["\'](?:data|config|out|output)["\']'
        ),
        "Path(__file__) to data/config/out/output (use lib.paths instead)",
    ),
    (
        re.compile(r'["\'][^"\']*(?:/Users/|C:\\\\|/home/)[^"\']*["\']'),
        "Hardcoded absolute home path (use lib.paths instead)",
    ),
]


def get_project_root() -> Path:
    """Get project root (parent of tests/ directory)."""
    return Path(__file__).parent.parent.parent


def should_scan_file(file_path: Path) -> bool:
    """Check if file should be scanned."""
    # Check extension
    if file_path.suffix not in SCAN_EXTENSIONS:
        return False
    if file_path.suffix in EXCLUDE_EXTENSIONS:
        return False

    # Check for excluded directories in path
    for part in file_path.parts:
        if part in EXCLUDE_DIRS:
            return False

    return True


def scan_file(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Scan a file for forbidden patterns.
    Returns list of (line_number, line_content, violation_description).
    """
    violations = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, description in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                violations.append((line_num, line.strip(), description))

    return violations


def scan_directory(dir_path: Path) -> dict[Path, list[tuple[int, str, str]]]:
    """
    Scan a directory recursively for forbidden patterns.
    Returns dict of {file_path: [(line_num, line, description), ...]}.
    """
    results = {}

    if not dir_path.exists():
        return results

    for file_path in dir_path.rglob("*"):
        if not file_path.is_file():
            continue
        if not should_scan_file(file_path):
            continue

        violations = scan_file(file_path)
        if violations:
            results[file_path] = violations

    return results


def test_no_forbidden_pathing_patterns():
    """
    Contract test: runtime code must not contain forbidden pathing patterns.

    Scans lib/, api/, cli/, collectors/, engine/ for:
    - sys.path.insert
    - Path(__file__) to data/config/out/output directories
    - Hardcoded absolute home paths
    """
    project_root = get_project_root()
    all_violations = {}

    for dir_name in SCAN_DIRS:
        dir_path = project_root / dir_name
        violations = scan_directory(dir_path)
        all_violations.update(violations)

    # Format violations for readable output
    if all_violations:
        print("\n" + "=" * 70)
        print("FORBIDDEN PATHING PATTERNS DETECTED")
        print("=" * 70)

        for file_path, violations in sorted(all_violations.items()):
            rel_path = file_path.relative_to(project_root)
            print(f"\n{rel_path}:")
            for line_num, line, description in violations:
                print(f"  L{line_num}: {description}")
                print(f"       {line[:80]}{'...' if len(line) > 80 else ''}")

        print("\n" + "=" * 70)
        total = sum(len(v) for v in all_violations.values())
        print(f"TOTAL: {total} violation(s) in {len(all_violations)} file(s)")
        print("=" * 70 + "\n")

    assert not all_violations, (
        f"Found {sum(len(v) for v in all_violations.values())} forbidden pathing pattern(s). "
        "See output above for details."
    )
