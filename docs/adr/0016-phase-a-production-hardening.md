# ADR-0016: Phase A Production Hardening

**Date:** 2026-03-08
**Status:** Accepted
**Context:** Audit remediation Phase A

## Decision

Add production hardening to api/server.py: real health checks (503 on critical failure), /api/ready probe, path traversal prevention, and CORS wildcard warning at startup.

## Changes

### API (api/server.py)
- `GET /api/health` -- wired to HealthChecker, returns component status map, 503 if any critical component is down
- `GET /api/ready` -- lightweight 200 probe for load balancer readiness checks
- Path traversal prevention on file-serving endpoints using Path.resolve + is_relative_to
- CORS wildcard origin warning logged at startup when running in production mode

### Daemon (lib/daemon.py)
- RotatingFileHandler (50MB, 5 backups) for log rotation
- Memory monitoring via resource.getrusage every 10 ticks
- Cycle timing wired to PerformanceMonitor

### Collectors
- XeroCollector circuit breaker and retry config (lib/collectors/xero.py)
- WatchdogTimer using SIGALRM (lib/collectors/watchdog.py)
- Per-future timeouts in collectors/scheduled_collect.py
- Stale lock detection with PID and TTL in lib/collector_registry.py

## Rationale

Production deployment requires health endpoints that reflect real system state (not stub 200s), path traversal guards on file-serving routes, and collector reliability improvements. ADR required because api/server.py is a governance-trigger file.
