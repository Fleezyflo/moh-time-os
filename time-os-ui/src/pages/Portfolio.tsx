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
import { usePortfolioOverview, usePortfolioRisks } from '../lib/hooks';

export function Portfolio() {
  const portfolioScore = usePortfolioScore();
  const criticalItems = useCriticalItems();
  const portfolioIntel = usePortfolioIntelligence();
  const portfolioOverview = usePortfolioOverview();
  const portfolioRisks = usePortfolioRisks(50);

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
        </div>
      )}
    </PageLayout>
  );
}

export default Portfolio;
