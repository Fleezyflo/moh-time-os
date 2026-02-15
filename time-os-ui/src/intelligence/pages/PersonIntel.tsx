/**
 * PersonIntel — Person Intelligence Deep Dive using ProfileShell
 *
 * Shows what the API actually returns:
 * - Header with load info, quick stats
 * - Load distribution across projects (from PersonProfile)
 * - Active signals
 * - Connected entities (clients, projects)
 */

import { useParams } from '@tanstack/react-router';
import { usePersonIntelligence, usePersonProfile } from '../hooks';
import { ProfileShell } from '../components/ProfileShell';
import { PersonLoadDistribution } from '../views/sections';
import { SignalCard } from '../components';
import { ProfileSection } from '../components/ProfileSection';
import type { PersonIntelligence, PersonProfile } from '../api';

/**
 * Combined person data from intelligence + profile endpoints
 */
interface PersonFullData extends PersonIntelligence {
  operationalProfile?: PersonProfile | null;
}

export default function PersonIntel() {
  const { personId: paramId } = useParams({ strict: false });
  const personId = paramId || '';

  const {
    data: intel,
    loading: intelLoading,
    error: intelError,
    refetch: refetchIntel,
  } = usePersonIntelligence(personId);
  const {
    data: profile,
    loading: profileLoading,
    error: profileError,
    refetch: refetchProfile,
  } = usePersonProfile(personId);

  if (!personId) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
          <div className="text-red-400">No person ID provided</div>
        </div>
      </div>
    );
  }

  const combinedData: PersonFullData | null = intel
    ? { ...intel, operationalProfile: profile }
    : null;
  const loading = intelLoading || profileLoading;
  const error = intelError || profileError;
  const refetch = () => {
    refetchIntel();
    refetchProfile();
  };

  return (
    <ProfileShell
      entityType="person"
      data={combinedData}
      loading={loading}
      error={error}
      onRefresh={refetch}
      mapToHeader={mapPersonToHeader}
      mapToConnected={mapPersonToConnected}
      renderSections={(data) => (
        <>
          <PersonLoadDistribution profile={data.operationalProfile || null} />
          <PersonSignalsSection signals={data.active_signals || []} />
        </>
      )}
    />
  );
}

/**
 * Active signals section for person
 */
function PersonSignalsSection({ signals }: { signals: PersonIntelligence['active_signals'] }) {
  if (!signals || signals.length === 0) {
    return (
      <ProfileSection title="Active Signals" description="Current alerts for this person.">
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 text-center">
          <div className="text-green-400 text-sm">✓ No active signals</div>
        </div>
      </ProfileSection>
    );
  }

  return (
    <ProfileSection
      title="Active Signals"
      description="Current alerts for this person."
      badge={<span className="text-xs text-amber-400">{signals.length} active</span>}
    >
      <div className="space-y-2">
        {signals.slice(0, 5).map((signal, i) => (
          <SignalCard key={signal.signal_id || i} signal={signal} compact />
        ))}
      </div>
    </ProfileSection>
  );
}

/**
 * Map combined person data to ProfileHeader props.
 */
function mapPersonToHeader(data: PersonFullData) {
  const scorecard = data.scorecard;
  const profile = data.operationalProfile;

  const primarySignal =
    data.active_signals && data.active_signals.length > 0
      ? {
          severity: data.active_signals[0].severity as 'critical' | 'warning' | 'watch',
          headline:
            data.active_signals[0].name || data.active_signals[0].evidence || 'Active signal',
        }
      : null;

  return {
    name: scorecard?.entity_name || profile?.person_name || data.person_id,
    score: scorecard?.composite_score,
    classification: null,
    primarySignal,
    quickStats: {
      Tasks: profile?.active_tasks ?? '—',
      Projects: profile?.projects?.length ?? '—',
      Clients: profile?.clients?.length ?? '—',
      Signals: data.active_signals?.length ?? 0,
    },
    trend: null,
  };
}

/**
 * Map combined person data to ConnectedEntities props.
 */
function mapPersonToConnected(data: PersonFullData) {
  const profile = data.operationalProfile;
  if (!profile) {
    return { persons: null, projects: null, clients: null, invoices: null };
  }

  return {
    persons: null,
    projects:
      profile.projects?.map((p) => ({
        project_id: p.project_id,
        name: p.project_name,
        task_count: p.tasks_on_project,
      })) || null,
    clients:
      profile.clients?.map((c) => ({
        client_id: c.client_id,
        name: c.client_name,
        task_count: c.tasks_for_client,
      })) || null,
    invoices: null,
  };
}
