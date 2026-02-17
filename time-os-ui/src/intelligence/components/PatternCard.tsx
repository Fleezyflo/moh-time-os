/**
 * PatternCard — Pattern summary card with expandable detail
 */

import { useState } from 'react';
import type { Pattern } from '../api';
import { PatternSeverityBadge, PatternTypeBadge } from './Badges';
import { EntityList } from './EntityLink';

interface PatternCardProps {
  pattern: Pattern;
  compact?: boolean;
  onClick?: () => void;
}

export function PatternCard({ pattern, compact = false, onClick }: PatternCardProps) {
  const [expanded, setExpanded] = useState(false);

  const bgColor =
    pattern.severity === 'structural'
      ? 'bg-red-500/5 border-red-500/30'
      : pattern.severity === 'operational'
        ? 'bg-amber-500/5 border-amber-500/30'
        : 'bg-slate-800 border-slate-700';

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (!compact) {
      setExpanded(!expanded);
    }
  };

  if (compact) {
    return (
      <div
        className={`rounded-lg p-3 border ${bgColor} cursor-pointer hover:border-slate-600 transition-colors`}
        onClick={handleClick}
      >
        <div className="flex items-center gap-2 mb-1">
          <PatternSeverityBadge severity={pattern.severity} />
          <PatternTypeBadge type={pattern.type} />
        </div>
        <div className="text-sm font-medium truncate">{pattern.name}</div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${bgColor}`}>
      <div className="p-3 sm:p-4 cursor-pointer" onClick={handleClick}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <PatternSeverityBadge severity={pattern.severity} />
              <PatternTypeBadge type={pattern.type} />
            </div>
            <div className="font-medium">{pattern.name}</div>
            <div className="text-sm text-slate-400 mt-1">{pattern.description}</div>
          </div>
          <div className="text-xs text-slate-500">{expanded ? '▲' : '▼'}</div>
        </div>
      </div>

      {expanded && (
        <div className="px-3 sm:px-4 pb-3 sm:pb-4 border-t border-slate-700 pt-3 sm:pt-4">
          {/* Affected entities */}
          {pattern.affected_entities && pattern.affected_entities.length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                Affected Entities ({pattern.affected_entities.length})
              </div>
              <EntityList entities={pattern.affected_entities} maxItems={8} />
            </div>
          )}

          {/* Metrics */}
          {pattern.metrics && Object.keys(pattern.metrics).length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Metrics</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(pattern.metrics).map(([key, value]) => (
                  <div key={key} className="bg-slate-700/50 rounded p-2">
                    <div className="text-xs text-slate-500">{key}</div>
                    <div className="text-sm font-medium">
                      {typeof value === 'number' ? value.toFixed(2) : String(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Implied action */}
          <div className="bg-slate-700/50 rounded p-3">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">
              Recommended Action
            </div>
            <div className="text-sm">{pattern.implied_action}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PatternCard;
