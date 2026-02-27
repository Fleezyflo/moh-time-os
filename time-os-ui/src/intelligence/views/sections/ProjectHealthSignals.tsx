/**
 * ProjectHealthSignals — Active signals affecting project health
 */

import { ProfileSection } from '../../components/ProfileSection';
import { SignalCard } from '../../components/SignalCard';
import { HealthScore } from '../../components/HealthScore';
import type { ProjectOperationalState, Signal } from '../../api';

interface ProjectHealthSignalsProps {
  project: ProjectOperationalState;
  signals?: Signal[];
}

export function ProjectHealthSignals({ project, signals = [] }: ProjectHealthSignalsProps) {
  const healthScore = project.health_score;
  const signalCount = signals.length;

  return (
    <ProfileSection
      title="Health Signals"
      description="Active signals affecting this project's health score."
      badge={
        signalCount > 0 ? (
          <span className="text-xs text-amber-400">{signalCount} active</span>
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-6 items-start">
        {/* Health score display */}
        <div className="flex flex-col items-center">
          {healthScore != null ? (
            <HealthScore score={healthScore} label="Project Health" size="lg" />
          ) : (
            <div className="text-[var(--grey-muted)] text-sm italic">No score available</div>
          )}
        </div>

        {/* Signals list */}
        <div>
          {signalCount > 0 ? (
            <div className="space-y-2">
              {signals.slice(0, 5).map((signal, i) => (
                <SignalCard key={signal.signal_id || i} signal={signal} compact />
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
