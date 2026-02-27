/**
 * Badge components for severity and urgency indicators
 */

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
}

// Base badge
function Badge({ children, className = '' }: BadgeProps) {
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${className}`}>{children}</span>;
}

// Severity badge (critical/warning/watch)
export function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-400 border border-red-500/30',
    warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    watch:
      'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border border-[var(--grey-muted)]/30',
  };

  return <Badge className={colors[severity] || colors.watch}>{severity}</Badge>;
}

// Urgency badge (immediate/this_week/monitor)
export function UrgencyBadge({ urgency }: { urgency: string }) {
  const colors: Record<string, string> = {
    immediate: 'bg-red-500/20 text-red-400 border border-red-500/30',
    this_week: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    monitor:
      'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border border-[var(--grey-muted)]/30',
  };

  const labels: Record<string, string> = {
    immediate: 'Immediate',
    this_week: 'This Week',
    monitor: 'Monitor',
  };

  return <Badge className={colors[urgency] || colors.monitor}>{labels[urgency] || urgency}</Badge>;
}

// Pattern type badge
export function PatternTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    concentration: 'bg-purple-500/20 text-purple-400',
    cascade: 'bg-orange-500/20 text-orange-400',
    degradation: 'bg-pink-500/20 text-pink-400',
    drift: 'bg-blue-500/20 text-blue-400',
    correlation: 'bg-cyan-500/20 text-cyan-400',
  };

  return (
    <Badge className={colors[type] || 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)]'}>
      {type}
    </Badge>
  );
}

// Pattern severity badge
export function PatternSeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    structural: 'bg-red-500/20 text-red-400',
    operational: 'bg-amber-500/20 text-amber-400',
    informational: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)]',
  };

  return <Badge className={colors[severity] || colors.informational}>{severity}</Badge>;
}

// Signal category badge
export function CategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    threshold: 'bg-blue-500/20 text-blue-400',
    trend: 'bg-purple-500/20 text-purple-400',
    anomaly: 'bg-orange-500/20 text-orange-400',
    compound: 'bg-pink-500/20 text-pink-400',
  };

  return (
    <Badge className={colors[category] || 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)]'}>
      {category}
    </Badge>
  );
}

// Count badge (for summary displays)
export function CountBadge({ count, severity }: { count: number; severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/50',
    warning: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
    watch: 'bg-[var(--grey-muted)]/20 text-[var(--grey-light)] border-[var(--grey-muted)]/50',
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm border ${colors[severity] || colors.watch}`}>
      {count} {severity}
    </span>
  );
}
