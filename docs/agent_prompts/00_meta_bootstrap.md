# Meta Bootstrap — Autonomous Agent Contract (Single Entry)

You are an autonomous agent operating inside this repo.

Hard rule: docs/agent_prompts/00_index.md is the ONLY ordering authority.
Hard rule: Docs execution is LAST (Prompt 07). Do not execute Docs earlier.

## Step 0 — Prove bundle exists (no ambiguity)
Run:
- pwd
- ls -lah docs/agent_prompts
- sed -n '1,120p' docs/agent_prompts/00_index.md

If any required file is missing, STOP and print the missing filename(s).

## Step 1 — Create outputs folder (idempotent)
Run:
- mkdir -p docs/agent_outputs

## Step 2 — Execution loop (deterministic)
For each prompt in the index order (01,02,03,04,05,06,07,99):
- Read the prompt file fully.
- Produce the deliverable exactly as specified.
- Write results to:
  docs/agent_outputs/<NN>_<slug>_output.md
- Include:
  - the command(s) you ran
  - the proof outputs (logs/sqlite output)
  - any code references requested (file/function names)
- If a prompt requires code changes:
  - implement minimal diff
  - include unified diff in the output file

## Step 3 — Verification (non-docs)
When Prompt 99 is reached:
- output the HEARTBEAT snippet requested by Prompt 99
- do not include Docs in those checks

## Drift prevention
- Do not invent new tasks.
- If a prompt is unclear, edit ONLY the prompt file (minimal change) and record a short changelog section at the top of the output file.

Begin by completing Step 0 and then execute Prompt 01.
