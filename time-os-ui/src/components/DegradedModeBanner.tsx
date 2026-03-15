/**
 * Degraded Mode Banner Component
 *
 * Shows when the app is offline or has failed requests.
 * Includes request_id for debugging.
 */

import { useState, useEffect } from 'react';
import { getDegradedState, isInDegradedMode, clearFailures } from '../lib/offline';

export function DegradedModeBanner() {
  const [state, setState] = useState(getDegradedState());
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    // Poll for state changes
    const interval = setInterval(() => {
      setState(getDegradedState());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  if (!isInDegradedMode()) {
    return null;
  }

  const handleRetry = () => {
    clearFailures();
    window.location.reload();
  };

  const handleDismiss = () => {
    clearFailures();
  };

  // Use red for offline (system broken), amber for partial failures
  const isOffline = state.isOffline;
  const borderColor = isOffline ? 'border-red-400' : 'border-amber-400';
  const bgColor = isOffline ? 'bg-red-500/10' : 'bg-amber-500/10';
  const textColor = isOffline ? 'text-red-300' : 'text-amber-300';
  const detailBg = isOffline ? 'bg-red-900/20' : 'bg-amber-900/20';
  const btnBg = isOffline
    ? 'bg-red-500/20 hover:bg-red-500/30 text-red-300'
    : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300';

  return (
    <div className={`${bgColor} border-b ${borderColor} px-4 py-3`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isOffline ? (
            <span className={textColor}>
              🔴 Offline — all data below is stale. Decisions may be based on outdated information.
            </span>
          ) : (
            <span className={textColor}>
              ⚠️ {state.failedRequests.length} request{state.failedRequests.length !== 1 ? 's' : ''}{' '}
              failed — some data below may be stale.
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className={`${textColor} hover:text-white text-sm underline`}
          >
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
          <button onClick={handleRetry} className={`${btnBg} px-3 py-1 rounded text-sm`}>
            Retry
          </button>
          <button onClick={handleDismiss} className={`${textColor} hover:text-white text-sm`}>
            Dismiss
          </button>
        </div>
      </div>

      {showDetails && state.failedRequests.length > 0 && (
        <div className={`mt-3 ${detailBg} rounded p-3 text-sm`}>
          <div className={`font-medium ${textColor} mb-2`}>Failed Requests:</div>
          <ul className="space-y-1">
            {state.failedRequests.map((req, i) => (
              <li key={i} className="text-[var(--grey-light)] font-mono text-xs">
                [{req.errorCode}] {req.url}
                <span className="text-[var(--grey)] ml-2">request_id: {req.requestId}</span>
              </li>
            ))}
          </ul>
          {state.lastSuccessfulSync && (
            <div className="mt-2 text-[var(--grey-light)]">
              Last successful sync: {new Date(state.lastSuccessfulSync).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
