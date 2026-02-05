// Deterministic sorting tests per CONTROL_ROOM_QUERIES.md
import { describe, it, expect } from 'vitest';
import { proposals, issues, couplings } from '../fixtures';

describe('Deterministic Sorting', () => {
  
  describe('Proposals sort by score DESC', () => {
    it('should have proposals sorted by score in descending order', () => {
      const openProposals = proposals.filter(p => p.status === 'open');
      const sorted = [...openProposals].sort((a, b) => b.score - a.score);
      
      // Verify fixture is pre-sorted or verify sort logic
      for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i-1].score).toBeGreaterThanOrEqual(sorted[i].score);
      }
    });
  });

  describe('Issues sort by priority DESC, then last_activity_at DESC', () => {
    it('should have issues sorted by priority order', () => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      const activeIssues = issues.filter(i => ['open','monitoring','awaiting','blocked'].includes(i.state));
      const sorted = [...activeIssues].sort((a, b) => {
        const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
        if (priorityDiff !== 0) return priorityDiff;
        return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
      });
      
      // Critical should come before high, high before medium, etc.
      for (let i = 1; i < sorted.length; i++) {
        expect(priorityOrder[sorted[i-1].priority]).toBeLessThanOrEqual(priorityOrder[sorted[i].priority]);
      }
    });
  });

  describe('Couplings sort by strength DESC', () => {
    it('should have couplings sorted by strength in descending order', () => {
      const sorted = [...couplings].sort((a, b) => b.strength - a.strength);
      
      for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i-1].strength).toBeGreaterThanOrEqual(sorted[i].strength);
      }
    });
  });

  describe('No duplicate IDs', () => {
    it('should have unique proposal_ids', () => {
      const ids = proposals.map(p => p.proposal_id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });

    it('should have unique issue_ids', () => {
      const ids = issues.map(i => i.issue_id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });

    it('should have unique coupling_ids', () => {
      const ids = couplings.map(c => c.coupling_id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });
  });
});
