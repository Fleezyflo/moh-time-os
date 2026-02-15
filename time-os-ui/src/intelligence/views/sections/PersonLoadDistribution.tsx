/**
 * PersonLoadDistribution — Work allocation across projects
 *
 * Uses PersonProfile.projects[] from /team/{id}/profile endpoint
 */

import { ProfileSection } from '../../components/ProfileSection';
import { DistributionChart } from '../../components/DistributionChart';
import { SeverityBadge } from '../../components/Badges';
import type { PersonProfile } from '../../api';

interface PersonLoadDistributionProps {
  profile: PersonProfile | null;
}

export function PersonLoadDistribution({ profile }: PersonLoadDistributionProps) {
  if (!profile || !profile.projects || profile.projects.length === 0) {
    return (
      <ProfileSection title="Load Distribution" description="Work allocation across projects.">
        <div className="text-sm text-slate-500 italic">No project assignments found</div>
      </ProfileSection>
    );
  }

  const projects = profile.projects;
  const totalTasks = projects.reduce((sum, p) => sum + (p.tasks_on_project || 0), 0);

  // Sort by task count descending
  const sorted = [...projects].sort(
    (a, b) => (b.tasks_on_project || 0) - (a.tasks_on_project || 0)
  );

  // Calculate concentration (top project as % of total)
  const topProjectTasks = sorted[0]?.tasks_on_project || 0;
  const concentrationPct = totalTasks > 0 ? (topProjectTasks / totalTasks) * 100 : 0;
  const highConcentration = concentrationPct > 60;

  // Create segments for distribution chart
  const segments = sorted.map((p) => ({
    label: `${p.project_name} (${p.client_name})`,
    value: p.tasks_on_project || 0,
  }));

  return (
    <ProfileSection
      title="Load Distribution"
      description="Work allocation across projects."
      badge={highConcentration ? <SeverityBadge severity="warning" /> : undefined}
    >
      <DistributionChart segments={segments} height={32} />

      {highConcentration && (
        <div className="mt-3 px-3 py-2 bg-amber-500/10 rounded text-sm text-amber-400">
          Concentration risk: {Math.round(concentrationPct)}% of work on one project
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2">
        {sorted.slice(0, 5).map((p, i) => {
          const sharePct = totalTasks > 0 ? (p.tasks_on_project / totalTasks) * 100 : 0;
          return (
            <div
              key={p.project_id || i}
              className="grid grid-cols-[1fr_100px_50px_50px] gap-2 items-center py-2 border-b border-slate-700/50 last:border-0 text-sm"
            >
              <span className="text-white truncate">{p.project_name}</span>
              <span className="text-slate-500 truncate">{p.client_name}</span>
              <span className="text-slate-400 text-right">{p.tasks_on_project}</span>
              <span className="text-slate-300 font-medium text-right">{Math.round(sharePct)}%</span>
            </div>
          );
        })}
      </div>
    </ProfileSection>
  );
}
