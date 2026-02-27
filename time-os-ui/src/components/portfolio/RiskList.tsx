/**
 * RiskList -- Renders at-risk clients with health scores and trends.
 *
 * Used on the Portfolio page to surface clients below the health threshold.
 * Data comes from usePortfolioRisks() hook.
 */

import type { AtRiskClient } from '../../lib/api';

interface RiskListProps {
  clients: AtRiskClient[];
  maxItems?: number;
}

function healthColor(score: number): string {
  if (score >= 60) return 'text-green-400';
  if (score >= 30) return 'text-amber-400';
  return 'text-red-400';
}

function trendIndicator(trend?: string): string {
  if (!trend) return '';
  if (trend === 'improving') return ' improving';
  if (trend === 'declining') return ' declining';
  return ' ' + trend;
}

export function RiskList({ clients, maxItems = 10 }: RiskListProps) {
  const displayed = clients.slice(0, maxItems);

  if (displayed.length === 0) {
    return <div className="text-center py-8 text-[var(--grey-light)]">No at-risk clients</div>;
  }

  return (
    <div className="space-y-2">
      {displayed.map((client) => (
        <div
          key={client.client_id}
          className="flex items-center justify-between p-3 bg-[var(--grey-dim)] rounded-lg hover:bg-[var(--grey)] transition-colors"
        >
          <div className="flex-1 min-w-0">
            <span className="font-medium text-[var(--white)] truncate block">{client.name}</span>
            {client.trend && (
              <span className="text-xs text-[var(--grey-muted)]">
                Trend:{trendIndicator(client.trend)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className={`text-lg font-bold ${healthColor(client.health_score)}`}>
              {Math.round(client.health_score)}
            </span>
            <span className="text-xs text-[var(--grey-muted)]">health</span>
          </div>
        </div>
      ))}
      {clients.length > maxItems && (
        <div className="text-center text-sm text-[var(--grey-muted)]">
          +{clients.length - maxItems} more at-risk clients
        </div>
      )}
    </div>
  );
}
