// Recently Active Client Drilldown — Spec §4
// Detailed view for recently active clients (91-270 days since last invoice)

import { useState, useEffect } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import type { Tier } from '../types/spec';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';

interface RecentlyActiveClient {
  id: string;
  name: string;
  tier: Tier;
  status: 'recently_active';
  last_invoice_date: string | null;
  first_invoice_date: string | null;
  // Financial comparison
  issued_last_12m: number;
  issued_prev_12m: number;
  paid_last_12m: number;
  paid_prev_12m: number;
  // Lifetime
  issued_lifetime: number;
  paid_lifetime: number;
  // Engagement history
  brands: BrandHistory[];
  // Invoice history
  invoices: Invoice[];
}

interface BrandHistory {
  id: string;
  name: string;
  engagements: EngagementHistory[];
}

interface EngagementHistory {
  id: string;
  name: string;
  type: 'project' | 'retainer';
  state: string;
  started_at: string | null;
  completed_at: string | null;
  total_invoiced: number;
  total_paid: number;
}

interface Invoice {
  id: string;
  number: string;
  issue_date: string;
  amount: number;
  status: string;
  paid_date: string | null;
}

const TIER_COLORS: Record<Tier, string> = {
  platinum: 'bg-purple-500 text-[var(--white)]',
  gold: 'bg-[var(--warning)] text-black',
  silver: 'bg-[var(--grey-light)] text-[var(--black)]',
  bronze: 'bg-orange-700 text-[var(--white)]',
  none: 'bg-[var(--grey-light)] text-[var(--grey-light)]',
};

function formatCurrency(amount: number, currency = 'AED'): string {
  return `${currency} ${amount.toLocaleString()}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return 'N/A';
  return new Date(iso).toLocaleDateString();
}

export function RecentlyActiveDrilldown() {
  const { clientId } = useParams({ from: '/clients/$clientId/recently-active' });
  const [client, setClient] = useState<RecentlyActiveClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchClient() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/clients/${clientId}?include=recently_active`);
        if (!res.ok) throw new Error('Failed to fetch client');
        const data = await res.json();
        setClient(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchClient();
  }, [clientId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-[var(--grey-dim)] rounded animate-pulse w-48" />
        <div className="h-64 bg-[var(--grey-dim)] rounded animate-pulse" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="p-8 text-center">
        <p className="text-[var(--danger)]">{error || 'Client not found'}</p>
        <Link to="/clients" className="mt-4 text-[var(--info)] hover:underline">
          ← Back to Clients
        </Link>
      </div>
    );
  }

  // Calculate trends
  const issuedTrend =
    client.issued_prev_12m > 0
      ? (
          ((client.issued_last_12m - client.issued_prev_12m) / client.issued_prev_12m) *
          100
        ).toFixed(0)
      : null;
  const paidTrend =
    client.paid_prev_12m > 0
      ? (((client.paid_last_12m - client.paid_prev_12m) / client.paid_prev_12m) * 100).toFixed(0)
      : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-[var(--grey-dim)] rounded-lg p-4">
        <Link
          to="/clients"
          className="text-sm text-[var(--grey-light)] hover:text-[var(--white)] mb-2 inline-block"
        >
          ← Back to Index
        </Link>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[var(--white)]">{client.name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[client.tier]}`}
              >
                {client.tier}
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-600 text-black">
                Recently Active
              </span>
            </div>
          </div>
          <div className="text-right text-sm text-[var(--grey-light)]">
            <div>Last Invoice: {formatDate(client.last_invoice_date)}</div>
            <div>First Invoice: {formatDate(client.first_invoice_date)}</div>
          </div>
        </div>
      </div>

      {/* Financial Comparison (§4.1) */}
      <div className="bg-[var(--grey-dim)] rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">Financial Comparison</h2>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Issued */}
          <div className="bg-[var(--black)] rounded p-4">
            <h3 className="text-sm text-[var(--grey-light)] mb-3">ISSUED</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Last 12 months</span>
                <span className="font-medium">{formatCurrency(client.issued_last_12m)}</span>
              </div>
              <div className="flex justify-between text-[var(--grey-light)]">
                <span>Previous 12 months</span>
                <span>{formatCurrency(client.issued_prev_12m)}</span>
              </div>
              {issuedTrend !== null && (
                <div
                  className={`text-sm ${Number(issuedTrend) >= 0 ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}
                >
                  {Number(issuedTrend) >= 0 ? '↑' : '↓'} {Math.abs(Number(issuedTrend))}% vs prior
                  period
                </div>
              )}
              <div className="border-t border-[var(--grey)] pt-2 mt-2">
                <div className="flex justify-between text-[var(--grey-light)]">
                  <span>Lifetime</span>
                  <span>{formatCurrency(client.issued_lifetime)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Paid */}
          <div className="bg-[var(--black)] rounded p-4">
            <h3 className="text-sm text-[var(--grey-light)] mb-3">PAID</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Last 12 months</span>
                <span className="font-medium">{formatCurrency(client.paid_last_12m)}</span>
              </div>
              <div className="flex justify-between text-[var(--grey-light)]">
                <span>Previous 12 months</span>
                <span>{formatCurrency(client.paid_prev_12m)}</span>
              </div>
              {paidTrend !== null && (
                <div
                  className={`text-sm ${Number(paidTrend) >= 0 ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}
                >
                  {Number(paidTrend) >= 0 ? '↑' : '↓'} {Math.abs(Number(paidTrend))}% vs prior
                  period
                </div>
              )}
              <div className="border-t border-[var(--grey)] pt-2 mt-2">
                <div className="flex justify-between text-[var(--grey-light)]">
                  <span>Lifetime</span>
                  <span>{formatCurrency(client.paid_lifetime)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Engagement History (§4.2) */}
      <div className="bg-[var(--grey-dim)] rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">Engagement History</h2>

        {client.brands?.length > 0 ? (
          <div className="space-y-4">
            {client.brands.map((brand) => (
              <div key={brand.id}>
                <h3 className="font-medium text-[var(--white)] mb-2">{brand.name}</h3>
                <div className="space-y-2">
                  {brand.engagements.map((eng) => (
                    <div key={eng.id} className="bg-[var(--black)] rounded p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium">{eng.name}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${
                            eng.type === 'retainer' ? 'bg-blue-600' : 'bg-[var(--success)]'
                          }`}
                        >
                          {eng.type}
                        </span>
                      </div>
                      <div className="text-sm text-[var(--grey-light)]">
                        {eng.started_at && <span>Started: {formatDate(eng.started_at)}</span>}
                        {eng.completed_at && (
                          <span className="ml-4">Completed: {formatDate(eng.completed_at)}</span>
                        )}
                      </div>
                      <div className="text-sm mt-1">
                        <span className="text-[var(--grey-light)]">Invoiced:</span>{' '}
                        {formatCurrency(eng.total_invoiced)}
                        <span className="text-[var(--grey-light)] ml-4">Paid:</span>{' '}
                        {formatCurrency(eng.total_paid)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--grey-light)]">No engagement history</div>
        )}
      </div>

      {/* Invoice History (§4.3) */}
      <div className="bg-[var(--grey-dim)] rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">Invoice History</h2>

        {client.invoices?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--grey)]">
                <tr>
                  <th className="text-left p-3">Invoice</th>
                  <th className="text-left p-3">Issue Date</th>
                  <th className="text-right p-3">Amount</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Paid Date</th>
                </tr>
              </thead>
              <tbody>
                {client.invoices.map((inv) => (
                  <tr key={inv.id} className="border-t border-[var(--grey)]">
                    <td className="p-3">{inv.number}</td>
                    <td className="p-3">{formatDate(inv.issue_date)}</td>
                    <td className="p-3 text-right">{formatCurrency(inv.amount)}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          inv.status === 'paid'
                            ? 'bg-[var(--success)]'
                            : inv.status === 'overdue'
                              ? 'bg-[var(--danger)]'
                              : 'bg-[var(--grey-light)]'
                        }`}
                      >
                        {inv.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3">{formatDate(inv.paid_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--grey-light)]">No invoices</div>
        )}
      </div>
    </div>
  );
}

export default RecentlyActiveDrilldown;
