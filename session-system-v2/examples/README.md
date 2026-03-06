# Session System Example: TaskFlow Project

This directory contains a **concrete instantiation** of the session system applied to a real-ish project: **TaskFlow**, a task management API with a React frontend.

## What This Shows

- **state.json**: Current project state at session 4. Phase 0 and 1 are complete. Phase 2 (Authentication) is in progress. Phases 3 and 4 are queued.
- **plan/index.yaml**: Master phase index matching the state.
- **plan/phase-02.yaml**: Detailed specification for the in-progress Authentication phase, with 6 tasks across user modeling, password hashing, API endpoints, JWT, middleware, and rate limiting.
- **sessions/session-004.yaml**: Work record for the current session, showing what was completed, files changed, and discoveries.
- **AGENT.md**: The filled-in agent configuration for TaskFlow, specifying environment constraints, code rules, and verification gates.

## Why This Matters

The session system is designed to make knowledge **persistent and machine-readable**. Each file serves a concrete purpose:

1. **state.json** answers: "Where is the project right now?"
2. **plan/phase-N.yaml** answers: "What work remains in this phase?"
3. **sessions/session-NNN.yaml** answers: "What happened in that session?"
4. **AGENT.md** answers: "What are the non-negotiable rules for working on this project?"

Together, they allow an agent (human or AI) to:
- Jump into any session without ramp-up
- Know the exact next task without asking for context
- Understand why a file was changed or why a task was blocked
- Hand off work cleanly between people and sessions
- Avoid repeating mistakes

## The TaskFlow Project

TaskFlow is a hypothetical but realistic project:

- **Backend**: Python API with FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React 18 with TypeScript, Vite bundler
- **Scope**: Task CRUD, user auth, priority/status tracking, shared task lists
- **Team constraint**: Shared sandbox environment (Linux x86) and developer Mac (Darwin ARM)
- **CI/CD**: GitHub Actions with pre-commit, lint, type checking, bandit

The phases show a realistic progression from project setup → API core → auth → UI → integration tests.

## How to Read This Example

Start with **state.json** to see the overall picture. Then read **phase-02.yaml** to see what granular task tracking looks like. Finally, check **session-004.yaml** to see how work is recorded.

The **AGENT.md** at the bottom is what gets checked into the TaskFlow repo itself. It's the source of truth for how to work on the project.

## Note on Completeness

This example is intentionally **partial** — it shows a snapshot at session 4, not a complete project history. In a real project, you would also have `phase-00.yaml` through `phase-04.yaml`, `session-001.yaml` through `session-003.yaml`, and a generated `HANDOFF.md`. Running `check_state.py` against this directory will report missing files, which is expected. The purpose here is to show the format and content of each file type, not to be a passing validation target.
