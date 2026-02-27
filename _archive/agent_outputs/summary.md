# Evidence Bundle

Generated: 2026-02-11T06:46:49.650561Z
Git SHA: `018929cb`
Branch: `recover-wip`

## Checks

| Check | Status |
|-------|--------|
| openapi | ✅ |
| schema | ✅ |
| system_map | ✅ |
| ui_bundle | ✅ |
| smoke | ✅ |
| scenarios | ✅ |

## Details

### openapi

```
No changes
```

### schema

```
No changes
```

### system_map

```
No changes
```

### ui_bundle

```

> time-os-ui@0.0.0 bundle:check /Users/molhamhomsi/clawd/moh_time_os/time-os-ui
> node scripts/check-bundle-size.js

  JS: index-D3HmgqV5.js: 392.1KB
  CSS: index-DsuTRVru.css: 47.6KB
✓ JS total: 392.1KB (budget: 500KB)
✓ CSS total: 47.6KB (budget: 100KB)
✓ Total: 439.7KB (budget: 1000KB)

✅ All bundles within budget

```

### smoke

```
🔥 Running smoke tests...

Starting API server on port 8422...
✅ startup: 0.641s / 10.000s - Server healthy

✅ health: 0.014s / 0.500s
✅ typical_query: 0.033s / 2.000s - /api/control-room/proposals responded
✅ db_cycle: 0.012s / 1.000s - DB health check passed

📊 Results: 3/3 passed

✅ All smoke tests passed

```

### scenarios

```
============================= test session starts ==============================
platform darwin -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0 -- /Users/molhamhomsi/clawd/moh_time_os/.venv/bin/python3
cachedir: .pytest_cache
hypothesis profile 'default'
rootdir: /Users/molhamhomsi/clawd/moh_time_os
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: anyio-4.12.1, hypothesis-6.151.5, cov-7.0.0
collecting ... collected 5 items

tests/scenarios/test_client_health_scenario.py::TestClientHealthScenario::test_healthy_client_path PASSED [ 20%]
tests/scenarios/test_client_health_scenario.py::TestClientHealthScenario::test_at_risk_client_path PASSED [ 40%]
tests/scenarios/test_client_health_scenario.py::TestProposalScenario::test_proposal_creation_path PASSED [ 60%]
tests/scenarios/test_client_health_scenario.py::TestIssueLifecycleScenario::test_issue_tagged_from_proposal PASSED [ 80%]
tests/scenarios/test_client_health_scenario.py::TestIssueLifecycleScenario::t
```
