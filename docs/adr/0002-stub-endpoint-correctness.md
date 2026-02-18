# ADR-0002: Stub Endpoint Correctness

## Status
Accepted

## Context
Several endpoints and handlers were returning fake success responses without implementing actual functionality:

1. `POST /api/tasks/link` returned `{"success": True, "message": "Bulk link not implemented yet"}`
2. `TaskHandler._sync_to_asana()` was a silent `pass` stub
3. `TaskHandler._complete_in_asana()` was a silent `pass` stub

This violates correctness: callers believe operations succeeded when nothing happened.

Additionally, `TasksCollector.collect()` was swallowing exceptions and returning empty data, making failures appear as "no tasks found" rather than errors.

## Decision
1. **Stub endpoints**: Return HTTP 501 (Not Implemented) instead of fake success
2. **Stub handlers**: Raise `NotImplementedError` instead of silent `pass`
3. **Error swallowing**: Propagate exceptions to caller (which has proper error handling)

## Consequences
- Callers that depended on fake success will now see explicit 501 errors
- This is the correct behavior: better to fail explicitly than silently lie
- Tests added to verify 501 responses and error propagation

## Affected Files
- api/server.py (`POST /api/tasks/link` → 501)
- lib/executor/handlers/task.py (`_sync_to_asana`, `_complete_in_asana` → NotImplementedError)
- lib/collectors/tasks.py (`collect()` → re-raise instead of swallow)
- lib/collectors/orchestrator.py (`health_check()` → log before returning False)
