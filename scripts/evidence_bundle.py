#!/usr/bin/env python3
"""
Evidence Bundle Generator.

Produces a comprehensive artifact for PR review:
- OpenAPI diff summary
- Schema diff summary
- System-map diff summary
- UI bundle report
- Smoke logs with request_id
- Scenario harness summary
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

EVIDENCE_DIR = Path("evidence")


def run_cmd(cmd: list[str], capture: bool = True) -> tuple[int, str]:
    """Run a command and return exit code + output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr if capture else ""
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def get_git_diff(path: str) -> str:
    """Get git diff for a specific path."""
    code, output = run_cmd(["git", "diff", "--stat", path])
    if code == 0 and output.strip():
        return output.strip()
    return "No changes"


def generate_evidence() -> dict:
    """Generate all evidence artifacts."""
    evidence = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "git_sha": "",
        "git_branch": "",
        "sections": {},
    }

    # Git info
    _, sha = run_cmd(["git", "rev-parse", "HEAD"])
    evidence["git_sha"] = sha.strip()

    _, branch = run_cmd(["git", "branch", "--show-current"])
    evidence["git_branch"] = branch.strip()

    # OpenAPI diff
    print("📋 Checking OpenAPI diff...")
    evidence["sections"]["openapi"] = {
        "diff": get_git_diff("docs/openapi.json"),
        "check_passed": run_cmd(["uv", "run", "python", "scripts/export_openapi.py", "--check"])[0] == 0,
    }

    # Schema diff
    print("📊 Checking schema diff...")
    evidence["sections"]["schema"] = {
        "diff": get_git_diff("docs/schema.sql"),
        "check_passed": run_cmd(["uv", "run", "python", "scripts/export_schema.py", "--check"])[0] == 0,
    }

    # System map diff
    print("🗺️  Checking system-map diff...")
    evidence["sections"]["system_map"] = {
        "diff": get_git_diff("docs/system-map.json"),
        "check_passed": run_cmd(["uv", "run", "python", "scripts/generate_system_map.py", "--check"])[0] == 0,
    }

    # UI bundle report
    print("📦 Checking UI bundle...")
    ui_build_code, ui_build_output = run_cmd(
        ["pnpm", "run", "bundle:check"],
        capture=True,
    )
    evidence["sections"]["ui_bundle"] = {
        "output": ui_build_output[:2000],  # Truncate
        "passed": ui_build_code == 0,
    }

    # Smoke test
    print("🔥 Running smoke test...")
    smoke_code, smoke_output = run_cmd(
        ["uv", "run", "python", "scripts/smoke_test.py"],
        capture=True,
    )
    evidence["sections"]["smoke"] = {
        "output": smoke_output[:5000],
        "passed": smoke_code == 0,
    }

    # Scenarios
    print("🎭 Running scenarios...")
    scenarios_code, scenarios_output = run_cmd(
        ["uv", "run", "pytest", "tests/scenarios/", "-v", "--tb=short"],
        capture=True,
    )
    evidence["sections"]["scenarios"] = {
        "output": scenarios_output[:5000],
        "passed": scenarios_code == 0,
    }

    return evidence


def save_evidence(evidence: dict) -> Path:
    """Save evidence to file."""
    EVIDENCE_DIR.mkdir(exist_ok=True)

    # Summary markdown
    summary_path = EVIDENCE_DIR / "summary.md"
    with open(summary_path, "w") as f:
        f.write("# Evidence Bundle\n\n")
        f.write(f"Generated: {evidence['generated_at']}\n")
        f.write(f"Git SHA: `{evidence['git_sha'][:8]}`\n")
        f.write(f"Branch: `{evidence['git_branch']}`\n\n")

        f.write("## Checks\n\n")
        f.write("| Check | Status |\n")
        f.write("|-------|--------|\n")

        for name, data in evidence["sections"].items():
            status = "✅" if data.get("passed") or data.get("check_passed") else "❌"
            f.write(f"| {name} | {status} |\n")

        f.write("\n## Details\n\n")
        for name, data in evidence["sections"].items():
            f.write(f"### {name}\n\n")
            if "diff" in data:
                f.write(f"```\n{data['diff']}\n```\n\n")
            if "output" in data:
                f.write(f"```\n{data['output'][:1000]}\n```\n\n")

    # Full JSON
    json_path = EVIDENCE_DIR / "evidence.json"
    json_path.write_text(json.dumps(evidence, indent=2) + "\n")

    return summary_path


def main():
    print("=" * 60)
    print("Evidence Bundle Generator")
    print("=" * 60)
    print()

    evidence = generate_evidence()
    summary_path = save_evidence(evidence)

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    all_passed = all(
        data.get("passed", data.get("check_passed", False))
        for data in evidence["sections"].values()
    )

    for name, data in evidence["sections"].items():
        status = "✅" if data.get("passed") or data.get("check_passed") else "❌"
        print(f"{status} {name}")

    print()
    print(f"Evidence saved to: {summary_path}")

    if all_passed:
        print("\n✅ All checks passed")
    else:
        print("\n❌ Some checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
