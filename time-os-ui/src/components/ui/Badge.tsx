import React from 'react';

export type BadgeVariant = 'status' | 'tier' | 'priority';
export type BadgeStatus = 'success' | 'warning' | 'danger' | 'info' | 'neutral';
export type BadgeTier = 'platinum' | 'gold' | 'silver' | 'bronze' | 'none';
export type BadgePriority = 'high' | 'medium' | 'low' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  status?: BadgeStatus;
  tier?: BadgeTier;
  priority?: BadgePriority;
  children: React.ReactNode;
  className?: string;
}

const statusStyles: Record<BadgeStatus, string> = {
  success: 'bg-[rgba(0,255,136,0.2)] text-[var(--success)]',
  warning: 'bg-[rgba(255,204,0,0.2)] text-[var(--warning)]',
  danger: 'bg-[rgba(255,61,0,0.2)] text-[var(--danger)]',
  info: 'bg-[rgba(10,132,255,0.2)] text-[var(--info)]',
  neutral: 'bg-[rgba(85,85,85,0.2)] text-[var(--grey-light)]',
};

const tierStyles: Record<BadgeTier, string> = {
  platinum: 'bg-purple-500 text-[var(--white)]',
  gold: 'bg-yellow-500 text-[var(--black)]',
  silver: 'bg-slate-400 text-[var(--black)]',
  bronze: 'bg-orange-700 text-[var(--white)]',
  none: 'bg-[var(--grey-dim)] text-[var(--grey-light)]',
};

const priorityStyles: Record<BadgePriority, string> = {
  high: 'bg-[rgba(255,61,0,0.2)] text-[var(--danger)]',
  medium: 'bg-[rgba(255,204,0,0.2)] text-[var(--warning)]',
  low: 'bg-[rgba(0,255,136,0.2)] text-[var(--success)]',
  info: 'bg-[rgba(10,132,255,0.2)] text-[var(--info)]',
};

export function Badge({
  variant = 'status',
  status,
  tier,
  priority,
  children,
  className = '',
}: BadgeProps) {
  const baseStyles =
    'inline-block px-[var(--space-sm)] py-[var(--space-xs)] rounded-[var(--radius-sm)] font-medium text-micro whitespace-nowrap';

  let typeStyles = '';

  if (variant === 'status' && status) {
    typeStyles = statusStyles[status];
  } else if (variant === 'tier' && tier) {
    typeStyles = tierStyles[tier];
  } else if (variant === 'priority' && priority) {
    typeStyles = priorityStyles[priority];
  } else {
    typeStyles = statusStyles.neutral;
  }

  return <span className={`${baseStyles} ${typeStyles} ${className}`}>{children}</span>;
}
