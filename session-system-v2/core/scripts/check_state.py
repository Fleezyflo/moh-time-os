#!/usr/bin/env python3
"""
State consistency validator.

Runs as a pre-commit hook. Blocks commits if state.json, plan/index.yaml,
and session records are inconsistent with each other.

This is the mechanism that prevents documentation drift. It does not rely
on the agent choosing to update files correctly. It structurally prevents
inconsistency from being committed.

Exit codes:
  0 — All checks pass
  1 — Consistency violation found (commit blocked)
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


def load_state(base: Path) -> dict:
    state_path = base / "state.json"
    if not state_path.exists():
        print(f"FAIL: {state_path} does not exist")
        sys.exit(1)
    with open(state_path) as f:
        return json.load(f)


def load_plan_index(base: Path) -> dict:
    index_path = base / "plan" / "index.yaml"
    if not index_path.exists():
        print(f"FAIL: {index_path} does not exist")
        sys.exit(1)
    with open(index_path) as f:
        return yaml.safe_load(f) or {}


def load_sessions(base: Path) -> dict[int, dict]:
    sessions_dir = base / "sessions"
    sessions = {}
    if sessions_dir.exists():
        for f in sessions_dir.glob("session-*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh) or {}
                if "session" in data:
                    sessions[data["session"]] = data
    return sessions


def load_phase_specs(base: Path) -> dict[str, dict]:
    plan_dir = base / "plan"
    specs = {}
    for f in plan_dir.glob("phase-*.yaml"):
        if f.name == "phase-template.yaml":
            continue
        with open(f) as fh:
            data = yaml.safe_load(fh) or {}
            if "id" in data:
                specs[data["id"]] = data
    return specs


def check_state_schema(state: dict) -> list[str]:
    """Basic structural validation of state.json."""
    errors = []
    required = ["project", "current_session", "phases", "last_pr", "enforcement"]
    for field in required:
        if field not in state:
            errors.append(f"state.json missing required field: {field}")
    if not isinstance(state.get("phases", None), dict):
        errors.append("state.json 'phases' must be an object")
    return errors


def check_phase_statuses(state: dict) -> list[str]:
    """Validate phase status values and lifecycle rules."""
    errors = []
    valid_statuses = {"pending", "blocked", "in_progress", "complete"}

    for phase_id, phase in state.get("phases", {}).items():
        status = phase.get("status")
        if status not in valid_statuses:
            errors.append(f"{phase_id}: invalid status '{status}'")
            continue

        if status == "complete":
            if "completed_session" not in phase:
                errors.append(
                    f"{phase_id}: status is 'complete' but 'completed_session' is missing"
                )
            if not phase.get("prs"):
                errors.append(
                    f"{phase_id}: status is 'complete' but 'prs' is empty — "
                    "every completed phase must have at least one PR"
                )

        if status == "in_progress":
            if "started_session" not in phase:
                errors.append(
                    f"{phase_id}: status is 'in_progress' but 'started_session' is missing"
                )

        if status == "blocked":
            if not phase.get("blocked_by"):
                errors.append(f"{phase_id}: status is 'blocked' but 'blocked_by' is empty")

    return errors


def check_dependency_satisfaction(state: dict) -> list[str]:
    """Verify no phase is in_progress/complete while dependencies are incomplete."""
    errors = []
    phases = state.get("phases", {})

    for phase_id, phase in phases.items():
        if phase.get("status") in ("in_progress", "complete"):
            for dep in phase.get("blocked_by", []):
                dep_phase = phases.get(dep)
                if not dep_phase:
                    errors.append(
                        f"{phase_id}: depends on '{dep}' which doesn't exist in state.json"
                    )
                elif dep_phase.get("status") != "complete":
                    errors.append(
                        f"{phase_id}: status is '{phase['status']}' but dependency "
                        f"'{dep}' is '{dep_phase.get('status')}'"
                    )

    return errors


def check_current_phase(state: dict) -> list[str]:
    """Verify current_phase matches actual state."""
    errors = []
    current = state.get("current_phase")
    phases = state.get("phases", {})

    if current is None and phases:
        # No current phase — check if there's an in_progress phase
        in_progress = [pid for pid, p in phases.items() if p.get("status") == "in_progress"]
        if in_progress:
            errors.append(f"current_phase is null but these phases are in_progress: {in_progress}")
    elif current is not None:
        if current not in phases:
            errors.append(f"current_phase '{current}' not found in phases")
        elif phases[current].get("status") not in ("in_progress", "complete"):
            errors.append(
                f"current_phase '{current}' has status "
                f"'{phases[current].get('status')}' — expected 'in_progress'"
            )

    return errors


def check_plan_state_sync(state: dict, plan_index: dict) -> list[str]:
    """Verify plan/index.yaml is in sync with state.json."""
    errors = []
    state_phases = set(state.get("phases", {}).keys())
    plan_phases = set()

    for phase_entry in plan_index.get("phases", []) or []:
        if isinstance(phase_entry, dict) and "id" in phase_entry:
            plan_phases.add(phase_entry["id"])

    # If plan has no phases yet (template state), skip
    if not plan_phases:
        return errors

    only_in_state = state_phases - plan_phases
    only_in_plan = plan_phases - state_phases

    if only_in_state:
        errors.append(f"Phases in state.json but not in plan/index.yaml: {only_in_state}")
    if only_in_plan:
        errors.append(f"Phases in plan/index.yaml but not in state.json: {only_in_plan}")

    return errors


def check_session_records(state: dict, sessions: dict[int, dict]) -> list[str]:
    """Verify session records are consistent with state.json."""
    errors = []
    phases = state.get("phases", {})

    for phase_id, phase in phases.items():
        if phase.get("status") == "complete":
            completed_session = phase.get("completed_session")
            if completed_session and completed_session not in sessions:
                errors.append(
                    f"{phase_id}: completed in session {completed_session} "
                    f"but no session record exists for session {completed_session}"
                )

    return errors


def check_phase_specs_exist(state: dict, specs: dict[str, dict]) -> list[str]:
    """Verify every phase in state.json has a spec file."""
    errors = []
    for phase_id in state.get("phases", {}):
        if phase_id not in specs:
            errors.append(
                f"{phase_id}: exists in state.json but no plan/{phase_id}.yaml spec file found"
            )
    return errors


def check_task_counts(state: dict, specs: dict[str, dict]) -> list[str]:
    """Verify task counts in state.json match spec files."""
    errors = []
    for phase_id, phase in state.get("phases", {}).items():
        if phase_id not in specs:
            continue
        spec = specs[phase_id]
        spec_tasks = len(spec.get("tasks", []) or [])
        state_total = phase.get("tasks_total", 0)

        if spec_tasks > 0 and state_total > 0 and spec_tasks != state_total:
            errors.append(
                f"{phase_id}: state.json says {state_total} tasks but spec has {spec_tasks} tasks"
            )

        tasks_complete = phase.get("tasks_complete", 0)
        if tasks_complete > state_total and state_total > 0:
            errors.append(
                f"{phase_id}: tasks_complete ({tasks_complete}) > tasks_total ({state_total})"
            )

    return errors


def main():
    # Find project root (directory containing state.json)
    base = Path(".")
    if not (base / "state.json").exists():
        # Try common locations
        for candidate in [Path("session-system"), Path(".")]:
            if (candidate / "state.json").exists():
                base = candidate
                break
        else:
            print("SKIP: No state.json found — session system not initialized")
            sys.exit(0)

    state = load_state(base)
    plan_index = load_plan_index(base)
    sessions = load_sessions(base)
    specs = load_phase_specs(base)

    all_errors: list[str] = []

    all_errors.extend(check_state_schema(state))
    all_errors.extend(check_phase_statuses(state))
    all_errors.extend(check_dependency_satisfaction(state))
    all_errors.extend(check_current_phase(state))
    all_errors.extend(check_plan_state_sync(state, plan_index))
    all_errors.extend(check_session_records(state, sessions))
    all_errors.extend(check_phase_specs_exist(state, specs))
    all_errors.extend(check_task_counts(state, specs))

    if all_errors:
        print("=" * 60)
        print("STATE CONSISTENCY CHECK FAILED")
        print("=" * 60)
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. {error}")
        print()
        print(f"Total: {len(all_errors)} error(s)")
        print("Fix these before committing.")
        sys.exit(1)
    else:
        print("✅ State consistency check passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
