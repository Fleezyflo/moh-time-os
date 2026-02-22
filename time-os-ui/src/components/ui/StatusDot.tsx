export type StatusDotColor = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface StatusDotProps {
  color?: StatusDotColor;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const colorMap: Record<StatusDotColor, string> = {
  success: 'bg-[var(--success)]',
  warning: 'bg-[var(--warning)]',
  danger: 'bg-[var(--danger)]',
  info: 'bg-[var(--info)]',
  neutral: 'bg-[var(--grey-light)]',
};

const sizeMap = {
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
};

export function StatusDot({ color = 'neutral', size = 'md', className = '' }: StatusDotProps) {
  return (
    <div
      className={`rounded-full ${colorMap[color]} ${sizeMap[size]} ${className}`}
      aria-hidden="true"
    />
  );
}
