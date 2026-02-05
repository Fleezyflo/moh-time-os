# Step 2 — REPO DISCOVERY + STACK LOCK

## Objective
Identify the UI stack and lock the exact commands used to run/dev/build/test.

## Deliverables
Write: docs/ui_exec/00_STACK_LOCK.md including:
- framework (Next.js/Vite/Electron/Tauri/etc.)
- routing approach
- package manager + commands:
  - install
  - dev
  - build
  - test
- where pages/routes live
- where components live

## Acceptance checks
- `dev` command starts successfully.
- Agent records the command + output snippet in RUN_LOG.md.

## Stop condition
If the repo has no UI scaffold, STOP and propose the minimum scaffold, do not proceed.
