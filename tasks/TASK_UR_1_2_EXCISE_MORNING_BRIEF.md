# TASK: Remove Morning Brief + Clawdbot Channel
> Brief: USER_READINESS | Phase: 1 | Sequence: 1.2 | Status: PENDING

## Context

The morning brief system (`lib/brief.py`, `lib/notifier/briefs.py`, `lib/time_truth/brief.py`) and Clawdbot notification channel are being replaced. Morning brief is removed entirely. Clawdbot is replaced by Google Chat (task UR-4.1).

## Objective

Remove all morning brief code and Clawdbot integration. The NotificationEngine stays (it's the routing infrastructure), but Clawdbot-specific loading and the default channel are removed.

## Files to DELETE (entire file)

| File | Lines | Reason |
|------|-------|--------|
| `lib/brief.py` | 242 | Morning brief generation |
| `lib/notifier/briefs.py` | 226 | Brief generation + sending (daily, midday, EOD) |
| `lib/notifier/channels/clawdbot.py` | 194 | Clawdbot notification channel |
| `lib/integrations/clawdbot_api.py` | 100+ | Clawdbot gateway REST client |

## Files for SURGICAL REMOVAL

| File | What to Remove |
|------|---------------|
| `lib/time_truth/brief.py` | Remove `generate_time_brief()` function and its `_format_markdown()` / `_format_plain()` helpers. Keep other functions if any exist. If file becomes empty, delete it. |
| `lib/time_truth/__init__.py` | Remove imports of `generate_time_brief`, `get_time_truth_status` from __all__ and import statements |
| `lib/cron_tasks.py` | Remove `cron_morning_brief()` function (lines 27-49), remove `from .brief import generate_morning_brief` import, remove "morning_brief" from cron config |
| `cli.py` | Remove `cmd_brief()` function, remove `generate_morning_brief` / `generate_status_summary` / `generate_client_status` imports, remove `brief` subcommand from argparse |
| `lib/notifier/channels/__init__.py` | Remove `from .clawdbot import ClawdbotChannel` and `"ClawdbotChannel"` from __all__ |
| `lib/integrations/__init__.py` | Remove `from .clawdbot_api import ClawdbotAPI, get_clawdbot_api` and their __all__ entries |
| `lib/notifier/engine.py` | Remove clawdbot channel loading (lines 37-42), change default channel from "clawdbot" to raise ValueError("No notification channel configured") at lines 112, 114, 219, 221 |
| `config/governance.yaml` | Remove clawdbot notification settings section (lines 50-90), remove clawdbot from channel lists in types section |
| `api/server.py` | Remove `from lib.time_truth import generate_time_brief` import, remove the API endpoint that calls it |

## Deletion Order (dependency-safe)

1. Delete test files (none identified for brief — verify with grep)
2. Delete complete files: `lib/brief.py`, `lib/notifier/briefs.py`, `lib/notifier/channels/clawdbot.py`, `lib/integrations/clawdbot_api.py`
3. Surgical removal in order:
   - `lib/notifier/channels/__init__.py`
   - `lib/integrations/__init__.py`
   - `lib/time_truth/brief.py` (or delete if empty after removal)
   - `lib/time_truth/__init__.py`
   - `lib/cron_tasks.py`
   - `cli.py`
   - `lib/notifier/engine.py`
   - `config/governance.yaml`
   - `api/server.py`

## Instructions

1. Delete files in order above
2. For each surgical removal, make the specific changes listed
3. Verify no dangling imports:
   ```bash
   grep -rn "from.*brief import\|import.*brief\|clawdbot\|ClawdbotChannel\|ClawdbotAPI\|generate_morning_brief\|generate_time_brief" lib/ api/ cli.py config/ --include="*.py" --include="*.yaml"
   ```
4. Run test suite

## Preconditions
- [ ] UR-1.1 complete (tier system removed)

## Validation
1. `grep -rn "clawdbot\|Clawdbot\|CLAWDBOT" lib/ api/ config/` returns empty
2. `grep -rn "morning_brief\|generate_morning_brief\|generate_time_brief" lib/ api/ cli.py` returns empty
3. `python3 -c "from lib.notifier.engine import NotificationEngine"` succeeds
4. `python3 -c "from lib.cron_tasks import get_cron_config"` succeeds
5. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] 4 files deleted
- [ ] 9 files surgically cleaned
- [ ] Zero clawdbot references
- [ ] Zero morning brief references
- [ ] NotificationEngine still importable (ready for Google Chat channel)
- [ ] Test suite passes

## Output
- Deleted: 4 files (~762 lines)
- Modified: 9 files
