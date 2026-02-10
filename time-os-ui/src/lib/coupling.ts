// Coupling strength utilities
// Centralized thresholds for consistent coupling representation

export type CouplingLevel = 'strong' | 'medium' | 'weak';

export interface CouplingThresholds {
  strong: number;
  medium: number;
  // Minimum threshold for display
  minimum: number;
}

// Default thresholds for coupling strength
export const COUPLING_THRESHOLDS: CouplingThresholds = {
  strong: 0.80,
  medium: 0.60,
  minimum: 0.50
};

// Get coupling strength level
export function couplingLevel(strength: number): CouplingLevel {
  if (strength >= COUPLING_THRESHOLDS.strong) return 'strong';
  if (strength >= COUPLING_THRESHOLDS.medium) return 'medium';
  return 'weak';
}

// Get coupling label
export function couplingLabel(strength: number): string {
  const level = couplingLevel(strength);
  return level.charAt(0).toUpperCase() + level.slice(1);
}

// Get coupling badge class
export function couplingBadgeClass(strength: number): string {
  const level = couplingLevel(strength);
  switch (level) {
    case 'strong': return 'bg-green-900/30 text-green-400';
    case 'medium': return 'bg-amber-900/30 text-amber-400';
    case 'weak': return 'bg-red-900/30 text-red-400';
  }
}

// Get coupling stroke color (for visualization)
export function couplingStrokeColor(confidence: number): string {
  if (confidence >= COUPLING_THRESHOLDS.strong) return '#22c55e';
  if (confidence >= COUPLING_THRESHOLDS.medium) return '#f59e0b';
  return '#ef4444';
}

// Filter couplings by minimum strength
export function filterByMinimumStrength<T extends { strength: number }>(couplings: T[]): T[] {
  return couplings.filter(c => c.strength > COUPLING_THRESHOLDS.minimum);
}
