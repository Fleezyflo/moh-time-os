#!/usr/bin/env python3
"""
Auto-generate CHANGELOG.md from conventional commits.

Parses git history and groups commits by type:
- Features (feat)
- Bug Fixes (fix)
- Documentation (docs)
- Performance (perf)
- Breaking Changes (!)

Usage:
    python scripts/generate_changelog.py [--since TAG] [--output FILE]
"""

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

COMMIT_PATTERN = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<description>.+)$",
    re.IGNORECASE,
)

TYPE_LABELS = {
    "feat": "✨ Features",
    "fix": "🐛 Bug Fixes",
    "docs": "📚 Documentation",
    "perf": "⚡ Performance",
    "refactor": "♻️ Refactoring",
    "test": "🧪 Tests",
    "build": "📦 Build",
    "ci": "🔧 CI",
    "chore": "🧹 Chores",
}


def get_commits(since_tag: str | None = None) -> list[dict]:
    """Get commits since a tag or all commits."""
    cmd = ["git", "log", "--pretty=format:%H|%s|%an|%ad", "--date=short"]
    if since_tag:
        cmd.append(f"{since_tag}..HEAD")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0][:8],
                "subject": parts[1],
                "author": parts[2],
                "date": parts[3],
            })

    return commits


def parse_commits(commits: list[dict]) -> dict[str, list[dict]]:
    """Parse commits and group by type."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    breaking: list[dict] = []

    for commit in commits:
        match = COMMIT_PATTERN.match(commit["subject"])
        if match:
            commit_type = match.group("type").lower()
            scope = match.group("scope") or ""
            desc = match.group("description")
            is_breaking = bool(match.group("breaking"))

            entry = {
                "hash": commit["hash"],
                "scope": scope,
                "description": desc,
                "author": commit["author"],
                "date": commit["date"],
            }

            if is_breaking:
                breaking.append(entry)

            grouped[commit_type].append(entry)

    if breaking:
        grouped["breaking"] = breaking

    return grouped


def format_changelog(grouped: dict[str, list[dict]], version: str = "Unreleased") -> str:
    """Format grouped commits as markdown."""
    lines = [
        "# Changelog\n",
        f"## [{version}] - {datetime.now().strftime('%Y-%m-%d')}\n",
    ]

    # Breaking changes first
    if "breaking" in grouped:
        lines.append("\n### 💥 Breaking Changes\n")
        for entry in grouped["breaking"]:
            scope = f"**{entry['scope']}:** " if entry["scope"] else ""
            lines.append(f"- {scope}{entry['description']} ({entry['hash']})")

    # Then by type
    order = ["feat", "fix", "perf", "docs", "refactor", "test", "build", "ci", "chore"]
    for commit_type in order:
        if commit_type in grouped and grouped[commit_type]:
            label = TYPE_LABELS.get(commit_type, commit_type.title())
            lines.append(f"\n### {label}\n")
            for entry in grouped[commit_type]:
                scope = f"**{entry['scope']}:** " if entry["scope"] else ""
                lines.append(f"- {scope}{entry['description']} ({entry['hash']})")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate changelog from commits")
    parser.add_argument("--since", help="Generate since this tag")
    parser.add_argument("--output", "-o", default="CHANGELOG.md", help="Output file")
    parser.add_argument("--version", default="Unreleased", help="Version label")
    parser.add_argument("--print", "-p", action="store_true", help="Print to stdout")
    args = parser.parse_args()

    commits = get_commits(args.since)
    if not commits:
        print("No commits found")
        return 1

    grouped = parse_commits(commits)
    changelog = format_changelog(grouped, args.version)

    if args.print:
        print(changelog)
    else:
        with open(args.output, "w") as f:
            f.write(changelog)
        print(f"✅ Generated {args.output} with {len(commits)} commits")

    return 0


if __name__ == "__main__":
    sys.exit(main())
