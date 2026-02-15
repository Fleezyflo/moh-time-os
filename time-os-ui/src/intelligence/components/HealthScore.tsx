/**
 * HealthScore — Large score display with color coding
 */

interface HealthScoreProps {
  score: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  showTrend?: boolean;
  trend?: 'up' | 'down' | 'stable';
}

export function HealthScore({ 
  score, 
  label, 
  size = 'lg',
  showTrend = false,
  trend = 'stable'
}: HealthScoreProps) {
  const color = score >= 60 ? 'text-green-400' : score >= 30 ? 'text-amber-400' : 'text-red-400';
  const bgColor = score >= 60 ? 'bg-green-500/10' : score >= 30 ? 'bg-amber-500/10' : 'bg-red-500/10';
  
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
    stable: 'text-slate-400',
  };
  
  return (
    <div className={`${bgColor} rounded-lg p-6 text-center`}>
      <div className="flex items-center justify-center gap-2">
        <span className={`${sizeClasses[size]} font-bold ${color}`}>
          {Math.round(score)}
        </span>
        {showTrend && (
          <span className={`text-xl ${trendColor[trend]}`}>
            {trendIcon[trend]}
          </span>
        )}
      </div>
      {label && (
        <div className="text-slate-400 mt-2">{label}</div>
      )}
    </div>
  );
}

export default HealthScore;
