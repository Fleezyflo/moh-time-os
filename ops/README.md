# MOH Time OS — Operations

Runtime supervision for MOH Time OS on macOS. Two launchd LaunchAgents run the system:

| Agent | Plist | Runs | Port |
|-------|-------|------|------|
| `com.mohtimeos.api` | `com.mohtimeos.api.plist` (repo root) | `python3 -m api.server` (uvicorn) | 8420 |
| `com.mohtime.daemon` | `ops/com.mohtime.daemon.plist` | `python -m lib.daemon` (in-process 8-stage scheduler) | — |

## Install (API first, then daemon)

Install the API agent **before** the daemon — the API is the surface the UI needs, and
the daemon's `collect` stage depends on a healthy DB/API path.

```bash
# API
cp com.mohtimeos.api.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mohtimeos.api.plist

# Daemon
cp ops/com.mohtime.daemon.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mohtime.daemon.plist

# Verify both
launchctl list | grep mohtime
lsof -nP -iTCP:8420 -sTCP:LISTEN
```

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.mohtimeos.api
launchctl bootout gui/$(id -u)/com.mohtime.daemon
rm ~/Library/LaunchAgents/com.mohtimeos.api.plist ~/Library/LaunchAgents/com.mohtime.daemon.plist
```

## Cron stays DISABLED — the daemon is the sole scheduler

The crontab line `*/15 * * * * ... -m lib.collectors.orchestrator sync` is intentionally
commented out (`#DISABLED`) and must remain so. `lib/daemon.py` is an in-process scheduler
that already runs `collect` every 30 minutes plus the other 7 stages. Re-enabling cron would:

- double-run the collectors, and
- re-trigger the `lock_contention` ("gmail collector is already running") that stalled
  gmail/calendar data at 2026-02-12.

`scripts/install_cron.sh` exists but must **not** be re-run. There is no fallback cron
scheduler by design — the launchd daemon is authoritative.

## Where runtime state lives

Code and `WorkingDirectory` are the repo (`/Users/molhamhomsi/clawd/moh_time_os`), but
runtime state resolves to a separate home-data tree via `lib/paths.py` (`Path.home()/.moh_time_os/data`):

| File | Path |
|------|------|
| Daemon job state | `~/.moh_time_os/data/daemon_state.json` |
| Daemon PID | `~/.moh_time_os/data/daemon.pid` |
| Database | `~/.moh_time_os/data/moh_time_os.db` (symlink → repo `data/moh_time_os.db`) |

This is intentional, but means **"is it running?" diagnosis must check `~/.moh_time_os/data/`,
not the repo `data/`**. The daemon must never run with `HOME=/Users/molham` (the legacy broken
plist home, fixed in `ops/com.mohtime.daemon.plist`); under that home, PID and state writes
would land in a nonexistent tree.
