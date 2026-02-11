// Clients Portfolio page
import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { SkeletonCardGrid } from '../components';
import { useClients } from '../lib/hooks';
import { formatCurrency } from '../lib/format';
import type { Client } from '../types/api';

// Health score ranges (0-100)
function getHealthStyle(score: number | null, dbHealth: string | null) {
  // Use computed score if available, fall back to DB health
  if (score !== null) {
    if (score < 30)
      return {
        bg: 'bg-red-900/50',
        text: 'text-red-300',
        label: `${score}`,
        border: 'border-red-900/50',
      };
    if (score < 50)
      return {
        bg: 'bg-orange-900/50',
        text: 'text-orange-300',
        label: `${score}`,
        border: 'border-orange-900/50',
      };
    if (score < 70)
      return {
        bg: 'bg-amber-900/50',
        text: 'text-amber-300',
        label: `${score}`,
        border: 'border-slate-700',
      };
    if (score < 85)
      return {
        bg: 'bg-green-900/50',
        text: 'text-green-300',
        label: `${score}`,
        border: 'border-slate-700',
      };
    return {
      bg: 'bg-emerald-900/50',
      text: 'text-emerald-300',
      label: `${score}`,
      border: 'border-slate-700',
    };
  }
  // Fallback to DB health string
  const healthStyles: Record<string, { bg: string; text: string; label: string; border: string }> =
    {
      critical: {
        bg: 'bg-red-900/50',
        text: 'text-red-300',
        label: 'Critical',
        border: 'border-red-900/50',
      },
      poor: {
        bg: 'bg-orange-900/50',
        text: 'text-orange-300',
        label: 'Poor',
        border: 'border-orange-900/50',
      },
      fair: {
        bg: 'bg-amber-900/50',
        text: 'text-amber-300',
        label: 'Fair',
        border: 'border-slate-700',
      },
      good: {
        bg: 'bg-green-900/50',
        text: 'text-green-300',
        label: 'Good',
        border: 'border-slate-700',
      },
      excellent: {
        bg: 'bg-emerald-900/50',
        text: 'text-emerald-300',
        label: 'Excellent',
        border: 'border-slate-700',
      },
    };
  return healthStyles[dbHealth || 'good'] || healthStyles.good;
}

const trendIcons: Record<string, string> = {
  improving: '📈',
  stable: '➡️',
  declining: '📉',
};

const agingStyles: Record<string, { bg: string; text: string }> = {
  current: { bg: 'bg-slate-700', text: 'text-slate-300' },
  '30': { bg: 'bg-amber-900/50', text: 'text-amber-300' },
  '60': { bg: 'bg-orange-900/50', text: 'text-orange-300' },
  '90+': { bg: 'bg-red-900/50', text: 'text-red-300' },
};

export function Clients() {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'health' | 'name' | 'tier' | 'ar' | 'revenue'>('revenue');
  const [filterHealth, setFilterHealth] = useState<string>('all');

  const { data: apiClients, loading } = useClients();

  if (loading) return <SkeletonCardGrid count={6} />;

  const clients = apiClients?.items || [];

  const filtered = clients.filter((c: Client) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
    const matchesHealth = filterHealth === 'all' || c.relationship_health === filterHealth;
    return matchesSearch && matchesHealth;
  });

  const tierOrder: Record<string, number> = { A: 0, B: 1, C: 2 };

  // Helper to get health score for sorting
  const getHealthScore = (c: Client): number =>
    c.health_score ??
    (c.relationship_health === 'critical'
      ? 10
      : c.relationship_health === 'poor'
        ? 30
        : c.relationship_health === 'fair'
          ? 50
          : 70);

  const sorted = [...filtered].sort((a: Client, b: Client) => {
    switch (sortBy) {
      case 'health':
        return getHealthScore(a) - getHealthScore(b);
      case 'name':
        return a.name.localeCompare(b.name);
      case 'tier':
        return (tierOrder[a.tier || ''] ?? 3) - (tierOrder[b.tier || ''] ?? 3);
      case 'ar':
        return (b.financial_ar_total || 0) - (a.financial_ar_total || 0);
      case 'revenue':
        return (b.lifetime_revenue || 0) - (a.lifetime_revenue || 0);
      default:
        return 0;
    }
  });

  // Summary stats
  const totalAR = clients.reduce((sum: number, c: Client) => sum + (c.financial_ar_total || 0), 0);
  const totalRevenue = clients.reduce(
    (sum: number, c: Client) => sum + (c.lifetime_revenue || 0),
    0
  );
  const ytdRevenue = clients.reduce((sum: number, c: Client) => sum + (c.ytd_revenue || 0), 0);
  const atRiskCount = clients.filter(
    (c: Client) => c.computed_at_risk || (c.health_score !== null && c.health_score < 50)
  ).length;
  const overdueAR = clients.reduce((sum: number, c: Client) => {
    if (c.financial_ar_aging_bucket && c.financial_ar_aging_bucket !== 'current') {
      return sum + (c.financial_ar_total || 0);
    }
    return sum;
  }, 0);

  return (
    <div>
      {/* Summary Banner */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-slate-100">{clients.length}</div>
          <div className="text-sm text-slate-400">Total Clients</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-green-900/50">
          <div className="text-2xl font-bold text-green-400">{formatCurrency(totalRevenue)}</div>
          <div className="text-sm text-slate-400">Lifetime Revenue</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-emerald-400">{formatCurrency(ytdRevenue)}</div>
          <div className="text-sm text-slate-400">YTD Revenue</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-amber-400">{formatCurrency(totalAR)}</div>
          <div className="text-sm text-slate-400">Outstanding AR</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-red-900/50">
          <div className="text-2xl font-bold text-red-400">{formatCurrency(overdueAR)}</div>
          <div className="text-sm text-slate-400">Overdue AR</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4 border border-orange-900/50">
          <div className="text-2xl font-bold text-orange-400">{atRiskCount}</div>
          <div className="text-sm text-slate-400">At-Risk</div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold">Clients Portfolio</h1>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Search clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm placeholder-slate-500 w-40"
          />
          <select
            value={filterHealth}
            onChange={(e) => setFilterHealth(e.target.value)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
          >
            <option value="all">All Health</option>
            <option value="critical">Critical</option>
            <option value="poor">Poor</option>
            <option value="fair">Fair</option>
            <option value="good">Good</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm"
          >
            <option value="revenue">Sort: Revenue</option>
            <option value="ar">Sort: AR Outstanding</option>
            <option value="health">Sort: Health</option>
            <option value="tier">Sort: Tier</option>
            <option value="name">Sort: A-Z</option>
          </select>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center">
          <p className="text-slate-400">No clients found</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((client: Client) => {
            const health = getHealthStyle(client.health_score, client.relationship_health);
            const aging = client.financial_ar_aging_bucket
              ? agingStyles[client.financial_ar_aging_bucket]
              : null;
            const hasAR = (client.financial_ar_total || 0) > 0;
            const isAtRisk =
              client.computed_at_risk || (client.health_score !== null && client.health_score < 50);
            const trend = client.health_trend || client.relationship_trend;

            return (
              <Link
                key={client.id}
                to="/clients/$clientId"
                params={{ clientId: client.id }}
                className={`block bg-slate-800 rounded-lg border transition-colors p-4 ${
                  isAtRisk
                    ? 'border-red-900/50 hover:border-red-700'
                    : 'border-slate-700 hover:border-slate-600'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-slate-100 truncate">{client.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`px-2 py-0.5 rounded text-xs ${health.bg} ${health.text}`}>
                        {client.health_score !== null ? `Health: ${health.label}` : health.label}
                      </span>
                      {trend && (
                        <span className="text-sm" title={trend}>
                          {trendIcons[trend] || ''}
                        </span>
                      )}
                    </div>
                  </div>
                  {client.tier && (
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        client.tier === 'A'
                          ? 'bg-green-900/50 text-green-300'
                          : client.tier === 'B'
                            ? 'bg-blue-900/50 text-blue-300'
                            : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      Tier {client.tier}
                    </span>
                  )}
                </div>

                {/* Health Factors (if computed) */}
                {client.health_factors && Object.keys(client.health_factors).length > 0 && (
                  <div className="grid grid-cols-4 gap-1 text-xs mb-3">
                    {client.health_factors.completion_rate !== undefined && (
                      <div className="text-center">
                        <div className="text-slate-300">
                          {Math.round(client.health_factors.completion_rate * 100)}%
                        </div>
                        <div className="text-slate-500">Done</div>
                      </div>
                    )}
                    {client.health_factors.overdue_count !== undefined && (
                      <div className="text-center">
                        <div
                          className={
                            client.health_factors.overdue_count > 0
                              ? 'text-red-400'
                              : 'text-slate-300'
                          }
                        >
                          {client.health_factors.overdue_count}
                        </div>
                        <div className="text-slate-500">Overdue</div>
                      </div>
                    )}
                    {client.health_factors.activity_score !== undefined && (
                      <div className="text-center">
                        <div className="text-slate-300">{client.health_factors.activity_score}</div>
                        <div className="text-slate-500">Activity</div>
                      </div>
                    )}
                    {client.health_factors.commitment_score !== undefined && (
                      <div className="text-center">
                        <div className="text-slate-300">
                          {client.health_factors.commitment_score}
                        </div>
                        <div className="text-slate-500">Commit</div>
                      </div>
                    )}
                  </div>
                )}

                {/* Revenue Section */}
                {(client.lifetime_revenue || 0) > 0 && (
                  <div className="p-2 rounded bg-green-900/20 border border-green-900/30 mb-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">Lifetime Revenue</span>
                      {(client.ytd_revenue || 0) > 0 && (
                        <span className="text-xs text-emerald-400">
                          YTD: {formatCurrency(client.ytd_revenue)}
                        </span>
                      )}
                    </div>
                    <div className="text-lg font-semibold text-green-400">
                      {formatCurrency(client.lifetime_revenue)}
                    </div>
                  </div>
                )}

                {/* AR Section */}
                {hasAR && (
                  <div className={`p-2 rounded ${aging?.bg || 'bg-slate-700/50'}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">AR Outstanding</span>
                      {client.financial_ar_aging_bucket && (
                        <span className={`text-xs ${aging?.text || 'text-slate-400'}`}>
                          {client.financial_ar_aging_bucket === 'current'
                            ? 'Current'
                            : `${client.financial_ar_aging_bucket} days`}
                        </span>
                      )}
                    </div>
                    <div className={`text-lg font-semibold ${aging?.text || 'text-slate-200'}`}>
                      {formatCurrency(client.financial_ar_total)}
                    </div>
                  </div>
                )}

                {/* Task counts */}
                {client.open_task_count || client.overdue_task_count ? (
                  <div className="mt-2 flex gap-3 text-xs">
                    {client.open_task_count ? (
                      <span className="text-slate-400">{client.open_task_count} tasks</span>
                    ) : null}
                    {client.overdue_task_count ? (
                      <span className="text-red-400">{client.overdue_task_count} overdue</span>
                    ) : null}
                  </div>
                ) : !hasAR ? (
                  <div className="mt-3 text-xs text-slate-500">No outstanding AR</div>
                ) : null}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
