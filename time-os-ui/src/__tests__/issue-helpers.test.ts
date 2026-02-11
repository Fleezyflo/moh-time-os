/**
 * Tests for issue helper functions - guards against undefined field access
 */

import { describe, it, expect } from 'vitest';

// Inline the helper since it's defined in a component file
const getIssueTitle = (issue: { title?: string; headline?: string }): string =>
  issue.title || issue.headline || '';

describe('Issue field helpers', () => {
  describe('getIssueTitle', () => {
    it('returns title when present', () => {
      expect(getIssueTitle({ title: 'Test Title' })).toBe('Test Title');
    });

    it('falls back to headline when title is missing', () => {
      expect(getIssueTitle({ headline: 'Test Headline' })).toBe('Test Headline');
    });

    it('returns empty string when both are missing', () => {
      expect(getIssueTitle({})).toBe('');
    });

    it('prefers title over headline', () => {
      expect(getIssueTitle({ title: 'Title', headline: 'Headline' })).toBe('Title');
    });

    it('handles undefined values safely', () => {
      expect(getIssueTitle({ title: undefined, headline: undefined })).toBe('');
    });
  });

  describe('safe replace pattern', () => {
    it('handles undefined input for replace operations', () => {
      const rawHeadline: string | undefined = undefined;
      const safeHeadline = rawHeadline || '';
      expect(() => safeHeadline.replace(/test/, '')).not.toThrow();
    });

    it('strips emoji prefixes safely', () => {
      const testCases = [
        { input: '⚠️ Test Issue', expected: 'Test Issue' },
        { input: 'No emoji', expected: 'No emoji' },
        { input: '', expected: '' },
        { input: undefined, expected: '' },
      ];

      // Strip leading emoji and whitespace
      const stripEmojiPrefix = (str: string): string => {
        // Match emoji (including variation selectors and zero-width joiners) at start
        // Emoji can be: base emoji + optional variation selector (FE0E/FE0F) + optional ZWJ sequences
        return str.replace(/^(?:\p{Emoji_Presentation}|\p{Emoji}\uFE0F?)+\s*/u, '').trim();
      };

      for (const { input, expected } of testCases) {
        const raw = input || '';
        const clean = stripEmojiPrefix(raw);
        expect(clean).toBe(expected);
      }
    });
  });
});
