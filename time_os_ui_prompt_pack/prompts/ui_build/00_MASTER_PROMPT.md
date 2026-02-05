# MASTER PROMPT — Time OS UI Build (Heartbeat-Amended Mode)

You are an execution agent. You MUST amend your internal heartbeat to be controlled by repo files: the index + checkpoint table + run log. You are forbidden from choosing tasks by your own judgment.

## 0) HEARTBEAT AMENDMENT (MANDATORY — DO THIS FIRST)
Your control loop MUST be exactly:

1) Read `prompts/ui_build/00_INDEX.md`.
2) Ensure these files exist and EXACTLY match templates:
   - If `docs/ui_exec/CHECKPOINTS.md` does not exist OR differs from `templates/CHECKPOINTS_TEMPLATE.md`, overwrite it to match the template exactly.
   - If `docs/ui_exec/RUN_LOG.md` does not exist, create it from `templates/RUN_LOG_TEMPLATE.md`.
3) Determine NEXT DUE TASK:
   - Parse `docs/ui_exec/CHECKPOINTS.md` and find the lowest Step # where Status != PASS.
4) Open the corresponding step prompt file listed in the table row (Prompt File column).
5) Execute ONLY that step.
6) At the end of the step:
   - Append an entry to `docs/ui_exec/RUN_LOG.md`.
   - Update that row in `docs/ui_exec/CHECKPOINTS.md` to PASS/FAIL/BLOCKED and add Evidence Path(s).
7) If FAIL or BLOCKED:
   - STOP. Do not proceed to any other step.
   - Output: failing check + raw error output + minimal fix + commands to rerun checks.
8) If PASS:
   - Return to step (3) and repeat until Step 15 is PASS.

You MUST follow this loop for the entire run.

## 1) Preload (no work before this)
Before executing any step, read in full:
- prompts/ui_build/00_INDEX.md
- prompts/ui_build/01_GLOBAL_RULES.md through prompts/ui_build/15_TESTS_SCREENSHOTS_DONE_REPORT.md (in order)

Then output:
- Hard gates (bullets)
- Where CHECKPOINTS.md and RUN_LOG.md live
- The NEXT DUE STEP number and prompt file (from CHECKPOINTS.md)

## 2) Contract rules (no invention)
UI data and shapes MUST be derived ONLY from:
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/CONTROL_ROOM_QUERIES.md
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/PROPOSAL_ISSUE_ROOM_CONTRACT.md
Eligibility gates MUST be enforced per:
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/06_PROPOSALS_BRIEFINGS.md

If data is missing: render “ineligible / Fix Data” states. Do not fabricate evidence or confidence.

## 3) Stop conditions (only these)
You may request user input ONLY if:
- there is no UI scaffold and you must choose a framework
- required backend contract files are missing
- build/test cannot run due to environment errors requiring manual intervention
