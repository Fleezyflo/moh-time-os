// CapacityGauge — circular gauge showing utilization percentage

interface CapacityGaugeProps {
  label: string;
  value: number; // 0-100
  size?: number;
  strokeWidth?: number;
}

function gaugeColor(value: number): string {
  if (value >= 90) return 'var(--danger)';
  if (value >= 75) return 'var(--warning)';
  if (value >= 50) return 'var(--accent)';
  return 'var(--success)';
}

export function CapacityGauge({ label, value, size = 120, strokeWidth = 10 }: CapacityGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedValue = Math.max(0, Math.min(100, value));
  const offset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="transform -rotate-90"
        role="img"
        aria-label={`${label}: ${clampedValue}%`}
      >
        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--grey)"
          strokeWidth={strokeWidth}
        />
        {/* Value arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={gaugeColor(clampedValue)}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="text-center -mt-[calc(50%+10px)] mb-[calc(50%-10px)]">
        <div className="text-2xl font-bold" style={{ color: gaugeColor(clampedValue) }}>
          {clampedValue}%
        </div>
      </div>
      <div className="text-sm text-[var(--grey-light)]">{label}</div>
    </div>
  );
}
