/**
 * ARAgingSummary -- Accounts receivable aging overview.
 *
 * Shows total AR, overdue AR, and the at-risk client breakdown
 * from the portfolio overview data. Rendered on the Portfolio page.
 */

interface ARAgingSummaryProps {
  totalAR: number;
  overdueCount: number;
  overdueTotal: number;
  totalAnnualValue: number;
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function ARAgingSummary({
  totalAR,
  overdueCount,
  overdueTotal,
  totalAnnualValue,
}: ARAgingSummaryProps) {
  const overduePercent = totalAR > 0 ? (overdueTotal / totalAR) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Main stats row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-3 bg-[var(--grey-dim)] rounded-lg text-center">
          <div className="text-2xl font-bold text-[var(--white)]">{formatCurrency(totalAR)}</div>
          <div className="text-xs text-[var(--grey-muted)] mt-1">Total AR</div>
        </div>
        <div className="p-3 bg-[var(--grey-dim)] rounded-lg text-center">
          <div
            className={`text-2xl font-bold ${overdueTotal > 0 ? 'text-red-400' : 'text-green-400'}`}
          >
            {formatCurrency(overdueTotal)}
          </div>
          <div className="text-xs text-[var(--grey-muted)] mt-1">
            Overdue ({overdueCount} clients)
          </div>
        </div>
        <div className="p-3 bg-[var(--grey-dim)] rounded-lg text-center">
          <div className="text-2xl font-bold text-[var(--white)]">
            {formatCurrency(totalAnnualValue)}
          </div>
          <div className="text-xs text-[var(--grey-muted)] mt-1">Annual Value</div>
        </div>
      </div>

      {/* Overdue bar */}
      {totalAR > 0 && (
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-[var(--grey-light)]">Overdue proportion</span>
            <span className={overduePercent > 20 ? 'text-red-400' : 'text-[var(--grey-light)]'}>
              {overduePercent.toFixed(1)}%
            </span>
          </div>
          <div className="h-2 bg-[var(--grey)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${overduePercent > 20 ? 'bg-red-500' : 'bg-amber-400'}`}
              style={{ width: `${Math.min(100, overduePercent)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
