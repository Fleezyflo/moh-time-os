// Client Index Page — Spec §2
// Three swimlanes: Active, Recently Active, Cold

import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import type { ClientCard, ClientIndexResponse, Tier, ClientStatus } from '../types/spec';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';

// Tier badge colors
const TIER_COLORS: Record<Tier, string> = {
  platinum: 'bg-purple-500 text-white',
  gold: 'bg-yellow-500 text-black',
  silver: 'bg-slate-400 text-black',
  bronze: 'bg-orange-700 text-white',
  none: 'bg-slate-600 text-slate-300',
};

// Status badge colors
const STATUS_COLORS: Record<ClientStatus, string> = {
  active: 'bg-green-600 text-white',
  recently_active: 'bg-yellow-600 text-black',
  cold: 'bg-slate-600 text-slate-300',
};

// Health score colors
function getHealthColor(score: number): string {
  if (score >= 70) return 'text-green-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

function getHealthBg(score: number): string {
  if (score >= 70) return 'bg-green-500';
  if (score >= 40) return 'bg-yellow-500';
  return 'bg-red-500';
}

// Format currency
function formatCurrency(amount: number, currency = 'AED'): string {
  return `${currency} ${amount.toLocaleString()}`;
}

export function ClientIndex() {
  const [data, setData] = useState<ClientIndexResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Collapsible sections (Active expanded by default)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    active: true,
    recently_active: false,
    cold: false,
  });

  // Filters
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [hasIssuesFilter, setHasIssuesFilter] = useState(false);
  const [hasOverdueFilter, setHasOverdueFilter] = useState(false);

  useEffect(() => {
    async function fetchClients() {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (tierFilter !== 'all') params.set('tier', tierFilter);
        if (hasIssuesFilter) params.set('has_issues', 'true');
        if (hasOverdueFilter) params.set('has_overdue_ar', 'true');

        const url = `${API_BASE}/clients${params.toString() ? '?' + params.toString() : ''}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch clients');
        const json = await res.json();
        setData(json);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchClients();
  }, [tierFilter, hasIssuesFilter, hasOverdueFilter]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-slate-800 rounded animate-pulse w-48" />
        <div className="h-64 bg-slate-800 rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-red-400">
        <p>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Clients</h1>
        <div className="flex gap-2">
          {/* Tier filter */}
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded px-3 py-1.5 text-sm"
          >
            <option value="all">All Tiers</option>
            <option value="platinum">Platinum</option>
            <option value="gold">Gold</option>
            <option value="silver">Silver</option>
            <option value="bronze">Bronze</option>
            <option value="none">None</option>
          </select>

          {/* Toggle filters */}
          <button
            onClick={() => setHasIssuesFilter(!hasIssuesFilter)}
            className={`px-3 py-1.5 rounded text-sm ${
              hasIssuesFilter ? 'bg-red-600' : 'bg-slate-800 border border-slate-700'
            }`}
          >
            Has Issues
          </button>
          <button
            onClick={() => setHasOverdueFilter(!hasOverdueFilter)}
            className={`px-3 py-1.5 rounded text-sm ${
              hasOverdueFilter ? 'bg-orange-600' : 'bg-slate-800 border border-slate-700'
            }`}
          >
            AR Overdue
          </button>
        </div>
      </div>

      {/* Swimlane: Active */}
      <Swimlane
        title="Active Clients"
        count={data.counts.active}
        expanded={expandedSections.active}
        onToggle={() => toggleSection('active')}
        clients={data.active}
        status="active"
      />

      {/* Swimlane: Recently Active */}
      <Swimlane
        title="Recently Active"
        count={data.counts.recently_active}
        expanded={expandedSections.recently_active}
        onToggle={() => toggleSection('recently_active')}
        clients={data.recently_active}
        status="recently_active"
      />

      {/* Swimlane: Cold */}
      <Swimlane
        title="Cold"
        count={data.counts.cold}
        expanded={expandedSections.cold}
        onToggle={() => toggleSection('cold')}
        clients={data.cold}
        status="cold"
      />
    </div>
  );
}

// ==== Swimlane Component ====

interface SwimlanePr {
  title: string;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  clients: ClientCard[];
  status: ClientStatus;
}

function Swimlane({ title, count, expanded, onToggle, clients, status }: SwimlanePr) {
  return (
    <div className="bg-slate-800 rounded-lg overflow-hidden">
      {/* Header (clickable) */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-750 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className={`transform transition-transform ${expanded ? 'rotate-90' : ''}`}>
            ▶
          </span>
          <span className="font-medium">{title}</span>
          <span className="px-2 py-0.5 bg-slate-700 rounded text-sm">{count}</span>
        </div>
      </button>

      {/* Content */}
      {expanded && (
        <div className="px-4 pb-4">
          {clients.length === 0 ? (
            <div className="text-center py-8 text-slate-400">No clients</div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {clients.map((client) => (
                <ClientCardComponent key={client.id} client={client} status={status} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==== Client Card Components ====

interface ClientCardProps {
  client: ClientCard;
  status: ClientStatus;
}

function ClientCardComponent({ client, status }: ClientCardProps) {
  if (status === 'active') {
    return <ActiveClientCard client={client} />;
  } else if (status === 'recently_active') {
    return <RecentlyActiveCard client={client} />;
  } else {
    return <ColdClientCard client={client} />;
  }
}

// Active Client Card — Spec §2.2
function ActiveClientCard({ client }: { client: ClientCard }) {
  const healthScore = client.health_score ?? 0;
  const healthPct = Math.min(100, Math.max(0, healthScore));

  return (
    <Link
      to="/clients/$clientId"
      params={{ clientId: client.id }}
      className="block bg-slate-900 rounded-lg p-4 hover:ring-1 hover:ring-slate-600 transition-all"
    >
      {/* Row 1: Name + Tier */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-white truncate">{client.name}</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[client.tier]}`}>
          {client.tier}
        </span>
      </div>

      {/* Row 2: Health Score */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-slate-400">Health</span>
          <span className={`font-medium ${getHealthColor(healthScore)}`}>
            {healthScore} <span className="text-slate-500">(provisional)</span>
          </span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full ${getHealthBg(healthScore)}`}
            style={{ width: `${healthPct}%` }}
          />
        </div>
      </div>

      {/* Row 3-4: Issued / Paid */}
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div>
          <div className="text-slate-400 text-xs">ISSUED</div>
          <div className="text-slate-300">Prior Yr: {formatCurrency(client.issued_year ?? 0)}</div>
          <div className="text-white">YTD: {formatCurrency(client.issued_ytd ?? 0)}</div>
        </div>
        <div>
          <div className="text-slate-400 text-xs">PAID</div>
          <div className="text-slate-300">Prior Yr: {formatCurrency(client.paid_year ?? 0)}</div>
          <div className="text-white">YTD: {formatCurrency(client.paid_ytd ?? 0)}</div>
        </div>
      </div>

      {/* Row 5: AR */}
      <div className="text-sm mb-3 p-2 bg-slate-800 rounded">
        <div className="flex justify-between">
          <span className="text-slate-400">AR Outstanding</span>
          <span className="text-white">{formatCurrency(client.ar_outstanding ?? 0)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Overdue</span>
          <span className={client.ar_overdue_pct && client.ar_overdue_pct > 30 ? 'text-red-400' : 'text-white'}>
            {formatCurrency(client.ar_overdue ?? 0)} ({client.ar_overdue_pct ?? 0}%)
          </span>
        </div>
      </div>

      {/* Row 6: Open Issues */}
      {(client.open_issues_high_critical ?? 0) > 0 && (
        <div className="flex items-center gap-1 text-sm text-red-400">
          <span>⚠</span>
          <span>{client.open_issues_high_critical} open issues (high/critical)</span>
        </div>
      )}
    </Link>
  );
}

// Recently Active Card — Spec §2.3
function RecentlyActiveCard({ client }: { client: ClientCard }) {
  return (
    <Link
      to="/clients/$clientId"
      params={{ clientId: client.id }}
      className="block bg-slate-900 rounded-lg p-4 hover:ring-1 hover:ring-slate-600 transition-all"
    >
      {/* Row 1: Name + Badge */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-white truncate">{client.name}</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS.recently_active}`}>
          Recently Active
        </span>
      </div>

      {/* Row 2-3: Issued / Paid */}
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div>
          <div className="text-slate-400 text-xs">ISSUED</div>
          <div className="text-white">Last 12m: {formatCurrency(client.issued_last_12m ?? 0)}</div>
          <div className="text-slate-300">Prev 12m: {formatCurrency(client.issued_prev_12m ?? 0)}</div>
        </div>
        <div>
          <div className="text-slate-400 text-xs">PAID</div>
          <div className="text-white">Last 12m: {formatCurrency(client.paid_last_12m ?? 0)}</div>
          <div className="text-slate-300">Prev 12m: {formatCurrency(client.paid_prev_12m ?? 0)}</div>
        </div>
      </div>

      {/* Row 4: Historical */}
      <div className="text-sm text-slate-400 mb-1">
        Historical: {formatCurrency(client.issued_lifetime ?? 0)} issued / {formatCurrency(client.paid_lifetime ?? 0)} paid
      </div>

      {/* Row 5: Last Invoice */}
      <div className="text-sm text-slate-500">
        Last invoice: {client.last_invoice_date ?? 'N/A'}
      </div>
    </Link>
  );
}

// Cold Client Card — Spec §2.4
function ColdClientCard({ client }: { client: ClientCard }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-4 opacity-60">
      {/* Row 1: Name + Badge */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-300 truncate">{client.name}</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS.cold}`}>
          Cold
        </span>
      </div>

      {/* Row 2: Historical */}
      <div className="text-sm text-slate-400 mb-1">
        Historical: {formatCurrency(client.issued_lifetime ?? 0)} issued / {formatCurrency(client.paid_lifetime ?? 0)} paid
      </div>

      {/* Row 3: Last Invoice */}
      <div className="text-sm text-slate-500">
        Last invoice: {client.last_invoice_date ?? 'N/A'}
      </div>
    </div>
  );
}

export default ClientIndex;
