// Format utilities tests
import { describe, it, expect } from 'vitest';
import { formatNumber, formatScore, formatPercent, formatCompact, formatConfidence } from '../lib/format';
import { parseISO, formatDate, daysAgo } from '../lib/datetime';

describe('Number formatting', () => {
  describe('formatNumber', () => {
    it('formats numbers with separators', () => {
      expect(formatNumber(1234)).toMatch(/1.?234/); // Locale-dependent separator
      expect(formatNumber(0)).toBe('0');
    });

    it('handles null/undefined', () => {
      expect(formatNumber(null)).toBe('—');
      expect(formatNumber(undefined)).toBe('—');
    });
  });

  describe('formatScore', () => {
    it('formats scores with 1 decimal', () => {
      expect(formatScore(85)).toBe('85.0');
      expect(formatScore(85.5)).toBe('85.5');
      expect(formatScore(85.56)).toBe('85.6'); // Rounds up
      expect(formatScore(85.54)).toBe('85.5'); // Rounds down
    });
  });

  describe('formatPercent', () => {
    it('formats decimal percentages', () => {
      expect(formatPercent(0.85)).toBe('85%');
      expect(formatPercent(0.855, true, 1)).toBe('85.5%');
    });

    it('formats non-decimal percentages', () => {
      expect(formatPercent(85, false)).toBe('85%');
    });
  });

  describe('formatCompact', () => {
    it('leaves small numbers unchanged', () => {
      expect(formatCompact(500)).toBe('500');
      expect(formatCompact(999)).toBe('999');
    });

    it('compacts thousands', () => {
      expect(formatCompact(1000)).toBe('1.0K');
      expect(formatCompact(1500)).toBe('1.5K');
    });

    it('compacts millions', () => {
      expect(formatCompact(1000000)).toBe('1.0M');
      expect(formatCompact(1500000)).toBe('1.5M');
    });
  });

  describe('formatConfidence', () => {
    it('formats confidence as percentage', () => {
      expect(formatConfidence(0.85)).toBe('85%');
      expect(formatConfidence(1)).toBe('100%');
      expect(formatConfidence(0)).toBe('0%');
    });
  });
});

describe('DateTime utilities', () => {
  describe('parseISO', () => {
    it('parses valid ISO strings', () => {
      const result = parseISO('2025-02-06T12:00:00Z');
      expect(result).toBeInstanceOf(Date);
    });

    it('returns null for invalid strings', () => {
      expect(parseISO('invalid')).toBe(null);
      expect(parseISO('')).toBe(null);
      expect(parseISO(null)).toBe(null);
    });
  });

  describe('formatDate', () => {
    it('formats dates', () => {
      const result = formatDate('2025-02-06T12:00:00Z');
      expect(result).toMatch(/2.*6.*2025/); // Contains day, month, year
    });

    it('handles invalid input', () => {
      expect(formatDate(null)).toBe('—');
      expect(formatDate(undefined)).toBe('—');
    });
  });

  describe('daysAgo', () => {
    it('returns ISO string for N days ago', () => {
      const result = daysAgo(7);
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      const date = new Date(result);
      expect(date.getTime()).toBeLessThan(Date.now());
    });
  });
});
