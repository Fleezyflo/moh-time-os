/**
 * ProfileShell — Full page wrapper for entity profile views
 *
 * Composes: ProfileHeader > custom sections > ConnectedEntities
 *
 * Entity views use ProfileShell by passing mapper functions and
 * a renderSections callback that returns entity-specific content.
 */

import type { ReactNode } from 'react';
import { ProfileHeader } from './ProfileHeader';
import { ConnectedEntities } from './ConnectedEntities';
import { ErrorState } from '../../components/ErrorState';
import { SkeletonCard } from '../../components/Skeleton';

type EntityType = 'client' | 'person' | 'project';

interface ProfileHeaderProps {
  name: string;
  score?: number | null;
  classification?: string | null;
  primarySignal?: { severity: 'critical' | 'warning' | 'watch'; headline: string } | null;
  quickStats?: Record<string, string | number>;
  trend?: { direction: 'increasing' | 'declining' | 'stable'; magnitude: number } | null;
}

interface ConnectedEntitiesProps {
  persons?: Array<{
    person_id: number | string;
    name: string;
    role?: string | null;
    task_count?: number;
    communication_volume?: number;
  }> | null;
  projects?: Array<{
    project_id: number | string;
    name: string;
    status?: string;
    health_score?: number;
    task_count?: number;
  }> | null;
  clients?: Array<{
    client_id: number | string;
    name: string;
    task_count?: number;
    communication_volume?: number;
  }> | null;
  invoices?: Array<{
    invoice_id: number | string;
    amount: number;
    status: string;
    date: string;
  }> | null;
}

interface ProfileShellProps<T> {
  entityType: EntityType;
  data: T | null;
  loading: boolean;
  error: Error | null;
  onRefresh: () => void;
  mapToHeader: (data: T) => ProfileHeaderProps;
  mapToConnected: (data: T) => ConnectedEntitiesProps;
  renderSections: (data: T) => ReactNode;
  headerActions?: ReactNode;
}

function LoadingSkeleton() {
  return (
    <div className="max-w-5xl">
      <div className="p-5 bg-slate-800 border border-slate-700 rounded-lg mb-6">
        <div className="animate-pulse">
          <div className="flex gap-3 mb-3">
            <div className="h-5 w-16 bg-slate-700/50 rounded-full" />
            <div className="h-6 w-48 bg-slate-700/50 rounded" />
          </div>
          <div className="flex gap-3 mb-4">
            <div className="h-10 w-16 bg-slate-700/50 rounded" />
            <div className="h-5 w-20 bg-slate-700/50 rounded" />
          </div>
          <div className="flex gap-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="h-4 w-20 bg-slate-700/50 rounded" />
            ))}
          </div>
        </div>
      </div>
      <div className="space-y-6">
        {Array.from({ length: 2 }, (_, i) => (
          <div key={i}>
            <div className="h-5 w-32 bg-slate-700/50 rounded mb-3 animate-pulse" />
            <SkeletonCard />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProfileShell<T>({
  entityType,
  data,
  loading,
  error,
  onRefresh,
  mapToHeader,
  mapToConnected,
  renderSections,
  headerActions,
}: ProfileShellProps<T>) {
  if (error && !data) {
    return (
      <div className="max-w-5xl p-6">
        <ErrorState error={error} onRetry={onRefresh} />
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-5xl p-6">
        <div className="text-center text-slate-400 py-12">No data available</div>
      </div>
    );
  }

  const headerProps = mapToHeader(data);
  const connectedProps = mapToConnected(data);

  return (
    <div className="p-6">
      <div className="max-w-5xl">
        {loading && (
          <div className="fixed top-4 right-4 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-400 flex items-center gap-2 z-50">
            <span className="animate-spin">↻</span>
            Refreshing...
          </div>
        )}

        {error && data && <ErrorState error={error} onRetry={onRefresh} hasData />}

        <ProfileHeader
          entityType={entityType}
          {...headerProps}
          actions={
            <div className="flex items-center gap-2">
              {headerActions}
              <button
                onClick={onRefresh}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-white bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded transition-colors"
                title="Refresh data"
              >
                ↻ Refresh
              </button>
            </div>
          }
        />

        <div className="mt-6">{renderSections(data)}</div>

        <ConnectedEntities {...connectedProps} />
      </div>
    </div>
  );
}
