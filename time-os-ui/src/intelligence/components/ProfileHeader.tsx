/**
 * ProfileHeader — Consistent header for all entity profile views
 * 
 * Visual structure:
 * ┌──────────────────────────────────────────────────────────────────────┐
 * │ [Entity Type Pill]  Entity Name                          [Actions]  │
 * │ [Score]  CLASSIFICATION  [Trend]                                    │
 * │                                                                      │
 * │ Stat: value   |   Stat: value   |   Stat: value   |   Stat: value   │
 * │                                                                      │
 * │ ⚠ [SeverityBadge] Primary signal headline                           │
 * └──────────────────────────────────────────────────────────────────────┘
 */

import type { ReactNode } from 'react';
import { HealthScore } from './HealthScore';
import { SeverityBadge } from './Badges';

type EntityType = 'client' | 'person' | 'project';
type Classification = 'CRITICAL' | 'AT_RISK' | 'STABLE' | 'HEALTHY' | 'STRONG' | string;
type TrendDirection = 'increasing' | 'declining' | 'stable';

interface Signal {
  severity: 'critical' | 'warning' | 'watch';
  headline: string;
}

interface Trend {
  direction: TrendDirection;
  magnitude: number;
}

interface ProfileHeaderProps {
  entityType: EntityType;
  name: string;
  score?: number | null;
  classification?: Classification | null;
  primarySignal?: Signal | null;
  quickStats?: Record<string, string | number>;
  trend?: Trend | null;
  actions?: ReactNode;
}

const TYPE_PILL_STYLES: Record<EntityType, string> = {
  client: 'bg-blue-500/20 text-blue-400',
  person: 'bg-purple-500/20 text-purple-400',
  project: 'bg-emerald-500/20 text-emerald-400',
};

const CLASSIFICATION_STYLES: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400',
  'at-risk': 'bg-amber-500/20 text-amber-400',
  stable: 'bg-slate-500/20 text-slate-400',
  healthy: 'bg-green-500/20 text-green-400',
  strong: 'bg-emerald-500/20 text-emerald-400',
};

const TREND_ICONS: Record<TrendDirection, string> = {
  increasing: '↑',
  declining: '↓',
  stable: '→',
};

const TREND_COLORS: Record<TrendDirection, string> = {
  increasing: 'text-green-400',
  declining: 'text-red-400',
  stable: 'text-slate-400',
};

export function ProfileHeader({
  entityType,
  name,
  score,
  classification,
  primarySignal,
  quickStats = {},
  trend,
  actions,
}: ProfileHeaderProps) {
  const statEntries = Object.entries(quickStats);
  const classKey = classification?.toLowerCase().replace('_', '-') || '';

  return (
    <div className="p-5 bg-slate-800 border border-slate-700 rounded-lg mb-6">
      {/* Row 1: type pill + name + actions */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide whitespace-nowrap ${TYPE_PILL_STYLES[entityType]}`}
          >
            {entityType}
          </span>
          <h1 className="text-xl font-bold text-white truncate">
            {name || '—'}
          </h1>
        </div>
        {actions && <div className="flex gap-2 flex-shrink-0">{actions}</div>}
      </div>

      {/* Row 2: score + classification + trend */}
      <div className="flex items-center gap-3 mb-4">
        {score != null && (
          <HealthScore score={score} size="md" />
        )}
        {classification && (
          <span
            className={`text-sm font-semibold px-2 py-0.5 rounded ${CLASSIFICATION_STYLES[classKey] || 'bg-slate-700 text-slate-300'}`}
          >
            {classification.replace('_', ' ')}
          </span>
        )}
        {trend && (
          <span className={`flex items-center gap-1 text-sm ${TREND_COLORS[trend.direction]}`}>
            <span>{TREND_ICONS[trend.direction]}</span>
            <span>{Math.abs(trend.magnitude).toFixed(1)}%</span>
          </span>
        )}
      </div>

      {/* Row 3: quick stats */}
      {statEntries.length > 0 && (
        <div className="flex items-center gap-3 flex-wrap pb-3 border-b border-slate-700/50">
          {statEntries.map(([label, value], i) => (
            <div key={label} className="flex items-center gap-3">
              {i > 0 && <span className="w-px h-5 bg-slate-700" />}
              <div className="text-sm">
                <span className="text-slate-400">{label}: </span>
                <span className="text-white font-medium">{value}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Row 4: primary signal banner */}
      {primarySignal && (
        <div className="flex items-center gap-2 pt-3">
          <SeverityBadge severity={primarySignal.severity} />
          <span className="text-sm text-slate-300">{primarySignal.headline}</span>
        </div>
      )}
    </div>
  );
}
