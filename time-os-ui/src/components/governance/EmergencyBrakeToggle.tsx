// Emergency brake toggle with reason input
import { useState, useCallback } from 'react';
import { activateEmergencyBrake, releaseEmergencyBrake } from '../../lib/api';

interface Props {
  active: boolean;
  onRefresh: () => void;
}

export function EmergencyBrakeToggle({ active, onRefresh }: Props) {
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  const handleActivate = useCallback(async () => {
    if (!reason.trim()) return;
    setLoading(true);
    try {
      await activateEmergencyBrake(reason.trim());
      setReason('');
      onRefresh();
    } finally {
      setLoading(false);
    }
  }, [reason, onRefresh]);

  const handleRelease = useCallback(async () => {
    setLoading(true);
    try {
      await releaseEmergencyBrake();
      onRefresh();
    } finally {
      setLoading(false);
    }
  }, [onRefresh]);

  return (
    <div
      className={`border rounded-xl p-4 space-y-3 ${
        active ? 'border-red-500/50 bg-red-950/30' : 'border-[var(--grey)] bg-[var(--grey-dim)]'
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-sm">Emergency Brake</h3>
          <p className="text-xs text-[var(--grey-light)]">
            {active
              ? 'Brake is ACTIVE — all autonomous actions are paused'
              : 'System is running normally'}
          </p>
        </div>
        <span
          className={`w-3 h-3 rounded-full ${active ? 'bg-red-500 animate-pulse' : 'bg-green-500'}`}
        />
      </div>

      {active ? (
        <button
          onClick={handleRelease}
          disabled={loading}
          className="text-sm px-4 py-2 rounded-lg bg-green-700 hover:bg-green-600 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Releasing...' : 'Release Brake'}
        </button>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for activating brake..."
            className="flex-1 bg-[var(--grey)] rounded-lg px-3 py-2 text-sm placeholder:text-[var(--grey-light)]"
          />
          <button
            onClick={handleActivate}
            disabled={loading || !reason.trim()}
            className="text-sm px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Activating...' : 'Activate'}
          </button>
        </div>
      )}
    </div>
  );
}
