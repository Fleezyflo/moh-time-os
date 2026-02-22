# TASK: End-to-End Production Readiness Validation
> Brief: USER_READINESS | Phase: 6 | Sequence: 6.2 | Status: PENDING

## Context

This is the final validation task. Everything should be working: dead code removed, truth modules wired, snapshot producing real data, Google Chat notifications operational, API serving intelligence, daemon completing cycles.

## Objective

Comprehensive validation that the system is production-ready for Molham.

## Instructions

1. **Full test suite**:
   ```bash
   export PATH="/sessions/loving-blissful-keller/.local/bin:$PATH"
   cd /sessions/loving-blissful-keller/mnt/clawd/moh_time_os
   pytest tests/ -q
   ```
   Target: 0 failures, 0 errors. Count may be lower than 706 due to deleted test files — document the difference.

2. **Dead code verification**:
   ```bash
   # No tier references
   grep -rn "Tier [0-4]\|tier_gate\|feature_flags\.yaml" lib/ config/ tests/
   # No clawdbot references
   grep -rn "clawdbot\|Clawdbot" lib/ api/ config/
   # No morning brief references
   grep -rn "morning_brief\|generate_morning_brief" lib/ api/
   # No f-string SQL (from Brief 7)
   grep -rn "f\".*SELECT\|f'.*SELECT" lib/ --include="*.py" -l | grep -v migrations
   ```

3. **Daemon cycle**:
   ```bash
   python3 -m lib.daemon run-once
   ```
   Must complete without error. Verify `data/agency_snapshot.json` is fresh.

4. **Snapshot validation**:
   ```python
   import json
   with open("data/agency_snapshot.json") as f:
       snapshot = json.load(f)
   # Check key sections exist and have data
   assert snapshot.get("meta", {}).get("confidence") in ("healthy", "degraded")
   assert len(snapshot.get("delivery_command", {}).get("portfolio", [])) > 0
   assert len(snapshot.get("client_360", {}).get("portfolio", [])) > 0
   assert snapshot.get("cash_ar", {}).get("total_ar", 0) > 0
   ```

5. **API smoke test**:
   ```bash
   python3 -m uvicorn api.server:app --port 8000 &
   sleep 2
   # Hit 3 key endpoints
   curl -sf http://localhost:8000/api/v2/intelligence/portfolio/overview > /dev/null && echo "portfolio: OK"
   curl -sf http://localhost:8000/api/v5/health/dashboard > /dev/null && echo "health: OK"
   curl -sf http://localhost:8000/health > /dev/null && echo "system: OK"
   kill %1
   ```

6. **Google Chat notification**:
   Verify dry-run notification was sent during daemon cycle (check logs).

7. **Create `scripts/validate_production.py`**:
   Consolidate all above checks into a single runnable script that exits 0 on full pass.

8. **Document final system state**:
   - Total tests passing
   - Total tables, views
   - Files deleted in Brief 8
   - Lines removed vs added
   - Snapshot sections and data counts

## Preconditions
- [ ] All UR tasks 1.1 through 6.1 complete

## Validation
1. Full test suite: 0 failures, 0 errors
2. Dead code grep: all return empty
3. Daemon run-once: exits 0
4. Snapshot: valid, non-empty, passes validation
5. API: 3 key endpoints return 200
6. Google Chat: dry-run notification logged
7. `scripts/validate_production.py` exits 0

## On Completion
- Update HEARTBEAT:
  - Mark Brief USER_READINESS as ✅ COMPLETE
  - Update System State with final metrics
  - Record: "Dead code removed, truth modules active, Google Chat wired, daemon operational"
  - Set Active Work to awaiting next brief
- Commit all changes
- Push branch

## Acceptance Criteria
- [ ] Full test suite green
- [ ] Zero dead code references
- [ ] Daemon completes full cycle
- [ ] Snapshot contains real agency data
- [ ] API serves real intelligence
- [ ] Google Chat notification works (dry-run)
- [ ] Production validation script created
- [ ] HEARTBEAT updated

## Output
- Created: `scripts/validate_production.py`
- Updated: HEARTBEAT (brief completion, system state)
- Final commit on `brief/user-readiness` branch
