// ConfidenceBadge — renders linkage or interpretation confidence per contract

interface ConfidenceBadgeProps {
  type: 'linkage' | 'interpretation';
  value: number;
  showLabel?: boolean;
}

export function ConfidenceBadge({ type, value, showLabel = true }: ConfidenceBadgeProps) {
  // Thresholds from 06_PROPOSALS_BRIEFINGS.md:
  // - Link confidence gate: ≥ 0.70
  // - Interpretation confidence gate: ≥ 0.55
  const threshold = type === 'linkage' ? 0.70 : 0.55;
  const passes = value >= threshold;
  
  const getLevel = () => {
    if (value == null) return { level: 'unknown', color: 'bg-slate-500', text: '—' };
    if (value >= 0.80) return { level: 'high', color: 'bg-green-500', text: 'High' };
    if (value >= 0.60) return { level: 'medium', color: 'bg-amber-500', text: 'Med' };
    return { level: 'low', color: 'bg-red-500', text: 'Low' };
  };
  
  const { color, text } = getLevel();
  const icon = type === 'linkage' ? '🔗' : '💡';
  const label = type === 'linkage' ? 'Link' : 'Hyp';
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs ${passes ? 'bg-slate-700' : 'bg-slate-800 border border-red-500/30'}`}>
      <span>{icon}</span>
      {showLabel && <span className="text-slate-400">{label}:</span>}
      <span className={`w-2 h-2 rounded-full ${color}`}></span>
      <span className="text-slate-200">{value != null ? (value * 100).toFixed(0) + '%' : text}</span>
      {passes ? <span className="text-green-400">✓</span> : <span className="text-red-400">✗</span>}
    </span>
  );
}
