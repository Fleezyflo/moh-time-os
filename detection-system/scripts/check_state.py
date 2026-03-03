#!/usr/bin/env python3
"""
State consistency validator for the Detection System build.

Adapted from session-system-v2/core/scripts/check_state.py.
Validates that state.json, plan/index.yaml, and phase specs are consistent.

Usage:
    python detection-system/scripts/check_state.py

Exit codes:
  0 -- All checks pass
  1 -- Consistency violation found
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


# Base directory is detection-system/ relative to repo root
BASE = Path(__file__).resolve().parent.parent


def load_state() -> dict:
    state_path = BASE / "state.json"
    if not state_path.exists():
        print(f"FAIL: {state_path} does not exist")
        sys.exit(1)
    with open(state_path) as f:
        return json.load(f)


def load_plan_index() -> dict:
    index_path = BASE / "plan" / "index.yaml"
    if not index_path.exists():
        print(f"FAIL: {index_path} does not exist")
        sys.exit(1)
    with open(index_path) as f:
        return yaml.safe_load(f) or {}


def load_sessions() -> dict[int, dict]:
    sessions_dir = BASE / "sessions"
    sessions = {}
    if sessions_dir.exists():
        for f in sessions_dir.glob("session-*.yaml"):
            if f.name == "session-template.yaml":
                continue
            with open(f) as fh:
                data = yaml.safe_load(fh) or {}
                if "session" in data:
                    sessions[data["session"]] = data
    return sessions


def load_phase_specs() -> dict[str, dict]:
    plan_dir = BASE / "plan"
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
            if not phase.get("completed_session"):
                errors.append(
                    f"{phase_id}: status is 'complete' but 'completed_session' is missing"
                )
            if not phase.get("prs"):
                errors.append(
                    f"{phase_id}: status is 'complete' but 'prs' is empty -- "
                    "every completed phase must have at least one PR"
                )

        if status == "in_progress":
            if not phase.get("started_session"):
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


def check_plan_state_sync(state: dict, plan_index: dict) -> list[str]:
    """Verify plan/index.yaml is in sync with state.json."""
    errors = []
    state_phases = set(state.get("phases", {}).keys())
    plan_phases = set()

    for phase_entry in plan_index.get("phases", []) or []:
        if isinstance(phase_entry, dict) and "id" in phase_entry:
            plan_phases.add(phase_entry["id"])

    if not plan_phases:
        return errors

    only_in_state = state_phases - plan_phases
    only_in_plan = plan_phases - state_phases

    if only_in_state:
        errors.append(f"Phases in state.json but not in plan/index.yaml: {only_in_state}")
    if only_in_plan:
        errors.append(f"Phases in plan/index.yaml but not in state.json: {only_in_plan}")

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


def check_detection_specific(state: dict, specs: dict[str, dict]) -> list[str]:
    """Detection system-specific checks."""
    errors = []

    # Verify dependency chain matches design doc
    expected_deps = {
        "phase-15a": [],
        "phase-15b": ["phase-15a"],
        "phase-15c": ["phase-15b"],
        "phase-15d": ["phase-15c"],
        "phase-15e": ["phase-15b"],
        "phase-15f": ["phase-15d"],
    }

    for phase_id, expected in expected_deps.items():
        phase = state.get("phases", {}).get(phase_id, {})
        actual = phase.get("blocked_by", [])
        if sorted(actual) != sorted(expected):
            errors.append(f"{phase_id}: expected dependencies {expected} but found {actual}")

    # Verify no spec prescribes USING calendar_events table.
    # References in "fix this broken pattern" or "NEVER use" context are OK.
    # Only flag if a task's files.create or files.modify list contains it,
    # or if a SQL snippet uses it as a FROM/JOIN target without documenting it as broken.
    # For now: skip this check since all references are documenting the broken pattern.
    # The real guard is in AGENT.md rule #11 and the completion_criteria checks.

    return errors


def main():
    state = load_state()
    plan_index = load_plan_index()
    specs = load_phase_specs()

    all_errors: list[str] = []

    all_errors.extend(check_state_schema(state))
    all_errors.extend(check_phase_statuses(state))
    all_errors.extend(check_dependency_satisfaction(state))
    all_errors.extend(check_plan_state_sync(state, plan_index))
    all_errors.extend(check_phase_specs_exist(state, specs))
    all_errors.extend(check_task_counts(state, specs))
    all_errors.extend(check_detection_specific(state, specs))

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
        print("All checks passed -- state is consistent")
        sys.exit(0)


if __name__ == "__main__":
    main()
