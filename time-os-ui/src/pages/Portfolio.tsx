/**
 * Portfolio Page -- Portfolio-level view of all clients, health, and intelligence.
 *
 * Phase 3.1 of BUILD_PLAN.md. Combines:
 * - Portfolio score (intelligence) via usePortfolioScore()
 * - Critical items via useCriticalItems()
 * - Portfolio intelligence via usePortfolioIntelligence()
 * - Portfolio overview (tier/health/AR) via usePortfolioOverview()
 * - At-risk clients via usePortfolioRisks()
 * - Proposal cards via usePortfolioIntelligence().top_proposals
 */

import { PageLayout } from '../components/layout/PageLayout';
import * as api from '../lib/api';
import { SummaryGrid } from '../components/layout/SummaryGrid';
import { MetricCard } from '../components/layout/MetricCard';
import { CriticalItemList } from '../components/portfolio/CriticalItemList';
import { ClientDistributionChart } from '../components/portfolio/ClientDistributionChart';
import { RiskList } from '../components/portfolio/RiskList';
import { ARAgingSummary } from '../components/portfolio/ARAgingSummary';
import { Scorecard } from '../intelligence/components/Scorecard';
import {
  usePortfolioScore,
  useCriticalItems,
  usePortfolioIntelligence,
} from '../intelligence/hooks';
import {
  usePortfolioOverview,
  usePortfolioRisks,
  useFinancialDetail,
  useAsanaPortfolioContext,
} from '../lib/hooks';

export function Portfolio() {
  const portfolioScore = usePortfolioScore();
  const criticalItems = useCriticalItems();
  const portfolioIntel = usePortfolioIntelligence();
  const portfolioOverview = usePortfolioOverview();
  const portfolioRisks = usePortfolioRisks(50);
  const financialDetail = useFinancialDetail();
  const asanaContext = useAsanaPortfolioContext();

  // Derive signal count and structural pattern count from intelligence data
  const signalCount = portfolioIntel.data?.signal_summary?.total_active ?? 0;
  const structuralPatterns =
    portfolioIntel.data?.structural_patterns?.filter((p) => p.severity === 'structural') ?? [];

  const isLoading =
    portfolioScore.loading ||
    criticalItems.loading ||
    portfolioIntel.loading ||
    portfolioOverview.loading;

  const hasError =
    portfolioScore.error || criticalItems.error || portfolioIntel.error || portfolioOverview.error;

  return (
    <PageLayout title="Portfolio">
      {/* Summary metrics */}
      <SummaryGrid>
        <MetricCard
          label="Health Score"
          value={portfolioScore.data ? Math.round(portfolioScore.data.composite_score) : '--'}
          severity={
            portfolioScore.data
              ? portfolioScore.data.composite_score >= 60
                ? 'success'
                : portfolioScore.data.composite_score >= 30
                  ? 'warning'
                  : 'danger'
              : undefined
          }
        />
        <MetricCard
          label="Critical Items"
          value={criticalItems.data?.length ?? '--'}
          severity={(criticalItems.data?.length ?? 0) > 0 ? 'danger' : undefined}
        />
        <MetricCard
          label="Active Signals"
          value={signalCount || '--'}
          severity={signalCount > 5 ? 'warning' : undefined}
        />
        <MetricCard label="Structural Patterns" value={structuralPatterns.length || '--'} />
      </SummaryGrid>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="animate-pulse text-[var(--grey-light)]">Loading portfolio data...</div>
        </div>
      )}

      {/* Error state */}
      {hasError && !isLoading && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <div className="text-red-400 font-medium">Failed to load some portfolio data</div>
          <div className="text-sm text-[var(--grey-light)] mt-1">
            {portfolioScore.error?.message ||
              criticalItems.error?.message ||
              portfolioIntel.error?.message ||
              portfolioOverview.error?.message}
          </div>
          <button
            onClick={() => {
              portfolioScore.refetch();
              criticalItems.refetch();
              portfolioIntel.refetch();
              portfolioOverview.refetch();
              portfolioRisks.refetch();
            }}
            className="mt-2 px-3 py-1 bg-red-500/20 rounded text-sm text-red-300 hover:bg-red-500/30"
          >
            Retry
          </button>
        </div>
      )}

      {/* Main content -- only show when not loading */}
      {!isLoading && (
        <div className="space-y-8">
          {/* Top Risks */}
          {criticalItems.data && criticalItems.data.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">Top Risks</h2>
              <CriticalItemList items={criticalItems.data} maxItems={5} />
            </section>
          )}

          {/* Portfolio Health (Scorecard breakdown) */}
          {portfolioScore.data && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">Portfolio Health</h2>
              <Scorecard scorecard={portfolioScore.data} />
            </section>
          )}

          {/* Client Distribution */}
          {portfolioOverview.data && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">
                Client Distribution
              </h2>
              <ClientDistributionChart
                byTier={portfolioOverview.data.by_tier}
                byHealth={portfolioOverview.data.by_health}
              />
            </section>
          )}

          {/* At-Risk Clients */}
          {portfolioRisks.data && portfolioRisks.data.clients.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">
                At-Risk Clients
                <span className="ml-2 text-sm font-normal text-[var(--grey-muted)]">
                  (health &lt; {portfolioRisks.data.threshold})
                </span>
              </h2>
              <RiskList clients={portfolioRisks.data.clients} maxItems={10} />
            </section>
          )}

          {/* AR Aging Summary */}
          {portfolioOverview.data && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">Financial Overview</h2>
              <ARAgingSummary
                totalAR={portfolioOverview.data.totals?.total_ar ?? 0}
                overdueCount={portfolioOverview.data.overdue_ar?.count ?? 0}
                overdueTotal={portfolioOverview.data.overdue_ar?.total ?? 0}
                totalAnnualValue={portfolioOverview.data.totals?.total_annual_value ?? 0}
              />
            </section>
          )}

          {/* Top Proposals from intelligence */}
          {portfolioIntel.data?.top_proposals && portfolioIntel.data.top_proposals.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-[var(--white)] mb-4">Top Proposals</h2>
              <div className="space-y-2">
                {portfolioIntel.data.top_proposals.map((p, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-[var(--grey-dim)] rounded-lg"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-[var(--white)] truncate block">{p.headline}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          p.urgency === 'immediate'
                            ? 'bg-red-500/20 text-red-300'
                            : p.urgency === 'this_week'
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-[var(--grey)] text-[var(--grey-light)]'
                        }`}
                      >
                        {p.urgency}
                      </span>
                      <span className="text-sm font-medium text-[var(--grey-light)]">
                        {Math.round(p.score)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Financial Detail Section */}
          <section>
            <details className="group">
              <summary className="cursor-pointer py-3 text-lg font-semibold text-[var(--white)] hover:text-[var(--grey-light)] transition">
                Financial Detail
                {financialDetail.data?.contacts && (
                  <span className="text-sm text-[var(--grey-muted)] ml-2">
                    ({financialDetail.data.contacts.length})
                  </span>
                )}
              </summary>
              <div className="mt-4 space-y-6">
                {!financialDetail.data ||
                (!financialDetail.data.contacts &&
                  !financialDetail.data.transactions &&
                  !financialDetail.data.tax_rates) ? (
                  <div className="p-4 text-center">
                    <p className="text-[var(--grey-light)]">
                      No financial detail available. Run the Xero collector to populate.
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Contacts */}
                    {financialDetail.data.contacts && financialDetail.data.contacts.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3">
                          Contacts
                        </h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm border-collapse">
                            <thead>
                              <tr className="border-b border-[var(--grey)]">
                                <th className="text-left p-2 text-[var(--grey-light)]">Name</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Email</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Type</th>
                                <th className="text-right p-2 text-[var(--grey-light)]">
                                  Outstanding
                                </th>
                                <th className="text-right p-2 text-[var(--grey-light)]">Overdue</th>
                              </tr>
                            </thead>
                            <tbody>
                              {financialDetail.data.contacts.map(
                                (contact: api.XeroContact, idx: number) => (
                                  <tr
                                    key={idx}
                                    className="border-b border-[var(--grey)]/30 hover:bg-[var(--grey-dim)]"
                                  >
                                    <td className="p-2 text-[var(--white)]">
                                      {contact.name || '--'}
                                    </td>
                                    <td className="p-2 text-[var(--grey-light)]">
                                      {contact.email || '--'}
                                    </td>
                                    <td className="p-2 text-[var(--grey-light)]">
                                      {contact.is_supplier && contact.is_customer
                                        ? 'Both'
                                        : contact.is_supplier
                                          ? 'Supplier'
                                          : contact.is_customer
                                            ? 'Customer'
                                            : '--'}
                                    </td>
                                    <td className="text-right p-2 text-[var(--grey-light)]">
                                      ${(contact.outstanding_balance || 0).toFixed(2)}
                                    </td>
                                    <td className="text-right p-2 text-[var(--grey-light)]">
                                      ${(contact.overdue_balance || 0).toFixed(2)}
                                    </td>
                                  </tr>
                                )
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Transactions */}
                    {financialDetail.data.transactions &&
                      financialDetail.data.transactions.length > 0 && (
                        <div>
                          <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3">
                            Transactions (Latest 50)
                          </h3>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm border-collapse">
                              <thead>
                                <tr className="border-b border-[var(--grey)]">
                                  <th className="text-left p-2 text-[var(--grey-light)]">Date</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">Type</th>
                                  <th className="text-right p-2 text-[var(--grey-light)]">Total</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">Status</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">
                                    Reference
                                  </th>
                                </tr>
                              </thead>
                              <tbody>
                                {financialDetail.data.transactions.map(
                                  (txn: api.BankTransaction, idx: number) => (
                                    <tr
                                      key={idx}
                                      className="border-b border-[var(--grey)]/30 hover:bg-[var(--grey-dim)]"
                                    >
                                      <td className="p-2 text-[var(--white)]">
                                        {txn.date || '--'}
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)]">
                                        {txn.type || '--'}
                                      </td>
                                      <td className="text-right p-2 text-[var(--grey-light)]">
                                        ${(txn.total || 0).toFixed(2)}
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)]">
                                        {txn.status || '--'}
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)] truncate">
                                        {txn.reference || '--'}
                                      </td>
                                    </tr>
                                  )
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                    {/* Tax Rates */}
                    {financialDetail.data.tax_rates &&
                      financialDetail.data.tax_rates.length > 0 && (
                        <div>
                          <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3">
                            Tax Rates
                          </h3>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm border-collapse">
                              <thead>
                                <tr className="border-b border-[var(--grey)]">
                                  <th className="text-left p-2 text-[var(--grey-light)]">Name</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">Type</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">Rate</th>
                                  <th className="text-left p-2 text-[var(--grey-light)]">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {financialDetail.data.tax_rates.map(
                                  (tax: api.TaxRate, idx: number) => (
                                    <tr
                                      key={idx}
                                      className="border-b border-[var(--grey)]/30 hover:bg-[var(--grey-dim)]"
                                    >
                                      <td className="p-2 text-[var(--white)]">
                                        {tax.name || '--'}
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)]">
                                        {tax.tax_type || '--'}
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)]">
                                        {((tax.effective_rate ?? 0) * 100).toFixed(2)}%
                                      </td>
                                      <td className="p-2 text-[var(--grey-light)]">
                                        {tax.status || '--'}
                                      </td>
                                    </tr>
                                  )
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                  </>
                )}
              </div>
            </details>
          </section>

          {/* Asana Context Section */}
          <section>
            <details className="group">
              <summary className="cursor-pointer py-3 text-lg font-semibold text-[var(--white)] hover:text-[var(--grey-light)] transition">
                Asana Context
                {asanaContext.data && (
                  <span className="text-sm text-[var(--grey-muted)] ml-2">
                    (
                    {(asanaContext.data.portfolios?.length || 0) +
                      (asanaContext.data.goals?.length || 0)}
                    )
                  </span>
                )}
              </summary>
              <div className="mt-4 space-y-6">
                {!asanaContext.data ||
                (!asanaContext.data.portfolios && !asanaContext.data.goals) ? (
                  <div className="p-4 text-center">
                    <p className="text-[var(--grey-light)]">
                      No Asana context available. Run the Asana collector to populate.
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Portfolios */}
                    {asanaContext.data.portfolios && asanaContext.data.portfolios.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3">
                          Portfolios
                        </h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm border-collapse">
                            <thead>
                              <tr className="border-b border-[var(--grey)]">
                                <th className="text-left p-2 text-[var(--grey-light)]">Name</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Owner</th>
                              </tr>
                            </thead>
                            <tbody>
                              {asanaContext.data.portfolios.map(
                                (portfolio: api.AsanaPortfolio, idx: number) => (
                                  <tr
                                    key={idx}
                                    className="border-b border-[var(--grey)]/30 hover:bg-[var(--grey-dim)]"
                                  >
                                    <td className="p-2 text-[var(--white)]">
                                      {portfolio.name || '--'}
                                    </td>
                                    <td className="p-2 text-[var(--grey-light)]">
                                      {portfolio.owner_name || '--'}
                                    </td>
                                  </tr>
                                )
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Goals */}
                    {asanaContext.data.goals && asanaContext.data.goals.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-[var(--grey-light)] mb-3">Goals</h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm border-collapse">
                            <thead>
                              <tr className="border-b border-[var(--grey)]">
                                <th className="text-left p-2 text-[var(--grey-light)]">Name</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Owner</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Status</th>
                                <th className="text-left p-2 text-[var(--grey-light)]">Due On</th>
                              </tr>
                            </thead>
                            <tbody>
                              {asanaContext.data.goals.map((goal: api.AsanaGoal, idx: number) => (
                                <tr
                                  key={idx}
                                  className="border-b border-[var(--grey)]/30 hover:bg-[var(--grey-dim)]"
                                >
                                  <td className="p-2 text-[var(--white)]">{goal.name || '--'}</td>
                                  <td className="p-2 text-[var(--grey-light)]">
                                    {goal.owner_name || '--'}
                                  </td>
                                  <td className="p-2 text-[var(--grey-light)]">
                                    {goal.status || '--'}
                                  </td>
                                  <td className="p-2 text-[var(--grey-light)]">
                                    {goal.due_on || '--'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </details>
          </section>
        </div>
      )}
    </PageLayout>
  );
}

export default Portfolio;
