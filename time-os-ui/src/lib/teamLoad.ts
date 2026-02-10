// Team member load calculation utilities
// Centralized thresholds for consistent load representation

export type LoadLevel = 'high' | 'medium' | 'low';

export interface LoadThresholds {
  high: number;
  medium: number;
}

// Default thresholds: based on typical sprint capacity (10-20 tasks per person)
// High: 20+ tasks = overloaded
// Medium: 10-19 tasks = at capacity
// Low: <10 tasks = has bandwidth
export const LOAD_THRESHOLDS: LoadThresholds = {
  high: 20,
  medium: 10
};

// Calculate load level from open task count
export function loadLevel(openTasks: number): LoadLevel {
  if (openTasks >= LOAD_THRESHOLDS.high) return 'high';
  if (openTasks >= LOAD_THRESHOLDS.medium) return 'medium';
  return 'low';
}

// Get load bar width class
export function loadBarWidth(level: LoadLevel): string {
  switch (level) {
    case 'high': return 'w-4/5';
    case 'medium': return 'w-1/2';
    case 'low': return 'w-1/4';
  }
}

// Get load bar color class
export function loadBarColor(level: LoadLevel): string {
  switch (level) {
    case 'high': return 'bg-red-500';
    case 'medium': return 'bg-amber-500';
    case 'low': return 'bg-green-500';
  }
}

// Get load summary
export function getLoadDisplay(openTasks: number) {
  const level = loadLevel(openTasks);
  return {
    level,
    width: loadBarWidth(level),
    color: loadBarColor(level)
  };
}
