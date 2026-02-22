import { type ReactNode } from 'react';

export type CardVariant = 'default' | 'raised' | 'bordered' | 'ghost';
export type CardSeverity = 'danger' | 'warning' | 'success' | 'info' | 'none';

interface CardProps {
  children: ReactNode;
  variant?: CardVariant;
  severity?: CardSeverity;
  className?: string;
}

const severityStyles: Record<CardSeverity, string> = {
  danger: 'ring-2 ring-[var(--danger)]',
  warning: 'ring-2 ring-[var(--warning)]',
  success: 'ring-2 ring-[var(--success)]',
  info: 'ring-2 ring-[var(--info)]',
  none: '',
};

const variantStyles: Record<CardVariant, string> = {
  default: 'bg-[var(--grey-dim)] border border-[var(--grey)]',
  raised: 'bg-[var(--grey-dim)] border border-[var(--grey)] shadow-md',
  bordered: 'bg-transparent border border-[var(--grey)]',
  ghost: 'bg-transparent border-none shadow-none',
};

export function Card({
  children,
  variant = 'default',
  severity = 'none',
  className = '',
}: CardProps) {
  const baseStyles = 'rounded-[var(--radius-md)] p-[var(--space-lg)] transition-all';
  const ringStyles = severityStyles[severity];
  const typeStyles = variantStyles[variant];

  return <div className={`${baseStyles} ${typeStyles} ${ringStyles} ${className}`}>{children}</div>;
}
