// Governance domain cards — mode, threshold, actions per domain
import { useState, useCallback } from 'react';
import type { GovernanceDomain } from '../../lib/api';
import { setGovernanceMode, setGovernanceThreshold } from '../../lib/api';

const MODE_LABELS: Record<string, { label: string; color: string }> = {
  observe: { label: 'Observe', color: 'bg-slate-600' },
  advise: { label: 'Advise', color: 'bg-blue-600' },
  guard: { label: 'Guard', color: 'bg-amber-600' },
  enforce: { label: 'Enforce', color: 'bg-red-600' },
};

const MODES = ['observe', 'advise', 'guard', 'enforce'];

interface Props {
  domains: GovernanceDomain[];
  onRefresh: () => void;
}

export function GovernanceDomainCards({ domains, onRefresh }: Props) {
  const [editingDomain, setEditingDomain] = useState<string | null>(null);
  const [pendingThreshold, setPendingThreshold] = useState<number>(0.5);

  const handleModeChange = useCallback(
    async (domain: string, mode: string) => {
      await setGovernanceMode(domain, mode);
      onRefresh();
    },
    [onRefresh]
  );

  const handleThresholdSave = useCallback(
    async (domain: string) => {
      await setGovernanceThreshold(domain, pendingThreshold);
      setEditingDomain(null);
      onRefresh();
    },
    [onRefresh, pendingThreshold]
  );

  if (domains.length === 0) {
    return (
      <div className="text-sm text-[var(--grey-light)]">No governance domains configured.</div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {domains.map((d) => {
        const modeInfo = MODE_LABELS[d.mode] ?? { label: d.mode, color: 'bg-slate-600' };
        return (
          <div
            key={d.domain}
            className="bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl p-4 space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm capitalize">{d.domain}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full text-white ${modeInfo.color}`}>
                {modeInfo.label}
              </span>
            </div>

            {/* Mode selector */}
            <div className="flex gap-1">
              {MODES.map((m) => (
                <button
                  key={m}
                  onClick={() => handleModeChange(d.domain, m)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${
                    d.mode === m
                      ? 'bg-[var(--accent)] text-white'
                      : 'bg-[var(--grey)] hover:bg-[var(--grey-light)]'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            {/* Threshold */}
            <div className="text-xs text-[var(--grey-light)]">
              Threshold:{' '}
              {editingDomain === d.domain ? (
                <span className="inline-flex items-center gap-1">
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={pendingThreshold}
                    onChange={(e) => setPendingThreshold(Number(e.target.value))}
                    className="w-16 bg-[var(--grey)] rounded px-1 py-0.5 text-xs"
                  />
                  <button
                    onClick={() => handleThresholdSave(d.domain)}
                    className="text-[var(--accent)] hover:underline"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingDomain(null)}
                    className="text-[var(--grey-light)] hover:underline"
                  >
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => {
                    setPendingThreshold(d.confidence_threshold);
                    setEditingDomain(d.domain);
                  }}
                  className="hover:text-white transition-colors"
                >
                  {d.confidence_threshold.toFixed(2)}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
