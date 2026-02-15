/**
 * ProfileSection — Titled content section within an entity profile
 * 
 * Provides consistent section layout with:
 * - Title with optional badge and actions
 * - Optional description
 * - Loading skeleton state
 * - Collapsible support
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { SkeletonCard, SkeletonRow } from '../../components/Skeleton';

type SkeletonType = 'card' | 'row' | 'metric' | 'chart';

interface ProfileSectionProps {
  title: string;
  description?: string | null;
  loading?: boolean;
  skeletonType?: SkeletonType;
  skeletonCount?: number;
  children: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

function MetricSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-3 w-16 bg-slate-700/50 rounded mb-1" />
      <div className="h-6 w-24 bg-slate-700/50 rounded" />
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="animate-pulse h-40 bg-slate-700/50 rounded" />
  );
}

export function ProfileSection({
  title,
  description,
  loading = false,
  skeletonType = 'card',
  skeletonCount = 3,
  children,
  badge,
  actions,
  collapsible = false,
  defaultCollapsed = false,
}: ProfileSectionProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const renderSkeleton = () => {
    switch (skeletonType) {
      case 'chart':
        return <ChartSkeleton />;
      case 'metric':
        return (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: skeletonCount }, (_, i) => (
              <MetricSkeleton key={i} />
            ))}
          </div>
        );
      case 'row':
        return (
          <div className="space-y-2">
            {Array.from({ length: skeletonCount }, (_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        );
      case 'card':
      default:
        return (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: skeletonCount }, (_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        );
    }
  };

  return (
    <div className="mb-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {collapsible && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="text-slate-400 hover:text-white transition-colors"
              aria-label={collapsed ? 'Expand section' : 'Collapse section'}
            >
              {collapsed ? '▶' : '▼'}
            </button>
          )}
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          {badge}
        </div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>

      {/* Description */}
      {description && !collapsed && (
        <p className="text-xs text-slate-500 mb-4 leading-relaxed">{description}</p>
      )}

      {/* Content */}
      {!collapsed && (
        <div className="min-h-[60px]">
          {loading ? renderSkeleton() : children}
        </div>
      )}
    </div>
  );
}
