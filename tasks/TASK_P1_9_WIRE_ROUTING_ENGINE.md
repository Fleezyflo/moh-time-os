# TASK: Wire Routing Engine
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.9 | Status: PENDING

## Context

`lib/routing_engine.py` (291 lines) exists with real routing logic but zero imports from outside itself.

Functions:
- `route_item(item: dict) -> dict` — routes a single item to the correct Asana list
- `batch_route(items: list[dict]) -> list[dict]` — routes a batch
- `check_duplicates(items: list[dict]) -> list[dict]` — deduplicates items
- `generate_dedupe_key(item: dict) -> str` — generates dedup key
- `determine_destination_list(item: dict) -> tuple[str, str]` — determines target list/section
- `should_mirror_to_waiting(item: dict) -> bool` — determines if item should mirror
- `format_task_title(item: dict) -> str` — formats Asana task title
- `format_task_notes(item: dict) -> str` — formats Asana task notes
- `format_calendar_block(item: dict, start_time: str, duration_minutes: int) -> dict` — formats calendar block

## Objective

Wire the routing engine into the action framework so that actions creating Asana tasks go through proper routing and deduplication.

## Instructions

### 1. Wire into `lib/actions/action_framework.py`

When the action framework creates Asana tasks, route through `routing_engine`:

```python
from lib.routing_engine import route_item, check_duplicates

# Before creating Asana task:
routed = route_item(task_data)
# routed now has correct list, section, title format
```

### 2. Wire into `lib/integrations/chat_commands.py` or `api/chat_webhook_router.py`

If chat commands create tasks, they should also route through the engine.

### 3. Read the module first

Understand what `route_item()` expects as input dict shape and what it returns. Adapt the callers accordingly.

## Preconditions
- [ ] None

## Validation
1. Action-created tasks routed to correct Asana lists
2. Duplicates detected before creation
3. `ruff check`, `bandit` clean
4. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] `route_item()` called before Asana task creation
- [ ] `check_duplicates()` prevents duplicate task creation
- [ ] ruff, bandit clean

## Output
- Modified: `lib/actions/action_framework.py` and/or `lib/integrations/chat_commands.py`

## Estimate
1.5 hours

## Branch
`feat/wire-routing-engine`
