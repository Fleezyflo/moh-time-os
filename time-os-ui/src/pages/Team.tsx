// Team page - Rich workload visualization
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { SkeletonCardGrid } from '../components'
import { useTeam } from '../lib/hooks'
import type { TeamMember } from '../types/api'

const loadLevels = {
  overloaded: { label: 'Overloaded', bg: 'bg-red-900/50', text: 'text-red-300', border: 'border-red-900/50' },
  high: { label: 'High Load', bg: 'bg-orange-900/50', text: 'text-orange-300', border: 'border-orange-900/50' },
  normal: { label: 'Normal', bg: 'bg-green-900/50', text: 'text-green-300', border: 'border-slate-700' },
  light: { label: 'Light', bg: 'bg-blue-900/50', text: 'text-blue-300', border: 'border-slate-700' },
  idle: { label: 'Idle', bg: 'bg-slate-700', text: 'text-slate-400', border: 'border-slate-700' },
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
    const matchesSearch = m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.role || '').toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || m.type === filterType;
    return matchesSearch && matchesType;
  });

  const sorted = [...filtered].sort((a: TeamMember, b: TeamMember) => {
    switch (sortBy) {
      case 'name': return a.name.localeCompare(b.name);
      case 'load': return (b.open_tasks || 0) - (a.open_tasks || 0);
      case 'overdue': return (b.overdue_tasks || 0) - (a.overdue_tasks || 0);
      default: return 0;
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
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-slate-100">{internalCount}</div>
          <div className="text-sm text-slate-400">Internal Team</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-blue-400">{totalOpenTasks}</div>
          <div className="text-sm text-slate-400">Open Tasks</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-red-900/50">
          <div className="text-2xl font-bold text-red-400">{totalOverdue}</div>
          <div className="text-sm text-slate-400">Overdue Tasks</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-orange-900/50">
          <div className="text-2xl font-bold text-orange-400">{overloadedCount}</div>
          <div className="text-sm text-slate-400">High/Overloaded</div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold">Team</h1>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Search team..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500 w-40"
          />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as typeof filterType)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
          >
            <option value="internal">Internal</option>
            <option value="external">External</option>
            <option value="all">All</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
          >
            <option value="overdue">Sort: Overdue</option>
            <option value="load">Sort: Workload</option>
            <option value="name">Sort: A-Z</option>
          </select>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center">
          <p className="text-slate-400">No team members found</p>
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
                className={`block bg-slate-800 rounded-lg border transition-colors p-4 ${
                  hasOverdue ? 'border-red-900/50 hover:border-red-700' : 'border-slate-700 hover:border-slate-600'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-slate-100 truncate">{member.name}</h3>
                    <p className="text-sm text-slate-500 truncate">
                      {member.role || member.department || 'Team Member'}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs ${load.bg} ${load.text}`}>
                    {load.label}
                  </span>
                </div>

                {/* Workload Stats */}
                <div className="grid grid-cols-3 gap-2 mt-3">
                  <div className="text-center p-2 bg-slate-700/50 rounded">
                    <div className="text-lg font-semibold text-slate-200">{member.open_tasks || 0}</div>
                    <div className="text-xs text-slate-500">Open</div>
                  </div>
                  <div className={`text-center p-2 rounded ${hasOverdue ? 'bg-red-900/30' : 'bg-slate-700/50'}`}>
                    <div className={`text-lg font-semibold ${hasOverdue ? 'text-red-400' : 'text-slate-200'}`}>
                      {member.overdue_tasks || 0}
                    </div>
                    <div className="text-xs text-slate-500">Overdue</div>
                  </div>
                  <div className="text-center p-2 bg-slate-700/50 rounded">
                    <div className="text-lg font-semibold text-green-400">{member.completed_this_week || 0}</div>
                    <div className="text-xs text-slate-500">Done/wk</div>
                  </div>
                </div>

                {/* Due Today indicator */}
                {(member.due_today || 0) > 0 && (
                  <div className="mt-3 px-2 py-1 bg-amber-900/30 rounded text-xs text-amber-300">
                    ⚡ {member.due_today} due today
                  </div>
                )}

                {/* Client association */}
                {member.client_name && (
                  <div className="mt-2 text-xs text-slate-500">
                    📎 {member.client_name}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
