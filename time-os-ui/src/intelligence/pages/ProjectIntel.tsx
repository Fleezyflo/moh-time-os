/**
 * ProjectIntel — Project Intelligence Deep Dive using ProfileShell
 *
 * Shows what the API actually returns:
 * - Header with health score, completion rate, quick stats
 * - Operational state (task metrics)
 * - Health signals
 * - Connected entities (client)
 */

import { useParams } from '@tanstack/react-router';
import { useProjectDetail, useActiveSignals } from '../hooks';
import { ProfileShell } from '../components/ProfileShell';
import { ProjectOperationalState, ProjectHealthSignals } from '../views/sections';
import { classifyScore } from '../utils/formatters';
import type { ProjectOperationalState as ProjectState, Signal } from '../api';

/**
 * Combined project data from operational state + signals
 */
interface ProjectFullData extends ProjectState {
  signals?: Signal[];
}

export default function ProjectIntel() {
  const { projectId } = useParams({ strict: false });
  const id = projectId || '';

  const {
    data: project,
    loading: projectLoading,
    error: projectError,
    refetch: refetchProject,
  } = useProjectDetail(id);
  const {
    data: signals,
    loading: signalsLoading,
    refetch: refetchSignals,
  } = useActiveSignals('project', id);

  if (!id) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
          <div className="text-red-400">No project ID provided</div>
        </div>
      </div>
    );
  }

  const combinedData: ProjectFullData | null = project
    ? { ...project, signals: signals || [] }
    : null;
  const loading = projectLoading || signalsLoading;
  const error = projectError;
  const refetch = () => {
    refetchProject();
    refetchSignals();
  };

  return (
    <ProfileShell
      entityType="project"
      data={combinedData}
      loading={loading}
      error={error}
      onRefresh={refetch}
      mapToHeader={mapProjectToHeader}
      mapToConnected={mapProjectToConnected}
      renderSections={(data) => (
        <>
          <ProjectOperationalState project={data} />
          <ProjectHealthSignals project={data} signals={data.signals} />
        </>
      )}
    />
  );
}

/**
 * Map project data to ProfileHeader props.
 */
function mapProjectToHeader(data: ProjectFullData) {
  const healthScore = data.health_score;
  const completionRate = data.completion_rate_pct || 0;
  const overdueTasks = data.overdue_tasks || 0;

  const primarySignal =
    data.signals && data.signals.length > 0
      ? {
          severity: data.signals[0].severity as 'critical' | 'warning' | 'watch',
          headline: data.signals[0].name || data.signals[0].evidence || 'Active signal detected',
        }
      : overdueTasks > 0
        ? {
            severity: 'warning' as const,
            headline: `${overdueTasks} overdue task${overdueTasks > 1 ? 's' : ''}`,
          }
        : null;

  return {
    name: data.project_name || data.project_id,
    score: healthScore,
    classification: classifyScore(healthScore),
    primarySignal,
    quickStats: {
      Health: healthScore != null ? `${Math.round(healthScore)}` : '—',
      Tasks: data.total_tasks ?? '—',
      Complete: `${Math.round(completionRate)}%`,
      Overdue: overdueTasks,
      Team: data.assigned_people ?? '—',
    },
    trend: null,
  };
}

/**
 * Map project data to ConnectedEntities props.
 */
function mapProjectToConnected(data: ProjectFullData) {
  return {
    persons: null,
    projects: null,
    clients: data.client_id
      ? [
          {
            client_id: data.client_id,
            name: data.client_name || 'Unknown Client',
          },
        ]
      : null,
    invoices: null,
  };
}
