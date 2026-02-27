// Error Boundary component for catching render errors
import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-[var(--black)] flex items-center justify-center p-4">
          <div className="bg-[var(--grey-dim)] border border-red-700/50 rounded-lg p-8 max-w-md w-full text-center">
            <div className="text-red-400 text-4xl mb-4">⚠️</div>
            <h1 className="text-xl font-semibold text-[var(--white)] mb-2">Something went wrong</h1>
            <p className="text-[var(--grey-light)] text-sm mb-4">
              An unexpected error occurred. Please try reloading the page.
            </p>
            {this.state.error && (
              <details className="text-left mb-4">
                <summary className="text-[var(--grey-muted)] text-xs cursor-pointer hover:text-[var(--grey-light)]">
                  Error details
                </summary>
                <pre className="mt-2 p-2 bg-[var(--black)] rounded text-xs text-red-400 overflow-x-auto">
                  {this.state.error.message}
                </pre>
              </details>
            )}
            <div className="flex gap-2 justify-center">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--white)] text-sm rounded"
              >
                Try Again
              </button>
              <button
                onClick={this.handleReload}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm rounded"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
