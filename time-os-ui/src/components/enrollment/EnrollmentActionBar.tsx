// EnrollmentActionBar — bulk actions + Xero sync + propose (Phase 12)
import { useState } from 'react';

interface EnrollmentActionBarProps {
  onSyncXero: () => void;
  onPropose: (name: string, clientId?: string, type?: string) => void;
  syncLoading?: boolean;
}

export function EnrollmentActionBar({
  onSyncXero,
  onPropose,
  syncLoading = false,
}: EnrollmentActionBarProps) {
  const [showPropose, setShowPropose] = useState(false);
  const [proposeName, setProposeName] = useState('');
  const [proposeClientId, setProposeClientId] = useState('');
  const [proposeType, setProposeType] = useState('retainer');

  const handlePropose = () => {
    if (!proposeName.trim()) return;
    onPropose(proposeName.trim(), proposeClientId.trim() || undefined, proposeType);
    setProposeName('');
    setProposeClientId('');
    setProposeType('retainer');
    setShowPropose(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        onClick={onSyncXero}
        disabled={syncLoading}
        className="px-3 py-1.5 text-sm font-medium rounded bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white transition-colors disabled:opacity-50"
        aria-label="Sync Xero data"
      >
        {syncLoading ? 'Syncing...' : 'Sync Xero'}
      </button>

      {!showPropose ? (
        <button
          onClick={() => setShowPropose(true)}
          className="px-3 py-1.5 text-sm font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--white)] transition-colors"
          aria-label="Propose new project"
        >
          + Propose Project
        </button>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="text"
            value={proposeName}
            onChange={(e) => setProposeName(e.target.value)}
            placeholder="Project name"
            className="px-2 py-1.5 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] placeholder:text-[var(--grey-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            onKeyDown={(e) => {
              if (e.key === 'Enter') handlePropose();
              if (e.key === 'Escape') setShowPropose(false);
            }}
            autoFocus
          />
          <input
            type="text"
            value={proposeClientId}
            onChange={(e) => setProposeClientId(e.target.value)}
            placeholder="Client ID (optional)"
            className="px-2 py-1.5 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] placeholder:text-[var(--grey-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] w-36"
          />
          <select
            value={proposeType}
            onChange={(e) => setProposeType(e.target.value)}
            className="px-2 py-1.5 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="retainer">Retainer</option>
            <option value="project">Project</option>
          </select>
          <button
            onClick={handlePropose}
            disabled={!proposeName.trim()}
            className="px-3 py-1.5 text-sm font-medium rounded bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-50"
          >
            Create
          </button>
          <button
            onClick={() => setShowPropose(false)}
            className="px-3 py-1.5 text-sm font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--grey-light)] transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

export default EnrollmentActionBar;
