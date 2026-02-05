// PostureStrip — shows entity posture derived from proposals

interface PostureStripProps {
  posture: 'critical' | 'attention' | 'healthy' | 'inactive';
  proposal_count: number;
  issue_count: number;
  confidence?: number;
}

const postureConfig = {
  critical: { icon: '🔴', color: 'text-red-500', bg: 'bg-red-500/10', text: 'Needs attention' },
  attention: { icon: '⚠️', color: 'text-amber-500', bg: 'bg-amber-500/10', text: 'Review recommended' },
  healthy: { icon: '✓', color: 'text-green-500', bg: 'bg-green-500/10', text: 'On track' },
  inactive: { icon: '◯', color: 'text-slate-400', bg: 'bg-slate-500/10', text: 'No recent activity' }
};

export function PostureStrip({ posture, proposal_count, issue_count, confidence }: PostureStripProps) {
  const config = postureConfig[posture];
  
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg ${config.bg}`}>
      <span className="text-lg">{config.icon}</span>
      <span className={`text-sm font-medium ${config.color}`}>{config.text}</span>
      <span className="text-slate-500">|</span>
      <span className="text-xs text-slate-400">
        {proposal_count} proposals · {issue_count} issues
      </span>
      {confidence != null && confidence < 0.70 && (
        <span className="text-xs text-amber-400 ml-auto">⚠️ Weak linkage</span>
      )}
    </div>
  );
}
