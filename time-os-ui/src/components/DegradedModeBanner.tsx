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

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {state.isOffline ? (
            <span className="text-yellow-800">
              📡 You&apos;re offline. Showing last known data.
            </span>
          ) : (
            <span className="text-yellow-800">
              ⚠️ Some requests failed. Showing last known data.
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-yellow-700 hover:text-yellow-900 text-sm underline"
          >
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
          <button
            onClick={handleRetry}
            className="bg-yellow-200 hover:bg-yellow-300 text-yellow-800 px-3 py-1 rounded text-sm"
          >
            Retry
          </button>
          <button
            onClick={handleDismiss}
            className="text-yellow-600 hover:text-yellow-800 text-sm"
          >
            Dismiss
          </button>
        </div>
      </div>

      {showDetails && state.failedRequests.length > 0 && (
        <div className="mt-3 bg-yellow-100 rounded p-3 text-sm">
          <div className="font-medium text-yellow-800 mb-2">Failed Requests:</div>
          <ul className="space-y-1">
            {state.failedRequests.map((req, i) => (
              <li key={i} className="text-yellow-700 font-mono text-xs">
                [{req.errorCode}] {req.url}
                <span className="text-yellow-500 ml-2">
                  request_id: {req.requestId}
                </span>
              </li>
            ))}
          </ul>
          {state.lastSuccessfulSync && (
            <div className="mt-2 text-yellow-600">
              Last successful sync: {new Date(state.lastSuccessfulSync).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
