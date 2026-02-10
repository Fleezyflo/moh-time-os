// ConfidenceBadge — displays confidence level for various metrics

interface ConfidenceBadgeProps {
  type: 'linkage' | 'interpretation' | 'load' | 'health';
  value: number | null | undefined;
}

export function ConfidenceBadge({ type, value }: ConfidenceBadgeProps) {
  if (value === null || value === undefined) {
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-400">
        {type}: —
      </span>
    );
  }

  const pct = value * 100;
  const color = pct >= 70 ? 'text-green-400 bg-green-900/30' :
                pct >= 50 ? 'text-amber-400 bg-amber-900/30' :
                'text-red-400 bg-red-900/30';

  return (
    <span className={`px-2 py-0.5 rounded text-xs ${color}`}>
      {type}: {pct.toFixed(0)}%
    </span>
  );
}
