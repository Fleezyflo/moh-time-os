// Priority utilities tests
import { describe, it, expect } from 'vitest';
import {
  priorityLabel,
  priorityBadgeClass,
  comparePriority,
  matchesPriorityFilter,
  PRIORITY_THRESHOLDS
} from '../lib/priority';
import { mockIssues, getIssuesSortedByPriority } from './fixtures/issues';

describe('Priority utilities', () => {
  describe('priorityLabel', () => {
    it('returns critical for priority >= 80', () => {
      expect(priorityLabel(80)).toBe('critical');
      expect(priorityLabel(95)).toBe('critical');
      expect(priorityLabel(100)).toBe('critical');
    });

    it('returns high for priority 60-79', () => {
      expect(priorityLabel(60)).toBe('high');
      expect(priorityLabel(75)).toBe('high');
      expect(priorityLabel(79)).toBe('high');
    });

    it('returns medium for priority 40-59', () => {
      expect(priorityLabel(40)).toBe('medium');
      expect(priorityLabel(50)).toBe('medium');
      expect(priorityLabel(59)).toBe('medium');
    });

    it('returns low for priority < 40', () => {
      expect(priorityLabel(0)).toBe('low');
      expect(priorityLabel(25)).toBe('low');
      expect(priorityLabel(39)).toBe('low');
    });
  });

  describe('priorityBadgeClass', () => {
    it('returns red class for critical priority', () => {
      expect(priorityBadgeClass(90)).toContain('red');
    });

    it('returns orange class for high priority', () => {
      expect(priorityBadgeClass(70)).toContain('orange');
    });

    it('returns yellow class for medium priority', () => {
      expect(priorityBadgeClass(50)).toContain('yellow');
    });

    it('returns slate class for low priority', () => {
      expect(priorityBadgeClass(20)).toContain('slate');
    });
  });

  describe('comparePriority', () => {
    it('sorts higher priority first (descending)', () => {
      expect(comparePriority(90, 50)).toBeLessThan(0); // 90 should come before 50
      expect(comparePriority(50, 90)).toBeGreaterThan(0); // 50 should come after 90
      expect(comparePriority(50, 50)).toBe(0); // Equal priorities
    });
  });

  describe('matchesPriorityFilter', () => {
    it('returns true for "all" filter', () => {
      expect(matchesPriorityFilter(95, 'all')).toBe(true);
      expect(matchesPriorityFilter(25, 'all')).toBe(true);
    });

    it('filters critical priorities correctly', () => {
      expect(matchesPriorityFilter(95, 80)).toBe(true);
      expect(matchesPriorityFilter(80, 80)).toBe(true);
      expect(matchesPriorityFilter(79, 80)).toBe(false);
    });

    it('filters high priorities correctly', () => {
      expect(matchesPriorityFilter(75, 60)).toBe(true);
      expect(matchesPriorityFilter(60, 60)).toBe(true);
      expect(matchesPriorityFilter(80, 60)).toBe(false); // Too high for high filter
      expect(matchesPriorityFilter(59, 60)).toBe(false); // Too low
    });

    it('filters medium priorities correctly', () => {
      expect(matchesPriorityFilter(50, 40)).toBe(true);
      expect(matchesPriorityFilter(40, 40)).toBe(true);
      expect(matchesPriorityFilter(60, 40)).toBe(false); // Too high
      expect(matchesPriorityFilter(39, 40)).toBe(false); // Too low
    });

    it('filters low priorities correctly', () => {
      expect(matchesPriorityFilter(25, 0)).toBe(true);
      expect(matchesPriorityFilter(39, 0)).toBe(true);
      expect(matchesPriorityFilter(40, 0)).toBe(false); // Too high
    });
  });
});

describe('Issue fixtures', () => {
  it('contains issues with all priority levels', () => {
    const priorities = mockIssues.map(i => i.priority ?? 0);
    expect(priorities.some(p => p >= PRIORITY_THRESHOLDS.critical)).toBe(true);
    expect(priorities.some(p => p >= PRIORITY_THRESHOLDS.high && p < PRIORITY_THRESHOLDS.critical)).toBe(true);
    expect(priorities.some(p => p >= PRIORITY_THRESHOLDS.medium && p < PRIORITY_THRESHOLDS.high)).toBe(true);
    expect(priorities.some(p => p < PRIORITY_THRESHOLDS.medium)).toBe(true);
  });

  it('sorts issues by priority descending', () => {
    const sorted = getIssuesSortedByPriority();
    expect(sorted[0].priority ?? 0).toBe(95); // Highest first
    expect(sorted[sorted.length - 1].priority ?? 0).toBe(25); // Lowest last

    // Verify strictly descending order
    for (let i = 1; i < sorted.length; i++) {
      expect((sorted[i - 1].priority ?? 0)).toBeGreaterThanOrEqual(sorted[i].priority ?? 0);
    }
  });
});
