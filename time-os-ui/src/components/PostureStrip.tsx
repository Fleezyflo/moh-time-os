// PostureStrip — displays health/relationship status

interface PostureStripProps {
  health: 'excellent' | 'good' | 'fair' | 'poor' | 'critical' | null | undefined;
  size?: 'sm' | 'md';
}

const healthConfig: Record<string, { icon: string; color: string; bg: string; text: string }> = {
  excellent: { icon: '✓', color: 'text-green-400', bg: 'bg-green-500/10', text: 'Excellent' },
  good: { icon: '✓', color: 'text-green-500', bg: 'bg-green-500/10', text: 'Good' },
  fair: { icon: '◐', color: 'text-amber-400', bg: 'bg-amber-500/10', text: 'Fair' },
  poor: { icon: '⚠️', color: 'text-orange-400', bg: 'bg-orange-500/10', text: 'Poor' },
  critical: { icon: '🔴', color: 'text-red-400', bg: 'bg-red-500/10', text: 'Critical' },
};

export function PostureStrip({ health, size = 'sm' }: PostureStripProps) {
  if (!health) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${size === 'sm' ? 'text-xs' : 'text-sm'} bg-[var(--grey)] text-[var(--grey-light)]`}
      >
        <span>◯</span>
        <span>Unknown</span>
      </span>
    );
  }

  const config = healthConfig[health] || healthConfig.fair;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${size === 'sm' ? 'text-xs' : 'text-sm'} ${config.bg} ${config.color}`}
    >
      <span>{config.icon}</span>
      <span>{config.text}</span>
    </span>
  );
}
