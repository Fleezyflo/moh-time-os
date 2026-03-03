#!/usr/bin/env python3
"""
Generates HANDOFF.md from structured state files for the Detection System build.

Adapted from session-system-v2/core/scripts/generate_handoff.py.
HANDOFF.md is generated from state.json, plan specs, and session records.

Usage:
    python detection-system/scripts/generate_handoff.py          # Generate
    python detection-system/scripts/generate_handoff.py --check  # Verify only
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


BASE = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_latest_session() -> dict | None:
    sessions_dir = BASE / "sessions"
    if not sessions_dir.exists():
        return None
    session_files = sorted(
        f for f in sessions_dir.glob("session-*.yaml") if f.name != "session-template.yaml"
    )
    if not session_files:
        return None
    return load_yaml(session_files[-1])


def get_current_phase_spec(phase_id: str | None) -> dict | None:
    if not phase_id:
        return None
    spec_path = BASE / "plan" / f"{phase_id}.yaml"
    if spec_path.exists():
        return load_yaml(spec_path)
    return None


def get_next_tasks(phase_spec: dict, state_phase: dict) -> list[dict]:
    """Find the next incomplete tasks in the current phase."""
    if not phase_spec:
        return []
    tasks = phase_spec.get("tasks", []) or []
    completed = state_phase.get("tasks_complete", 0)
    return tasks[completed:]


def generate_handoff() -> str:
    state = load_json(BASE / "state.json")
    latest_session = get_latest_session()
    current_phase_id = state.get("current_phase")
    current_phase_spec = get_current_phase_spec(current_phase_id)
    current_phase_state = state.get("phases", {}).get(current_phase_id or "", {})

    lines: list[str] = []

    # Header
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# HANDOFF -- MOH Time OS Detection System")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Session:** {state.get('current_session', 0)}")
    lines.append(
        f"**Current Phase:** {current_phase_id or 'None'}"
        f" ({current_phase_state.get('status', 'unknown')})"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # What Just Happened
    lines.append("## What Just Happened")
    lines.append("")
    if latest_session:
        lines.append(
            f"Session {latest_session.get('session', '?')} "
            f"({latest_session.get('date', '?')}) -- "
            f"Type: {latest_session.get('type', '?')}"
        )
        lines.append("")
        for item in latest_session.get("work_done", []) or []:
            desc = item.get("description", "")
            lines.append(f"- {desc}")
        lines.append("")
        prs = latest_session.get("prs", []) or []
        if prs:
            lines.append("**PRs:**")
            for pr in prs:
                lines.append(
                    f"- #{pr.get('number', '?')} -- {pr.get('status', '?')} "
                    f"(CI: {pr.get('ci_status', '?')})"
                )
            lines.append("")
    else:
        lines.append("No previous session recorded. This is the first session.")
        lines.append("")

    # Phase Status Table
    lines.append("## Phase Status")
    lines.append("")
    lines.append("| Phase | Status | Tasks | PRs |")
    lines.append("|-------|--------|-------|-----|")
    for phase_id in sorted(state.get("phases", {}).keys()):
        phase = state["phases"][phase_id]
        status = phase.get("status", "?")
        marker = {
            "complete": "DONE",
            "in_progress": "ACTIVE",
            "blocked": "BLOCKED",
            "pending": "READY",
        }.get(status, "?")
        tasks_info = f"{phase.get('tasks_complete', 0)}/{phase.get('tasks_total', '?')}"
        prs = ", ".join(f"#{p}" for p in phase.get("prs", []))
        lines.append(f"| {phase_id} | {marker} | {tasks_info} | {prs} |")
    lines.append("")

    # What's Next
    lines.append("## What's Next")
    lines.append("")
    if current_phase_spec:
        next_tasks = get_next_tasks(current_phase_spec, current_phase_state)
        if next_tasks:
            lines.append(
                f"**Phase:** {current_phase_id} -- {current_phase_spec.get('name', 'Unknown')}"
            )
            lines.append("")
            lines.append(
                f"**Progress:** {current_phase_state.get('tasks_complete', 0)}"
                f"/{current_phase_state.get('tasks_total', '?')} tasks complete"
            )
            lines.append("")
            lines.append("**Next tasks:**")
            lines.append("")
            for task in next_tasks[:3]:
                lines.append(f"### {task.get('id', '?')}: {task.get('name', '?')}")
                lines.append("")
                desc = task.get("description", "").strip()
                if desc:
                    lines.append(desc)
                    lines.append("")
                files = task.get("files", {})
                if files.get("create") or files.get("modify"):
                    lines.append("**Files:**")
                    for f in files.get("create", []):
                        lines.append(f"- CREATE `{f}`")
                    for f in files.get("modify", []):
                        lines.append(f"- MODIFY `{f}`")
                    lines.append("")
                verification = task.get("verification", [])
                if verification:
                    lines.append("**Verification:**")
                    for v in verification:
                        lines.append(f"- {v}")
                    lines.append("")
        else:
            lines.append(
                f"All tasks in {current_phase_id} appear complete. "
                "Verify and mark phase as complete."
            )
            lines.append("")
    else:
        for phase_id in sorted(state.get("phases", {}).keys()):
            phase = state["phases"][phase_id]
            if phase.get("status") in ("pending", "blocked"):
                lines.append(f"Next phase: **{phase_id}** (status: {phase['status']})")
                if phase.get("blocked_by"):
                    lines.append(f"Blocked by: {', '.join(phase['blocked_by'])}")
                lines.append("")
                break
        else:
            lines.append("All phases complete.")
            lines.append("")

    # Key Rules (static for detection system)
    lines.append("## Key Rules")
    lines.append("")
    lines.append(
        "- All calendar queries use `events JOIN calendar_attendees`, NEVER `calendar_events`"
    )
    lines.append("- Revenue queries use COALESCE with try/except for missing columns")
    lines.append(
        "- `collect_calendar_for_user()` fetches but does NOT persist -- use `CalendarCollector.sync()`"
    )
    lines.append("- Sandbox cannot run git, format, install, or dev servers")
    lines.append("- Commit subjects max 72 chars, first letter after prefix lowercase")
    lines.append("- Stage ALL files before committing")
    lines.append("- ADR required when modifying api/server.py (Phase 15c)")
    lines.append("- System map regeneration required for new fetch('/api/...') calls")
    lines.append("")

    # Documents to Read
    lines.append("## Documents to Read")
    lines.append("")
    if current_phase_id:
        lines.append(f"1. `detection-system/plan/{current_phase_id}.yaml` -- Current phase spec")
    lines.append("2. `detection-system/AGENT.md` -- Engineering rules and verification gates")
    lines.append("3. `detection-system/commit-workflow.md` -- Error recovery protocol")
    lines.append("4. `docs/design/DETECTION_SYSTEM_DESIGN.md` -- Full design document")
    lines.append("5. `CLAUDE.md` -- Repo-level rules")
    lines.append("")

    return "\n".join(lines)


def main():
    check_mode = "--check" in sys.argv
    content = generate_handoff()
    handoff_path = BASE / "HANDOFF.md"

    if check_mode:
        if not handoff_path.exists():
            print("FAIL: HANDOFF.md does not exist -- run generate_handoff.py to create it")
            sys.exit(1)

        existing = handoff_path.read_text()

        def strip_timestamp(text: str) -> str:
            return "\n".join(
                line for line in text.splitlines() if not line.startswith("**Generated:**")
            )

        if strip_timestamp(existing) != strip_timestamp(content):
            print("FAIL: HANDOFF.md is stale or was hand-edited")
            print("Run `python detection-system/scripts/generate_handoff.py` to regenerate")
            sys.exit(1)
        else:
            print("HANDOFF.md is up to date")
            sys.exit(0)

    with open(handoff_path, "w") as f:
        f.write(content)
    print(f"Generated {handoff_path}")


if __name__ == "__main__":
    main()
