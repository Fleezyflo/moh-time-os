/**
 * DimensionBar — Horizontal bar showing a score dimension with threshold marker
 */

type Status = 'critical' | 'warning' | 'watch' | 'healthy' | 'strong';

interface DimensionBarProps {
  label: string;
  value: number;
  threshold?: number | null;
  status?: Status;
  showValue?: boolean;
}

const FILL_COLORS: Record<Status, string> = {
  critical: 'bg-red-500',
  warning: 'bg-amber-500',
  watch: 'bg-[var(--grey-muted)]',
  healthy: 'bg-green-500',
  strong: 'bg-emerald-500',
};

const VALUE_COLORS: Record<Status, string> = {
  critical: 'text-red-400',
  warning: 'text-amber-400',
  watch: 'text-[var(--grey-light)]',
  healthy: 'text-green-400',
  strong: 'text-emerald-400',
};

export function DimensionBar({
  label,
  value = 0,
  threshold,
  status = 'healthy',
  showValue = true,
}: DimensionBarProps) {
  const clampedValue = Math.max(0, Math.min(100, value));

  return (
    <div className="grid grid-cols-[120px_1fr_40px] gap-2 items-center py-1">
      <span className="text-sm text-[var(--grey-light)] text-right truncate">{label}</span>
      <div className="relative h-2 bg-[var(--grey)]/50 rounded-full overflow-visible">
        <div
          className={`h-full rounded-full transition-all ${FILL_COLORS[status]}`}
          style={{ width: `${clampedValue}%` }}
        />
        {threshold != null && (
          <div
            className="absolute -top-0.5 w-0.5 h-3 bg-white rounded-sm"
            style={{
              left: `${Math.max(0, Math.min(100, threshold))}%`,
              transform: 'translateX(-50%)',
            }}
            title={`Threshold: ${threshold}`}
          />
        )}
      </div>
      {showValue && (
        <span className={`text-sm font-semibold text-right ${VALUE_COLORS[status]}`}>
          {Math.round(value)}
        </span>
      )}
    </div>
  );
}
