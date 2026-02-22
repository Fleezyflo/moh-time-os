import { type ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  message?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  icon,
  title,
  message,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-[var(--space-3xl)] px-[var(--space-lg)] text-center ${className}`}
    >
      {icon && (
        <div className="mb-[var(--space-lg)] text-4xl text-[var(--grey-light)]">
          {icon}
        </div>
      )}
      <h3 className="text-headline-3 text-[var(--white)] mb-[var(--space-sm)]">
        {title}
      </h3>
      {message && (
        <p className="text-body-small text-[var(--grey-light)] mb-[var(--space-lg)] max-w-md">
          {message}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-[var(--space-lg)] py-[var(--space-md)] bg-[var(--accent)] text-[var(--black)] rounded-[var(--radius-sm)] font-medium text-body-small hover:brightness-110 transition-all"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
