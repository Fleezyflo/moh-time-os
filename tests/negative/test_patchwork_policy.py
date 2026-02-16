"""
test_patchwork_policy.py - Ensure patchwork patterns are blocked.

This test runs the patchwork scan as part of pytest to ensure no one
can bypass the scan by forgetting to run the shell script in CI.

The test imports the banned patterns and scans the critical paths,
failing if any violations are found.
"""

import re
import subprocess
from pathlib import Path

import pytest

# Project root (moh_time_os/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Critical paths to scan (relative to project root)
SCAN_PATHS = [
    "lib/agency_snapshot/",
    "lib/contracts/",
    "lib/normalize/",
]

# Banned patterns (must match patchwork_scan.sh)
UNIVERSAL_BANNED_PATTERNS = {
    "setdefault": r"\.setdefault\s*\(",
    "update_dict": r"\.update\s*\(\s*\{",
    "deepmerge": r"deepmerge|deep_merge",
    "enrich_snapshot": r"enrich_snapshot",
}

# Snapshot mutation pattern (context-dependent for generator.py)
SNAPSHOT_MUTATION_PATTERN = r"snapshot\[.+\]\s*="


def _is_excluded_line(content: str, filepath: str) -> bool:
    """Check if a line should be excluded from violation reporting."""
    # Exclude comments
    if re.match(r"^\s*#", content):
        return True

    # Exclude test files
    if "test_" in filepath or "_test.py" in filepath:
        return True

    # Exclude string literals containing patterns (definitions, not code)
    if re.search(r'PATTERNS\s*=|BANNED|".*setdefault.*"', content, re.IGNORECASE):
        return True

    # Exclude initial snapshot creation
    if re.match(r"^\s*snapshot\s*=\s*\{", content):
        return True

    # Exclude _drawers dict (legitimate accumulator)
    if "_drawers[" in content:
        return True

    # Exclude counter/accumulator patterns
    if re.search(r"\[[^\]]+\]\s*\+=", content):
        return True

    return False


def _find_patchwork_boundary_line(filepath: Path) -> int:
    """Find the line number of PATCHWORK_BOUNDARY marker in a file."""
    try:
        with open(filepath) as f:
            for lineno, line in enumerate(f, 1):
                if "PATCHWORK_BOUNDARY" in line:
                    return lineno
    except Exception:
        pass
    return 999999  # No boundary = scan entire file


def _scan_file(filepath: Path, patterns: dict[str, str]) -> list[tuple[str, int, str, str]]:
    """
    Scan a file for banned patterns.

    Returns list of (pattern_name, lineno, content, filepath) tuples.
    """
    violations = []

    try:
        with open(filepath) as f:
            lines = f.readlines()
    except Exception:
        return violations

    for pattern_name, pattern in patterns.items():
        regex = re.compile(pattern)
        for lineno, line in enumerate(lines, 1):
            if regex.search(line):
                if not _is_excluded_line(line, str(filepath)):
                    violations.append((pattern_name, lineno, line.strip(), str(filepath)))

    return violations


def _scan_for_snapshot_mutations(filepath: Path) -> list[tuple[str, int, str, str]]:
    """
    Scan for snapshot mutations with context-awareness for generator.py.

    In generator.py, only mutations AFTER PATCHWORK_BOUNDARY are violations.
    In other files, all snapshot mutations are violations.
    """
    violations = []
    regex = re.compile(SNAPSHOT_MUTATION_PATTERN)

    try:
        with open(filepath) as f:
            lines = f.readlines()
    except Exception:
        return violations

    # For generator.py, get the boundary line
    is_generator = "generator.py" in str(filepath)
    boundary_line = _find_patchwork_boundary_line(filepath) if is_generator else 0

    for lineno, line in enumerate(lines, 1):
        if regex.search(line):
            if _is_excluded_line(line, str(filepath)):
                continue

            # For generator.py, only flag mutations AFTER boundary
            if is_generator and lineno < boundary_line:
                continue

            violations.append(("snapshot_mutation", lineno, line.strip(), str(filepath)))

    return violations


class TestPatchworkPolicy:
    """Test that patchwork patterns are not present in critical paths."""

    def test_no_universal_banned_patterns(self):
        """Scan for universally banned patterns (setdefault, update, deepmerge, etc.)."""
        violations = []

        for scan_path in SCAN_PATHS:
            full_path = PROJECT_ROOT / scan_path
            if not full_path.exists():
                continue

            for py_file in full_path.rglob("*.py"):
                # Skip __pycache__
                if "__pycache__" in str(py_file):
                    continue

                file_violations = _scan_file(py_file, UNIVERSAL_BANNED_PATTERNS)
                violations.extend(file_violations)

        if violations:
            msg = f"Found {len(violations)} patchwork violations:\n"
            for pattern, lineno, content, filepath in violations[:10]:  # Show first 10
                rel_path = str(Path(filepath).relative_to(PROJECT_ROOT))
                msg += f"  [{pattern}] {rel_path}:{lineno}: {content[:80]}\n"
            if len(violations) > 10:
                msg += f"  ... and {len(violations) - 10} more\n"
            pytest.fail(msg)

    def test_no_post_assembly_snapshot_mutations(self):
        """Scan for snapshot mutations in post-assembly zones."""
        violations = []

        for scan_path in SCAN_PATHS:
            full_path = PROJECT_ROOT / scan_path
            if not full_path.exists():
                continue

            for py_file in full_path.rglob("*.py"):
                # Skip __pycache__
                if "__pycache__" in str(py_file):
                    continue

                file_violations = _scan_for_snapshot_mutations(py_file)
                violations.extend(file_violations)

        if violations:
            msg = f"Found {len(violations)} post-assembly snapshot mutations:\n"
            for pattern, lineno, content, filepath in violations[:10]:
                rel_path = str(Path(filepath).relative_to(PROJECT_ROOT))
                msg += f"  [{pattern}] {rel_path}:{lineno}: {content[:80]}\n"
            if len(violations) > 10:
                msg += f"  ... and {len(violations) - 10} more\n"
            msg += "\nMove mutations BEFORE PATCHWORK_BOUNDARY marker or upstream to normalize/."
            pytest.fail(msg)

    def test_patchwork_boundary_exists_in_generator(self):
        """Ensure generator.py has PATCHWORK_BOUNDARY marker."""
        generator_path = PROJECT_ROOT / "lib" / "agency_snapshot" / "generator.py"

        if not generator_path.exists():
            pytest.skip("generator.py not found")

        with open(generator_path) as f:
            content = f.read()

        assert "PATCHWORK_BOUNDARY" in content, (
            "generator.py must have a PATCHWORK_BOUNDARY marker to define "
            "the assembly completion point. Add this comment after all "
            "snapshot[...] = assignments are complete."
        )

    def test_shell_scan_matches_pytest_scan(self):
        """Verify shell script scan agrees with Python scan."""
        # Run the shell script
        script_path = PROJECT_ROOT / "scripts" / "patchwork_scan.sh"

        if not script_path.exists():
            pytest.skip("patchwork_scan.sh not found")

        result = subprocess.run(
            ["bash", str(script_path), "--ci"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        # Both should pass (exit 0) since previous tests already validated no violations
        assert result.returncode == 0, (
            f"Shell script patchwork_scan.sh failed but Python scan passed.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
