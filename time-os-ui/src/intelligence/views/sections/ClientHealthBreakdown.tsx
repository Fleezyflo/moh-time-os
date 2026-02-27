/**
 * ClientHealthBreakdown — Per-dimension health scores + active signals
 */

import { ProfileSection } from '../../components/ProfileSection';
import { BreakdownChart } from '../../components/BreakdownChart';
import { SignalCard } from '../../components/SignalCard';
import { formatDimensionLabel } from '../../utils/formatters';
import type { ClientIntelligence } from '../../api';

interface ClientHealthBreakdownProps {
  client: ClientIntelligence;
}

type DimensionStatus = 'critical' | 'warning' | 'watch' | 'healthy' | 'strong';

function scoreToStatus(score: number): DimensionStatus {
  if (score <= 30) return 'critical';
  if (score <= 50) return 'warning';
  if (score <= 60) return 'watch';
  if (score <= 80) return 'healthy';
  return 'strong';
}

export function ClientHealthBreakdown({ client }: ClientHealthBreakdownProps) {
  // Map dimensions from scorecard to array for BreakdownChart
  const dimensions = Object.entries(client.scorecard?.dimensions || {}).map(([key, dim]) => ({
    label: formatDimensionLabel(key),
    value: dim.score,
    threshold: 60, // default threshold
    status: scoreToStatus(dim.score),
  }));

  const signalCount = client.active_signals?.length || 0;

  return (
    <ProfileSection
      title="Health Breakdown"
      description="Score by operational dimension. Bars sorted worst-first."
      badge={
        signalCount > 0 ? (
          <span className="text-xs text-amber-400">{signalCount} active</span>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6 items-start">
        {/* Dimension breakdown chart */}
        <div>
          <BreakdownChart
            dimensions={dimensions}
            compositeScore={client.scorecard?.composite_score}
          />
        </div>

        {/* Active signals */}
        <div>
          <h4 className="text-sm font-semibold text-[var(--grey-light)] mb-3">Active Signals</h4>
          {signalCount > 0 ? (
            <div className="space-y-2">
              {client.active_signals?.slice(0, 5).map((signal, i) => (
                <SignalCard key={signal.signal_id || i} signal={signal} />
              ))}
              {signalCount > 5 && (
                <div className="text-xs text-[var(--grey-muted)] text-center py-2">
                  +{signalCount - 5} more signals
                </div>
              )}
            </div>
          ) : (
            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 text-center">
              <div className="text-green-400 text-sm">✓ No active signals</div>
            </div>
          )}
        </div>
      </div>
    </ProfileSection>
  );
}
