/**
 * ClientIntel — Client Intelligence Deep Dive using ProfileShell
 * 
 * Shows what the API actually returns:
 * - Header with score, classification, quick stats
 * - Health breakdown (per-dimension scores + active signals)
 * - Connected entities (persons, projects, invoices)
 */

import { useParams } from '@tanstack/react-router';
import { useClientIntelligence, useClientProfile } from '../hooks';
import { ProfileShell } from '../components/ProfileShell';
import { ClientHealthBreakdown } from '../views/sections';
import { classifyScore } from '../utils/formatters';
import type { ClientIntelligence, ClientProfile } from '../api';

/**
 * Combined client data from intelligence + profile endpoints
 */
interface ClientFullData extends ClientIntelligence {
  profile?: ClientProfile | null;
}

export default function ClientIntel() {
  const { clientId } = useParams({ strict: false });
  const { data: intel, loading: intelLoading, error: intelError, refetch: refetchIntel } = useClientIntelligence(clientId || '');
  const { data: profile, loading: profileLoading, error: profileError, refetch: refetchProfile } = useClientProfile(clientId || '');

  if (!clientId) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
          <div className="text-red-400">No client ID provided</div>
        </div>
      </div>
    );
  }

  const combinedData: ClientFullData | null = intel ? { ...intel, profile } : null;
  const loading = intelLoading || profileLoading;
  const error = intelError || profileError;
  const refetch = () => {
    refetchIntel();
    refetchProfile();
  };

  return (
    <ProfileShell
      entityType="client"
      data={combinedData}
      loading={loading}
      error={error}
      onRefresh={refetch}
      mapToHeader={mapClientToHeader}
      mapToConnected={mapClientToConnected}
      renderSections={(data) => (
        <ClientHealthBreakdown client={data} />
      )}
    />
  );
}

/**
 * Map combined client data to ProfileHeader props.
 */
function mapClientToHeader(data: ClientFullData) {
  const scorecard = data.scorecard;
  const profile = data.profile;
  const compositeScore = scorecard?.composite_score;
  
  const primarySignal = data.active_signals && data.active_signals.length > 0
    ? {
        severity: data.active_signals[0].severity as 'critical' | 'warning' | 'watch',
        headline: data.active_signals[0].name || data.active_signals[0].evidence || 'Active signal detected',
      }
    : null;

  return {
    name: scorecard?.entity_name || profile?.client_name || data.client_id,
    score: compositeScore,
    classification: classifyScore(compositeScore),
    primarySignal,
    quickStats: {
      'Health': compositeScore ? `${Math.round(compositeScore)}` : '—',
      'Signals': data.active_signals?.length ?? 0,
      'Projects': profile?.project_count ?? '—',
      'Tasks': profile?.total_tasks ?? '—',
    },
    trend: null,
  };
}

/**
 * Map combined client data to ConnectedEntities props.
 */
function mapClientToConnected(data: ClientFullData) {
  const profile = data.profile;
  if (!profile) {
    return { persons: null, projects: null, clients: null, invoices: null };
  }

  return {
    persons: profile.people_involved?.map(p => ({
      person_id: p.person_id,
      name: p.person_name,
      role: p.role,
      task_count: p.tasks_for_client,
    })) || null,
    projects: profile.projects?.map(p => ({
      project_id: p.project_id,
      name: p.project_name,
      task_count: p.total_tasks,
      health_score: p.completion_rate_pct,
    })) || null,
    clients: null,
    invoices: profile.recent_invoices?.map(inv => ({
      invoice_id: inv.invoice_id,
      amount: inv.amount,
      status: inv.invoice_status,
      date: inv.issue_date,
    })) || null,
  };
}
