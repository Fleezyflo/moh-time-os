// Shared error state component for consistent error UI across pages
import { ApiError } from '../lib/api';

interface ErrorStateProps {
  error: Error;
  onRetry?: () => void;
  onDismiss?: () => void;
  hasData?: boolean; // If true, show non-blocking banner instead of full-page error
  className?: string;
}

function getErrorInfo(error: Error): {
  icon: string;
  title: string;
  message: string;
  canRetry: boolean;
} {
  if (error instanceof ApiError) {
    if (error.isNetworkError) {
      return {
        icon: '📡',
        title: 'Connection Error',
        message: 'Unable to connect to the server. Check your internet connection.',
        canRetry: true,
      };
    }
    if (error.isUnauthorized) {
      return {
        icon: '🔒',
        title: 'Unauthorized',
        message: 'Your session may have expired. Please refresh the page.',
        canRetry: false,
      };
    }
    if (error.isForbidden) {
      return {
        icon: '🚫',
        title: 'Access Denied',
        message: "You don't have permission to access this resource.",
        canRetry: false,
      };
    }
    if (error.isNotFound) {
      return {
        icon: '🔍',
        title: 'Not Found',
        message: 'The requested resource could not be found.',
        canRetry: false,
      };
    }
    if (error.isServerError) {
      return {
        icon: '🔥',
        title: 'Server Error',
        message: error.message || 'The server encountered an error. Please try again later.',
        canRetry: true,
      };
    }
  }
  return {
    icon: '⚠️',
    title: 'Something went wrong',
    message: error.message,
    canRetry: true,
  };
}

export function ErrorState({
  error,
  onRetry,
  onDismiss,
  hasData,
  className = '',
}: ErrorStateProps) {
  const errorInfo = getErrorInfo(error);
  // Non-blocking banner when we have stale data
  if (hasData) {
    return (
      <div
        className={`bg-amber-900/20 border border-amber-700/50 rounded-lg p-3 mb-4 flex items-center justify-between ${className}`}
      >
        <div className="flex items-center gap-2">
          <span className="text-amber-400">{errorInfo.icon}</span>
          <span className="text-sm text-amber-300">
            {errorInfo.title}: {errorInfo.message}
          </span>
        </div>
        <div className="flex gap-2">
          {onRetry && errorInfo.canRetry && (
            <button
              onClick={onRetry}
              className="px-2 py-1 text-xs bg-amber-700/50 hover:bg-amber-600/50 text-amber-200 rounded"
            >
              Retry
            </button>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="px-2 py-1 text-xs text-amber-400 hover:text-amber-300"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    );
  }

  // Blocking error state when no data available
  return (
    <div
      className={`bg-red-900/20 border border-red-700/50 rounded-lg p-8 text-center ${className}`}
    >
      <div className="text-red-400 text-2xl mb-2">{errorInfo.icon}</div>
      <div className="text-red-300 text-lg font-medium mb-2">{errorInfo.title}</div>
      <p className="text-[var(--grey-light)] text-sm mb-4">{errorInfo.message}</p>
      {onRetry && errorInfo.canRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-red-700/50 hover:bg-red-600/50 text-red-200 rounded-lg transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
