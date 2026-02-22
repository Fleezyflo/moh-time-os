// Team page - Rich workload visualization
import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { SkeletonCardGrid } from '../components';
import { useTeam } from '../lib/hooks';
import type { TeamMember } from '../types/api';

const loadLevels = {
  overloaded: {
    label: 'Overloaded',
    bg: 'bg-[var(--danger)]/20',
    text: 'text-[var(--danger)]',
    border: 'border-[var(--danger)]/50',
  },
  high: {
    label: 'High Load',
    bg: 'bg-[var(--warning)]/20',
    text: 'text-[var(--warning)]',
    border: 'border-[var(--warning)]/50',
  },
  normal: {
    label: 'Normal',
    bg: 'bg-[var(--success)]/20',
    text: 'text-[var(--success)]',
    border: 'border-[var(--grey)]',
  },
  light: {
    label: 'Light',
    bg: 'bg-[var(--info)]/20',
    text: 'text-[var(--info)]',
    border: 'border-[var(--grey)]',
  },
  idle: {
    label: 'Idle',
    bg: 'bg-[var(--grey)]',
    text: 'text-[var(--grey-light)]',
    border: 'border-[var(--grey)]',
  },
};

function getLoadLevel(openTasks: number, overdue: number) {
  if (overdue > 5 || openTasks > 20) return loadLevels.overloaded;
  if (overdue > 2 || openTasks > 12) return loadLevels.high;
  if (openTasks > 5) return loadLevels.normal;
  if (openTasks > 0) return loadLevels.light;
  return loadLevels.idle;
}

export function Team() {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'load' | 'overdue'>('overdue');
  const [filterType, setFilterType] = useState<'all' | 'internal' | 'external'>('all');

  const { data: apiTeam, loading } = useTeam();

  if (loading) return <SkeletonCardGrid count={6} />;

  const team = apiTeam?.items || [];

  const filtered = team.filter((m: TeamMember) => {
    const matchesSearch =
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.role || '').toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || m.type === filterType;
    return matchesSearch && matchesType;
  });

  const sorted = [...filtered].sort((a: TeamMember, b: TeamMember) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'load':
        return (b.open_tasks || 0) - (a.open_tasks || 0);
      case 'overdue':
        return (b.overdue_tasks || 0) - (a.overdue_tasks || 0);
      default:
        return 0;
    }
  });

  // Summary stats
  const internalCount = team.filter((m: TeamMember) => m.type === 'internal').length;
  const totalOpenTasks = team.reduce((sum: number, m: TeamMember) => sum + (m.open_tasks || 0), 0);
  const totalOverdue = team.reduce((sum: number, m: TeamMember) => sum + (m.overdue_tasks || 0), 0);
  const overloadedCount = team.filter((m: TeamMember) => {
    const load = getLoadLevel(m.open_tasks || 0, m.overdue_tasks || 0);
    return load === loadLevels.overloaded || load === loadLevels.high;
  }).length;

  return (
    <div>
      {/* Summary Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--white)]">{internalCount}</div>
          <div className="text-sm text-[var(--grey-light)]">Internal Team</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--info)]">{totalOpenTasks}</div>
          <div className="text-sm text-[var(--grey-light)]">Open Tasks</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--danger)]/50">
          <div className="text-2xl font-bold text-[var(--danger)]">{totalOverdue}</div>
          <div className="text-sm text-[var(--grey-light)]">Overdue Tasks</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--warning)]/50">
          <div className="text-2xl font-bold text-[var(--warning)]">{overloadedCount}</div>
          <div className="text-sm text-[var(--grey-light)]">High/Overloaded</div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold text-[var(--white)]">Team</h1>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Search team..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm placeholder-[var(--grey)] w-40 text-[var(--white)]"
          />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as typeof filterType)}
            className="px-3 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm text-[var(--white)]"
          >
            <option value="internal">Internal</option>
            <option value="external">External</option>
            <option value="all">All</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="px-3 py-1.5 bg-[var(--grey-dim)] border border-[var(--grey)] rounded text-sm text-[var(--white)]"
          >
            <option value="overdue">Sort: Overdue</option>
            <option value="load">Sort: Workload</option>
            <option value="name">Sort: A-Z</option>
          </select>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="bg-[var(--grey-dim)]/50 rounded-lg border border-[var(--grey)] p-8 text-center">
          <p className="text-[var(--grey-light)]">No team members found</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((member: TeamMember) => {
            const load = getLoadLevel(member.open_tasks || 0, member.overdue_tasks || 0);
            const hasOverdue = (member.overdue_tasks || 0) > 0;

            return (
              <Link
                key={member.id}
                to="/team/$id"
                params={{ id: member.id }}
                className={`block bg-[var(--grey-dim)] rounded-lg border transition-colors p-4 ${
                  hasOverdue
                    ? 'border-[var(--danger)]/50 hover:border-[var(--danger)]'
                    : 'border-[var(--grey)] hover:border-[var(--grey-light)]'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-[var(--white)] truncate">{member.name}</h3>
                    <p className="text-sm text-[var(--grey)] truncate">
                      {member.role || member.department || 'Team Member'}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs ${load.bg} ${load.text}`}>
                    {load.label}
                  </span>
                </div>

                {/* Workload Stats */}
                <div className="grid grid-cols-3 gap-2 mt-3">
                  <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                    <div className="text-lg font-semibold text-[var(--white)]">
                      {member.open_tasks || 0}
                    </div>
                    <div className="text-xs text-[var(--grey)]">Open</div>
                  </div>
                  <div
                    className={`text-center p-2 rounded ${hasOverdue ? 'bg-[var(--danger)]/30' : 'bg-[var(--black)]/50'}`}
                  >
                    <div
                      className={`text-lg font-semibold ${hasOverdue ? 'text-[var(--danger)]' : 'text-[var(--white)]'}`}
                    >
                      {member.overdue_tasks || 0}
                    </div>
                    <div className="text-xs text-[var(--grey)]">Overdue</div>
                  </div>
                  <div className="text-center p-2 bg-[var(--black)]/50 rounded">
                    <div className="text-lg font-semibold text-[var(--success)]">
                      {member.completed_this_week || 0}
                    </div>
                    <div className="text-xs text-[var(--grey)]">Done/wk</div>
                  </div>
                </div>

                {/* Due Today indicator */}
                {(member.due_today || 0) > 0 && (
                  <div className="mt-3 px-2 py-1 bg-[var(--warning)]/30 rounded text-xs text-[var(--warning)]">
                    ⚡ {member.due_today} due today
                  </div>
                )}

                {/* Client association */}
                {member.client_name && (
                  <div className="mt-2 text-xs text-[var(--grey)]">📎 {member.client_name}</div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default Team;
