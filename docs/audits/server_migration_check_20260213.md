# server.py Migration Check — 2026-02-13

## Verdict: ⚠️ NEEDS REVIEW — UI still depends on server.py endpoints

## Endpoint Comparison
- Spec router endpoints: 31
- Server legacy endpoints: 135
- In both (normalized paths): 14
- Only in spec_router: 17
- Only in server.py: 118

## UI Dependency Analysis
The UI (`time-os-ui/src/`) actively calls server.py endpoints:

| Path Pattern | UI References | Status |
|--------------|--------------|--------|
| `/api/v*` | 86 | CALLED — main API prefix |
| `/api/control-room/*` | 25 | CALLED — control room features |
| `/api/clients/*` | 12 | CALLED — partially in spec_router |
| `/api/tasks/*` | 11 | CALLED — not in spec_router |
| `/api/priorities/*` | 10 | CALLED — in spec_router |
| `/api/projects/*` | 8 | CALLED — in spec_router |
| `/api/data-quality/*` | 6 | CALLED — not in spec_router |
| `/api/health` | 6 | CALLED — in spec_router |
| `/api/commitments/*` | 6 | CALLED — not in spec_router |
| `/api/capacity/*` | 6 | CALLED — not in spec_router |
| `/api/bundles/*` | 6 | CALLED — not in spec_router |

## Server-Only Endpoints (118 total)

### High Priority — Called by UI
| Path | Method | Purpose |
|------|--------|---------|
| `/api/tasks/*` | GET/POST | Task management |
| `/api/data-quality/*` | GET | Data quality dashboard |
| `/api/commitments/*` | GET/POST | Commitment tracking |
| `/api/capacity/*` | GET/POST | Capacity planning |
| `/api/bundles/*` | GET/POST | Bundle management |
| `/api/control-room/*` | GET/POST | Control room features |

### Medium Priority — May be called externally
| Path | Method | Purpose |
|------|--------|---------|
| `/api/calendar/*` | GET | Calendar data |
| `/api/notifications/*` | GET/POST | Notification system |
| `/api/governance/*` | GET | Governance rules |
| `/api/sync/*` | POST | Sync triggers |

### Low Priority — Likely unused
| Path | Method | Purpose |
|------|--------|---------|
| `/api/admin/*` | POST | Admin functions |
| `/api/anomalies` | GET | Legacy anomaly endpoint |
| `/api/analyze` | POST | Legacy analyze endpoint |

## Migration Options

### Option A: Keep server.py running alongside spec_router
- **Risk:** Two codebases to maintain
- **Effort:** None
- **Recommendation:** Current state, acceptable short-term

### Option B: Migrate called endpoints to spec_router
- **Risk:** Breaking changes if not careful
- **Effort:** High (50+ endpoints)
- **Recommendation:** Not recommended during SYSPREP

### Option C: Archive server.py but keep API paths working
- **Risk:** Need to ensure all paths route correctly
- **Effort:** Medium
- **Recommendation:** Post-SYSPREP work

## Recommendation

**DO NOT archive server.py** during Phase 1. The UI actively depends on ~50+ legacy endpoints not yet in spec_router.

**Instead:**
1. Mark server.py as "legacy — do not extend"
2. Continue using spec_router for new features
3. Plan gradual migration post-SYSPREP
4. Archive only when UI is fully migrated to spec_router

## Action Items for Moh's Review
1. Confirm OK to keep server.py running for now
2. Decide if endpoint migration should be added as Phase 4+ work
3. Confirm UI can be updated to use spec_router paths when ready
