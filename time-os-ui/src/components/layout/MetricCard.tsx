/**
 * MetricCard — Single metric display for SummaryGrid.
 *
 * Shows label + value + optional trend indicator.
 * Uses .metric-card CSS classes from tokens.css.
 */

interface MetricCardProps {
  /** Metric label (e.g., "Total Items") */
  label: string;
  /** Metric value (e.g., 42 or "98%") */
  value: string | number;
  /** Optional trend direction */
  trend?: 'up' | 'down' | 'stable';
  /** Optional trend text (e.g., "+12% from last week") */
  trendText?: string;
  /** Optional severity coloring for the value */
  severity?: 'danger' | 'warning' | 'success' | 'info';
}

const severityColors: Record<string, string> = {
  danger: 'var(--danger)',
  warning: 'var(--warning)',
  success: 'var(--success)',
  info: 'var(--info)',
};

export function MetricCard({ label, value, trend, trendText, severity }: MetricCardProps) {
  const valueColor = severity ? severityColors[severity] : 'var(--white)';
  const trendClass = trend ? `metric-card__trend metric-card__trend--${trend}` : '';

  return (
    <div className="card metric-card">
      <span className="metric-card__label">{label}</span>
      <span className="metric-card__value" style={{ color: valueColor }}>
        {value}
      </span>
      {trend && trendText && <span className={trendClass}>{trendText}</span>}
    </div>
  );
}
