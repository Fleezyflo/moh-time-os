/**
 * ClientDistributionChart -- Tier and health breakdown visualization.
 *
 * Shows client distribution by tier (A/B/C) with AR totals and at-risk counts.
 * Data comes from usePortfolioOverview() hook.
 */

interface TierData {
  tier: string;
  count: number;
  total_ar: number;
  at_risk: number;
}

interface HealthData {
  health: string;
  count: number;
}

interface ClientDistributionChartProps {
  byTier: TierData[];
  byHealth: HealthData[];
}

const TIER_COLORS: Record<string, string> = {
  A: 'bg-blue-500',
  B: 'bg-blue-400',
  C: 'bg-blue-300',
};

const HEALTH_COLORS: Record<string, string> = {
  excellent: 'bg-green-500',
  good: 'bg-green-400',
  fair: 'bg-amber-400',
  poor: 'bg-orange-500',
  critical: 'bg-red-500',
};

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function ClientDistributionChart({ byTier, byHealth }: ClientDistributionChartProps) {
  const totalClients = byTier.reduce((sum, t) => sum + t.count, 0);
  const totalHealthClients = byHealth.reduce((sum, h) => sum + h.count, 0);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Tier breakdown */}
      <div>
        <h4 className="text-sm font-medium text-[var(--grey-light)] mb-3">By Tier</h4>
        <div className="space-y-3">
          {byTier.map((tier) => {
            const pct = totalClients > 0 ? (tier.count / totalClients) * 100 : 0;
            return (
              <div key={tier.tier}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-[var(--white)] font-medium">Tier {tier.tier}</span>
                  <span className="text-[var(--grey-light)]">{tier.count} clients</span>
                </div>
                <div className="h-2 bg-[var(--grey)] rounded-full overflow-hidden">
                  <div
                    className={`h-full ${TIER_COLORS[tier.tier] || 'bg-blue-300'} rounded-full`}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-[var(--grey-muted)]">
                  <span>AR: {formatCurrency(tier.total_ar || 0)}</span>
                  {tier.at_risk > 0 && <span className="text-red-400">{tier.at_risk} at risk</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Health breakdown */}
      <div>
        <h4 className="text-sm font-medium text-[var(--grey-light)] mb-3">By Health</h4>
        <div className="space-y-3">
          {byHealth.map((h) => {
            const pct = totalHealthClients > 0 ? (h.count / totalHealthClients) * 100 : 0;
            return (
              <div key={h.health}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-[var(--white)] capitalize">{h.health}</span>
                  <span className="text-[var(--grey-light)]">{h.count}</span>
                </div>
                <div className="h-2 bg-[var(--grey)] rounded-full overflow-hidden">
                  <div
                    className={`h-full ${HEALTH_COLORS[h.health] || 'bg-[var(--grey-muted)]'} rounded-full`}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
