interface LoadingStateProps {
  message?: string;
  variant?: 'skeleton' | 'spinner';
  className?: string;
}

export function LoadingState({ message, variant = 'skeleton', className = '' }: LoadingStateProps) {
  if (variant === 'spinner') {
    return (
      <div
        className={`flex flex-col items-center justify-center py-[var(--space-3xl)] px-[var(--space-lg)] gap-[var(--space-lg)] ${className}`}
      >
        <div
          className="w-8 h-8 border-2 border-[var(--grey)] border-t-[var(--accent)] rounded-full animate-spin"
          aria-label="Loading"
        />
        {message && <p className="text-body-small text-[var(--grey-light)]">{message}</p>}
      </div>
    );
  }

  return (
    <div className={`space-y-[var(--space-lg)] ${className}`}>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-12 bg-[var(--grey-dim)] rounded-[var(--radius-md)] animate-pulse"
        />
      ))}
    </div>
  );
}
