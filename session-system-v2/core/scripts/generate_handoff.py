#!/usr/bin/env python3
"""
Generates HANDOFF.md from structured state files.

HANDOFF.md is NEVER hand-edited. It is always generated from:
- state.json (current project status)
- plan/index.yaml + plan/phase-NN.yaml (what needs to happen)
- sessions/session-NNN.yaml (what has happened)
- AGENT.md (rules summary)

This eliminates stale handoffs. The generated file is always consistent
with the structured state because it's derived from it.
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


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_latest_session(base: Path) -> dict | None:
    sessions_dir = base / "sessions"
    if not sessions_dir.exists():
        return None
    session_files = sorted(sessions_dir.glob("session-*.yaml"))
    if not session_files:
        return None
    return load_yaml(session_files[-1])


def get_current_phase_spec(base: Path, phase_id: str | None) -> dict | None:
    if not phase_id:
        return None
    spec_path = base / "plan" / f"{phase_id}.yaml"
    if spec_path.exists():
        return load_yaml(spec_path)
    return None


def get_next_tasks(phase_spec: dict, state_phase: dict) -> list[dict]:
    """Find the next incomplete tasks in the current phase."""
    if not phase_spec:
        return []
    tasks = phase_spec.get("tasks", []) or []
    completed = state_phase.get("tasks_complete", 0)
    # Return tasks starting from the first incomplete one
    return tasks[completed:]


def generate_handoff(base: Path) -> str:
    state = load_json(base / "state.json")
    load_yaml(base / "plan" / "index.yaml")  # validates plan exists
    latest_session = get_latest_session(base)
    current_phase_id = state.get("current_phase")
    current_phase_spec = get_current_phase_spec(base, current_phase_id)
    current_phase_state = state.get("phases", {}).get(current_phase_id or "", {})

    lines: list[str] = []

    # Header
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# Session Handoff")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Project:** {state.get('project', 'Unknown')}")
    lines.append(f"**Session:** {state.get('current_session', 0)}")
    lines.append(
        f"**Current Phase:** {current_phase_id or 'None'}"
        f" ({current_phase_state.get('status', 'unknown')})"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> **This file is generated. Do not hand-edit.**")
    lines.append("> Run `python scripts/generate_handoff.py` to regenerate.")
    lines.append("")

    # What Just Happened
    lines.append("## What Just Happened")
    lines.append("")
    if latest_session:
        lines.append(
            f"Session {latest_session.get('session', '?')} "
            f"({latest_session.get('date', '?')}) — "
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
                    f"- #{pr.get('number', '?')} — {pr.get('status', '?')} "
                    f"(CI: {pr.get('ci_status', '?')})"
                )
            lines.append("")
    else:
        lines.append("No previous session recorded.")
        lines.append("")

    # Current State
    lines.append("## Phase Status")
    lines.append("")
    lines.append("| Phase | Status | Session | PRs |")
    lines.append("|-------|--------|---------|-----|")
    # Sort phases by ID
    for phase_id in sorted(state.get("phases", {}).keys()):
        phase = state["phases"][phase_id]
        status = phase.get("status", "?")
        marker = {"complete": "✅", "in_progress": "🔨", "blocked": "🚫", "pending": "⏳"}.get(
            status, "?"
        )
        session_info = ""
        if status == "complete":
            session_info = str(phase.get("completed_session", "?"))
        elif status == "in_progress":
            session_info = f"started {phase.get('started_session', '?')}"
        prs = ", ".join(f"#{p}" for p in phase.get("prs", []))
        lines.append(f"| {phase_id} | {marker} {status} | {session_info} | {prs} |")
    lines.append("")

    # What's Next
    lines.append("## What's Next")
    lines.append("")
    if current_phase_spec:
        next_tasks = get_next_tasks(current_phase_spec, current_phase_state)
        if next_tasks:
            lines.append(
                f"**Phase:** {current_phase_id} — {current_phase_spec.get('name', 'Unknown')}"
            )
            lines.append("")
            lines.append(
                f"**Progress:** {current_phase_state.get('tasks_complete', 0)}"
                f"/{current_phase_state.get('tasks_total', '?')} tasks complete"
            )
            lines.append("")
            lines.append("**Next tasks:**")
            lines.append("")
            for task in next_tasks[:3]:  # Show up to 3 next tasks
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
        # Find next pending/blocked phase
        for phase_id in sorted(state.get("phases", {}).keys()):
            phase = state["phases"][phase_id]
            if phase.get("status") in ("pending", "blocked"):
                lines.append(f"Next phase: **{phase_id}** (status: {phase['status']})")
                if phase.get("blocked_by"):
                    lines.append(f"Blocked by: {', '.join(phase['blocked_by'])}")
                lines.append("")
                break
        else:
            lines.append("All phases complete. No more work planned.")
            lines.append("")

    # Documents to Read
    lines.append("## Documents to Read")
    lines.append("")
    lines.append("1. `state.json` — Current project state (you should have already read this)")
    lines.append("2. `AGENT.md` — Rules and protocols")
    if current_phase_id:
        lines.append(f"3. `plan/{current_phase_id}.yaml` — Current phase spec")
    lines.append(
        f"{'4' if current_phase_id else '3'}. Latest session YAML — What the last session did"
    )
    lines.append("")

    # Enforcement
    enforcement = state.get("enforcement", {})
    if enforcement.get("repo"):
        lines.append("## Enforcement")
        lines.append("")
        lines.append(f"- **Repo:** {enforcement['repo']}")
        lines.append(f"- **Read token:** `{enforcement.get('read_token_secret', '?')}`")
        lines.append(f"- **Dispatch token:** `{enforcement.get('dispatch_token_secret', '?')}`")
        protected = enforcement.get("protected_files", [])
        if protected:
            lines.append(f"- **Protected files:** {len(protected)} files")
        lines.append("")

    return "\n".join(lines)


def main():
    check_mode = "--check" in sys.argv

    base = Path(".")
    if not (base / "state.json").exists():
        for candidate in [Path("session-system"), Path(".")]:
            if (candidate / "state.json").exists():
                base = candidate
                break
        else:
            if check_mode:
                print("SKIP: No state.json found — session system not initialized")
                sys.exit(0)
            print("ERROR: No state.json found")
            sys.exit(1)

    content = generate_handoff(base)
    handoff_path = base / "HANDOFF.md"

    if check_mode:
        # Compare generated content against existing HANDOFF.md
        # Ignores the "Generated:" timestamp line for comparison
        if not handoff_path.exists():
            print("FAIL: HANDOFF.md does not exist — run generate_handoff.py to create it")
            sys.exit(1)

        existing = handoff_path.read_text()

        def strip_timestamp(text: str) -> str:
            """Remove the Generated: line so timestamp differences don't cause false failures."""
            return "\n".join(
                line for line in text.splitlines() if not line.startswith("**Generated:**")
            )

        if strip_timestamp(existing) != strip_timestamp(content):
            print("FAIL: HANDOFF.md is stale or was hand-edited")
            print("Run `python scripts/generate_handoff.py` to regenerate it")
            sys.exit(1)
        else:
            print("✅ HANDOFF.md is up to date")
            sys.exit(0)

    with open(handoff_path, "w") as f:
        f.write(content)
    print(f"✅ Generated {handoff_path}")


if __name__ == "__main__":
    main()
