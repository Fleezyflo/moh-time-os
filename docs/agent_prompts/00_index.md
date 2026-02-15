# Agent Prompt Bundle Index (Docs Last)

Order:
00 Index
01 Data collection inventory (exclude Docs implementation)
02 Correctness review (pagination/cursor invariants)
03 Practical queries (exclude Docs)
04 Docs pipeline spec (explain only)
05 Performance & storage audit
06 Sweep completeness & resume (converges after restarts)
07 Docs (LAST): resumable + aggregated counters + proofs
99 Verification bundle

Global DONE criteria (non-docs):
- partial_subjects_count == 0
- errors_count == 0
- active_targets_attempted == active_targets_total
