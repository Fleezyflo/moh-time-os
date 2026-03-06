#!/usr/bin/env python3
"""
System-wide validator for cross-file consistency.

Validates all system files parse correctly and checks consistency across:
- state.json: project state and phase tracking
- plan/*.yaml: phase definitions and tasks
- sessions/session-*.yaml: session records
- HANDOFF.md and AGENT.md: documentation

Exit codes:
  0: all checks passed
  1: one or more checks failed
  2: missing dependencies or invalid configuration
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Try to import yaml with clear error message
try:
    import yaml
except ImportError:
    logger.error("PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(2)


class ValidationError(Exception):
    """Raised when a validation check fails."""

    pass


class SystemValidator:
    """Validates system-wide file consistency."""

    def __init__(self, root_dir: Path, strict: bool = False):
        self.root = Path(root_dir).resolve()
        self.strict = strict
        self.checks_passed = 0
        self.checks_failed = 0
        self.errors: list[str] = []

    def run(self) -> bool:
        """Run all validation checks. Returns True if all pass."""
        print(f"Validating system at {self.root}")
        print()

        # Phase 1: Parse all files
        print("=== File Parsing ===")
        state_data = self._validate_state_json()
        phase_files = self._validate_plan_files()
        session_files = self._validate_session_files()
        self._validate_docs()

        # Phase 2: Cross-file consistency
        print()
        print("=== Cross-File Consistency ===")
        if state_data:
            self._validate_state_references(state_data, phase_files, session_files)

        # Phase 3: Strict mode
        if self.strict:
            print()
            print("=== Strict Mode ===")
            if state_data:
                self._validate_state_strict(state_data)
            if phase_files:
                self._validate_phase_files_strict(phase_files)
            if session_files:
                self._validate_session_files_strict(session_files)

        # Summary
        print()
        print("=== Summary ===")
        total = self.checks_passed + self.checks_failed
        print(f"Passed: {self.checks_passed}/{total}")
        if self.checks_failed > 0:
            print(f"Failed: {self.checks_failed}/{total}")
            print()
            for error in self.errors:
                print(f"  ❌ {error}")

        return self.checks_failed == 0

    def _check(self, condition: bool, message: str) -> None:
        """Record a check result."""
        if condition:
            print(f"  ✓ {message}")
            self.checks_passed += 1
        else:
            print(f"  ❌ {message}")
            self.checks_failed += 1
            self.errors.append(message)

    def _validate_state_json(self) -> dict[str, Any] | None:
        """Validate state.json exists and parses."""
        state_file = self.root / "state.json"

        if not state_file.exists():
            self._check(False, "state.json exists")
            return None

        try:
            with open(state_file) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self._check(False, f"state.json valid JSON: {e}")
            return None

        self._check(True, "state.json exists and valid JSON")

        # Check required top-level fields
        required_fields = {"project", "owner", "current_phase", "current_session", "phases"}
        missing = required_fields - set(data.keys())
        self._check(
            not missing,
            f"state.json has required fields (missing: {missing})"
            if missing
            else "state.json has required fields",
        )

        # Check phases structure
        if "phases" in data and isinstance(data["phases"], dict):
            for phase_id, phase_data in data["phases"].items():
                if not isinstance(phase_data, dict):
                    self._check(False, f"state.json phases[{phase_id}] is dict")
                    continue

                required_phase_fields = {"status", "started_session", "completed_session"}
                missing_phase = required_phase_fields - set(phase_data.keys())
                self._check(
                    not missing_phase,
                    f"state.json phases[{phase_id}] has required fields"
                    if not missing_phase
                    else f"state.json phases[{phase_id}] missing fields: {missing_phase}",
                )
        else:
            self._check(False, "state.json phases is dict")

        return data

    def _validate_plan_files(self) -> dict[str, dict[str, Any]]:
        """Validate all plan/*.yaml files."""
        plan_dir = self.root / "plan"
        phase_files = {}

        if not plan_dir.exists():
            self._check(False, "plan/ directory exists")
            return phase_files

        self._check(True, "plan/ directory exists")

        # Filter out index.yaml (registry file, not a phase spec)
        yaml_files = sorted(
            f
            for f in plan_dir.glob("*.yaml")
            if f.name != "index.yaml" and f.name != "phase-template.yaml"
        )
        if not yaml_files:
            self._check(False, "plan/ has phase files (*.yaml)")
            return phase_files

        self._check(True, "plan/ has phase files (*.yaml)")

        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self._check(False, f"plan/{yaml_file.name} valid YAML: {e}")
                continue

            if not isinstance(data, dict):
                self._check(False, f"plan/{yaml_file.name} is dict, not {type(data).__name__}")
                continue

            # Check required fields
            required_fields = {"id", "name", "description", "tasks"}
            missing = required_fields - set(data.keys())
            self._check(
                not missing,
                f"plan/{yaml_file.name} has required fields"
                if not missing
                else f"plan/{yaml_file.name} missing fields: {missing}",
            )

            # Check tasks structure
            if "tasks" in data:
                if not isinstance(data["tasks"], list):
                    self._check(False, f"plan/{yaml_file.name} tasks is list")
                else:
                    for idx, task in enumerate(data["tasks"]):
                        if not isinstance(task, dict):
                            self._check(False, f"plan/{yaml_file.name} task[{idx}] is dict")
                            continue

                        required_task_fields = {
                            "id",
                            "name",
                            "description",
                            "files",
                            "verification",
                        }
                        missing_task = required_task_fields - set(task.keys())
                        self._check(
                            not missing_task,
                            f"plan/{yaml_file.name} task[{idx}] has required fields"
                            if not missing_task
                            else f"plan/{yaml_file.name} task[{idx}] missing: {missing_task}",
                        )

            phase_files[yaml_file.stem] = data

        return phase_files

    def _validate_session_files(self) -> dict[str, dict[str, Any]]:
        """Validate all sessions/session-*.yaml files."""
        sessions_dir = self.root / "sessions"
        session_files = {}

        if not sessions_dir.exists():
            self._check(False, "sessions/ directory exists")
            return session_files

        self._check(True, "sessions/ directory exists")

        yaml_files = sorted(sessions_dir.glob("session-*.yaml"))
        if not yaml_files:
            self._check(False, "sessions/ has session files (session-*.yaml)")
            return session_files

        self._check(True, "sessions/ has session files (session-*.yaml)")

        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self._check(False, f"sessions/{yaml_file.name} valid YAML: {e}")
                continue

            if not isinstance(data, dict):
                self._check(False, f"sessions/{yaml_file.name} is dict, not {type(data).__name__}")
                continue

            # Check required fields
            required_fields = {"session", "date", "type", "assignment", "work_done"}
            missing = required_fields - set(data.keys())
            self._check(
                not missing,
                f"sessions/{yaml_file.name} has required fields"
                if not missing
                else f"sessions/{yaml_file.name} missing fields: {missing}",
            )

            session_files[yaml_file.stem] = data

        return session_files

    def _validate_docs(self) -> None:
        """Validate required documentation files exist and are non-empty."""
        handoff_file = self.root / "HANDOFF.md"
        agent_file = self.root / "AGENT.md"

        # Check HANDOFF.md
        handoff_exists = handoff_file.exists()
        self._check(handoff_exists, "HANDOFF.md exists")

        if handoff_exists:
            content = handoff_file.read_text().strip()
            self._check(len(content) > 0, "HANDOFF.md is non-empty")

        # Check AGENT.md
        agent_exists = agent_file.exists()
        self._check(agent_exists, "AGENT.md exists")

        if agent_exists:
            content = agent_file.read_text().strip()
            self._check(len(content) > 0, "AGENT.md is non-empty")

    def _validate_state_references(
        self,
        state_data: dict[str, Any],
        phase_files: dict[str, dict[str, Any]],
        session_files: dict[str, dict[str, Any]],
    ) -> None:
        """Validate cross-file references between state.json and other files."""
        # Check that all phases in state.json have corresponding plan files
        if "phases" in state_data:
            state_phase_ids = set(state_data["phases"].keys())
            plan_phase_ids = {
                data.get("id")
                for data in phase_files.values()
                if isinstance(data, dict) and "id" in data
            }

            missing_plan_files = state_phase_ids - plan_phase_ids
            self._check(
                not missing_plan_files,
                "All state.json phase IDs have plan files"
                if not missing_plan_files
                else f"Missing plan files for phases: {missing_plan_files}",
            )

        # Check that current_session references an existing session file
        # Session filenames may be zero-padded (e.g., session-004.yaml for session 4)
        if "current_session" in state_data:
            current_session = state_data["current_session"]
            session_exists = any(
                data.get("session") == current_session
                for data in session_files.values()
                if isinstance(data, dict)
            )
            self._check(
                session_exists,
                f"state.json current_session {current_session} has a matching session file",
            )

        # Check that phase IDs in plan files match state.json keys
        for filename, data in phase_files.items():
            if not isinstance(data, dict) or "id" not in data:
                continue

            phase_id = data["id"]
            in_state = phase_id in state_data.get("phases", {})
            self._check(in_state, f"plan/{filename}.yaml phase ID '{phase_id}' is in state.json")

        # Check session filename consistency
        # Session filenames may be zero-padded (session-004 for session 4)
        for filename, data in session_files.items():
            if not isinstance(data, dict) or "session" not in data:
                continue

            session_num = data["session"]
            # Extract the numeric part from filename (e.g., "session-004" -> 4)
            try:
                filename_num = int(filename.replace("session-", ""))
                matches = filename_num == session_num
            except ValueError:
                matches = False
            self._check(
                matches, f"sessions/{filename}.yaml filename matches session number {session_num}"
            )

    def _validate_state_strict(self, state_data: dict[str, Any]) -> None:
        """Strict mode: validate required fields are non-empty."""
        required_nonempty = {"project", "owner", "current_phase"}
        for field in required_nonempty:
            if field in state_data:
                is_nonempty = bool(state_data[field])
                self._check(is_nonempty, f"state.json {field} is non-empty")

    def _validate_phase_files_strict(self, phase_files: dict[str, dict[str, Any]]) -> None:
        """Strict mode: validate phase file fields are non-empty."""
        for filename, data in phase_files.items():
            if not isinstance(data, dict):
                continue

            required_nonempty = {"id", "name", "description"}
            for field in required_nonempty:
                if field in data:
                    is_nonempty = bool(data[field])
                    self._check(is_nonempty, f"plan/{filename}.yaml {field} is non-empty")

    def _validate_session_files_strict(self, session_files: dict[str, dict[str, Any]]) -> None:
        """Strict mode: validate session file fields are non-empty."""
        for filename, data in session_files.items():
            if not isinstance(data, dict):
                continue

            required_nonempty = {"session", "date", "type", "assignment"}
            for field in required_nonempty:
                if field in data:
                    is_nonempty = bool(data[field])
                    self._check(is_nonempty, f"sessions/{filename}.yaml {field} is non-empty")


def main() -> int:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate system-wide file consistency")
    parser.add_argument(
        "root_dir",
        nargs="?",
        default=".",
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode: check for non-empty required fields",
    )

    args = parser.parse_args()

    root = Path(args.root_dir)
    if not root.exists():
        logger.error(f"Root directory does not exist: {root}")
        return 2

    validator = SystemValidator(root, strict=args.strict)
    success = validator.run()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
