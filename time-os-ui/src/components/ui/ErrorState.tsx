
interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Error',
  message,
  onRetry,
  className = '',
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-[var(--space-3xl)] px-[var(--space-lg)] gap-[var(--space-lg)] ${className}`}
    >
      <div className="text-4xl text-[var(--danger)]">⚠️</div>
      <div className="text-center">
        <h3 className="text-headline-3 text-[var(--white)] mb-[var(--space-sm)]">
          {title}
        </h3>
        <p className="text-body-small text-[var(--grey-light)] max-w-md">
          {message}
        </p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-[var(--space-lg)] py-[var(--space-md)] bg-[var(--accent)] text-[var(--black)] rounded-[var(--radius-sm)] font-medium text-body-small hover:brightness-110 transition-all"
        >
          Retry
        </button>
      )}
    </div>
  );
}
