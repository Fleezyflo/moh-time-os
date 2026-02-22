// Cold Clients Page — Spec §5
// Dedicated page for cold clients (>270 days since last invoice)

import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import type { Tier } from '../types/spec';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';

interface ColdClient {
  id: string;
  name: string;
  tier: Tier;
  status: 'cold';
  last_invoice_date: string | null;
  first_invoice_date: string | null;
  // Lifetime only
  issued_lifetime: number;
  paid_lifetime: number;
  // Days since last activity
  days_since_last_invoice: number | null;
}

const TIER_COLORS: Record<Tier, string> = {
  platinum: 'bg-purple-500 text-[var(--white)]',
  gold: 'bg-[var(--warning)] text-[var(--black)]',
  silver: 'bg-[var(--grey-light)] text-[var(--black)]',
  bronze: 'bg-[var(--warning)] text-[var(--white)]',
  none: 'bg-[var(--grey-dim)] text-[var(--grey-light)]',
};

function formatCurrency(amount: number, currency = 'AED'): string {
  return `${currency} ${amount.toLocaleString()}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return 'N/A';
  return new Date(iso).toLocaleDateString();
}

export function ColdClients() {
  const [clients, setClients] = useState<ColdClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'name' | 'lifetime' | 'last_activity'>('last_activity');

  useEffect(() => {
    async function fetchClients() {
      setLoading(true);
      try {
        const params = new URLSearchParams({ status: 'cold' });
        if (tierFilter !== 'all') params.set('tier', tierFilter);

        const res = await fetch(`${API_BASE}/clients?${params.toString()}`);
        if (!res.ok) throw new Error('Failed to fetch clients');
        const data = await res.json();
        setClients(data.cold || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchClients();
  }, [tierFilter]);

  // Sort clients
  const sortedClients = [...clients].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'lifetime':
        return (b.issued_lifetime || 0) - (a.issued_lifetime || 0);
      case 'last_activity':
        return (b.days_since_last_invoice || 9999) - (a.days_since_last_invoice || 9999);
      default:
        return 0;
    }
  });

  // Summary stats
  const totalLifetimeIssued = clients.reduce((sum, c) => sum + (c.issued_lifetime || 0), 0);
  const totalLifetimePaid = clients.reduce((sum, c) => sum + (c.paid_lifetime || 0), 0);
  const avgDaysSince =
    clients.length > 0
      ? Math.round(
          clients.reduce((sum, c) => sum + (c.days_since_last_invoice || 0), 0) / clients.length
        )
      : 0;

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-[var(--grey-dim)] rounded animate-pulse w-48" />
        <div className="h-64 bg-[var(--grey-dim)] rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-[var(--danger)]">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/clients" className="text-sm text-[var(--grey-light)] hover:text-[var(--white)] mb-1 inline-block">
            ← Back to All Clients
          </Link>
          <h1 className="text-2xl font-bold text-[var(--white)]">Cold Clients</h1>
          <p className="text-[var(--grey-light)] text-sm">Clients with no activity for 270+ days</p>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--white)]">{clients.length}</div>
          <div className="text-sm text-[var(--grey-light)]">Cold Clients</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--white)]">{formatCurrency(totalLifetimeIssued)}</div>
          <div className="text-sm text-[var(--grey-light)]">Lifetime Issued</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--white)]">{formatCurrency(totalLifetimePaid)}</div>
          <div className="text-sm text-[var(--grey-light)]">Lifetime Paid</div>
        </div>
        <div className="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
          <div className="text-2xl font-bold text-[var(--white)]">{avgDaysSince}d</div>
          <div className="text-sm text-[var(--grey-light)]">Avg Days Inactive</div>
        </div>
      </div>

      {/* Filters and Sort */}
      <div className="flex items-center gap-4 bg-[var(--grey-dim)] rounded-lg p-3 border border-[var(--grey)]">
        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--grey-light)]">Tier:</label>
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm text-[var(--white)]"
          >
            <option value="all">All</option>
            <option value="platinum">Platinum</option>
            <option value="gold">Gold</option>
            <option value="silver">Silver</option>
            <option value="bronze">Bronze</option>
            <option value="none">None</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--grey-light)]">Sort:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="bg-[var(--grey)] border-none rounded px-2 py-1 text-sm text-[var(--white)]"
          >
            <option value="last_activity">Last Activity (most recent)</option>
            <option value="lifetime">Lifetime Value (highest)</option>
            <option value="name">Name (A-Z)</option>
          </select>
        </div>

        <div className="ml-auto text-sm text-[var(--grey-light)]">Showing {sortedClients.length} clients</div>
      </div>

      {/* Client List */}
      {sortedClients.length === 0 ? (
        <div className="text-center py-16 text-[var(--grey-light)]">
          <span className="text-4xl mb-2 block">🥶</span>
          <p>No cold clients found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sortedClients.map((client) => (
            <ColdClientCard key={client.id} client={client} />
          ))}
        </div>
      )}
    </div>
  );
}

function ColdClientCard({ client }: { client: ColdClient }) {
  return (
    <div className="bg-[var(--black)]/60 rounded-lg p-4 opacity-70 hover:opacity-100 transition-opacity border border-[var(--grey)]">
      <div className="flex items-start gap-4">
        {/* Left: Name and tier */}
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-[var(--grey-light)]">{client.name}</h3>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[client.tier]}`}>
              {client.tier}
            </span>
          </div>
          <div className="text-sm text-[var(--grey)]">
            Last invoice: {formatDate(client.last_invoice_date)}
            {client.days_since_last_invoice && (
              <span className="ml-2">({client.days_since_last_invoice} days ago)</span>
            )}
          </div>
        </div>

        {/* Right: Lifetime stats */}
        <div className="text-right">
          <div className="text-sm">
            <span className="text-[var(--grey-light)]">Issued:</span>
            <span className="ml-2 text-[var(--grey-light)]">
              {formatCurrency(client.issued_lifetime || 0)}
            </span>
          </div>
          <div className="text-sm">
            <span className="text-[var(--grey-light)]">Paid:</span>
            <span className="ml-2 text-[var(--grey-light)]">{formatCurrency(client.paid_lifetime || 0)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ColdClients;
