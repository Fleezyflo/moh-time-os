/**
 * HealthScore — Large score display with 5-level color coding.
 *
 * Score bands:
 *   >= 70  strong   (green)
 *   >= 50  fair     (blue/teal)
 *   >= 30  warning  (amber)
 *   >= 10  poor     (orange)
 *   <  10  critical (red)
 *   null   unknown  (grey, shows "—")
 */

interface HealthScoreProps {
  score: number | null | undefined;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  showTrend?: boolean;
  trend?: 'up' | 'down' | 'stable';
  computedAt?: string;
  /** When true, show "(provisional)" qualifier */
  provisional?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-green-400';
  if (score >= 50) return 'text-teal-400';
  if (score >= 30) return 'text-amber-400';
  if (score >= 10) return 'text-orange-400';
  return 'text-red-400';
}

function scoreBg(score: number): string {
  if (score >= 70) return 'bg-green-500/10';
  if (score >= 50) return 'bg-teal-500/10';
  if (score >= 30) return 'bg-amber-500/10';
  if (score >= 10) return 'bg-orange-500/10';
  return 'bg-red-500/10';
}

function freshnessLabel(computedAt: string): string {
  const diff = Date.now() - new Date(computedAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function HealthScore({
  score,
  label,
  size = 'lg',
  showTrend = false,
  trend = 'stable',
  computedAt,
  provisional = false,
}: HealthScoreProps) {
  const sizeClasses = {
    sm: 'text-2xl',
    md: 'text-4xl',
    lg: 'text-5xl',
  };

  const trendIcon = {
    up: '↑',
    down: '↓',
    stable: '→',
  };

  const trendColor = {
    up: 'text-green-400',
    down: 'text-red-400',
    stable: 'text-[var(--grey-light)]',
  };

  // Handle null/undefined score: show unknown state
  if (score == null) {
    return (
      <div className="bg-[var(--grey)]/10 rounded-lg p-6 text-center">
        <div className={`${sizeClasses[size]} font-bold text-[var(--grey-light)]`}>—</div>
        <div className="text-[var(--grey)] mt-2">Score unavailable</div>
        {label && <div className="text-[var(--grey-light)] mt-1">{label}</div>}
      </div>
    );
  }

  const color = scoreColor(score);
  const bgColor = scoreBg(score);

  return (
    <div className={`${bgColor} rounded-lg p-6 text-center`}>
      <div className="flex items-center justify-center gap-2">
        <span className={`${sizeClasses[size]} font-bold ${color}`}>{Math.round(score)}</span>
        {showTrend && <span className={`text-xl ${trendColor[trend]}`}>{trendIcon[trend]}</span>}
      </div>
      {provisional && (
        <div className="text-xs text-[var(--warning)] mt-1">provisional — incomplete data</div>
      )}
      {label && <div className="text-[var(--grey-light)] mt-2">{label}</div>}
      {computedAt && (
        <div className="text-xs text-[var(--grey)] mt-1">Updated {freshnessLabel(computedAt)}</div>
      )}
    </div>
  );
}

export default HealthScore;
