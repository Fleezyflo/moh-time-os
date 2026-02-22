# TASK: Auto-Calculate Client Tiers from Revenue Data
> Brief: DATA_FOUNDATION | Phase: 1 | Sequence: 1.3 | Status: PENDING

## Context

156 of 160 clients have no tier assigned (only 4 are A/B). The tier field is fundamental to the system's prioritization logic — signals, inbox items, and the operator queue all reference client tier for routing. Meanwhile, the `invoices` table has 1,257 invoices totaling 32M+ AED with proper client linkage. The data to calculate tiers already exists.

Current tier distribution: A=2, B=2, NULL=156.

Revenue data: `invoices.amount` summed by `client_id` where `status = 'paid'`.

Existing columns on `clients`: `tier` (CHECK A/B/C), `financial_ar_total`, `financial_annual_value`, `lifetime_revenue`, `ytd_revenue`, `prior_year_revenue`.

## Objective

Create a tier calculation function that assigns A/B/C tiers based on lifetime revenue and writes them to the `clients` table. Also populate `lifetime_revenue`, `ytd_revenue`, and `prior_year_revenue` fields.

## Instructions

1. Read `lib/client_truth/` to understand existing client health logic.
2. Create `lib/client_truth/tier_calculator.py` with:
   - `calculate_client_revenue_stats(db_path) -> dict[str, dict]` — queries invoices to compute lifetime_revenue, ytd_revenue, prior_year_revenue per client.
   - `assign_tiers(revenue_stats) -> dict[str, str]` — applies tiering rules:
     - **Tier A:** Top 20% by lifetime revenue OR lifetime revenue > 1M AED
     - **Tier B:** Next 30% by lifetime revenue OR lifetime revenue > 200K AED
     - **Tier C:** Everyone else with any revenue
     - **NULL:** Clients with zero invoiced revenue (keep untiered)
   - `update_client_tiers(db_path)` — runs both functions and writes results to `clients` table.
3. Add CLI command to `cli.py` or `cli_v4.py`: `timeos tier-update` that calls `update_client_tiers`.
4. Write tests in `tests/test_tier_calculator.py`:
   - Test tier assignment logic with mock data
   - Test revenue stat calculation
   - Test that NULL-revenue clients stay untiered
5. Run: `pytest tests/ -q`

## Preconditions
- [ ] Test suite passing
- [ ] `lib/client_truth/` directory exists

## Validation
1. `python -c "from lib.client_truth.tier_calculator import update_client_tiers"` succeeds
2. `pytest tests/test_tier_calculator.py -v` passes
3. `pytest tests/ -q` all pass
4. Tier logic matches spec: A=top 20% or >1M, B=next 30% or >200K, C=rest with revenue

## Acceptance Criteria
- [ ] `tier_calculator.py` exists in `lib/client_truth/`
- [ ] Tier calculation uses revenue data from invoices
- [ ] `lifetime_revenue`, `ytd_revenue`, `prior_year_revenue` are computed and written
- [ ] CLI command `tier-update` is available
- [ ] Tests cover tier boundary conditions
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- New: `lib/client_truth/tier_calculator.py`
- New: `tests/test_tier_calculator.py`
- Modified: CLI file (add `tier-update` command)

## On Completion
- Update HEARTBEAT: Task DF-1.3 complete — Client tier auto-calculation from revenue data
- Record: new module, test count delta

## On Failure
- If tier thresholds need Moh's input, propose defaults and document in Blocked with the distribution preview
