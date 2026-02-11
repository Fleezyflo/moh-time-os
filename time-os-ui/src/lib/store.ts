// Global state management with Zustand
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Proposal, Issue } from '../types/api';

// Drawer state
interface DrawerState {
  // Proposal drawer
  selectedProposal: Proposal | null;
  proposalDrawerOpen: boolean;
  openProposalDrawer: (proposal: Proposal) => void;
  closeProposalDrawer: () => void;

  // Issue drawer
  selectedIssue: Issue | null;
  issueDrawerOpen: boolean;
  openIssueDrawer: (issue: Issue) => void;
  closeIssueDrawer: () => void;

  // Close all
  closeAllDrawers: () => void;
}

export const useDrawerStore = create<DrawerState>()(
  devtools(
    (set) => ({
      // Proposal drawer
      selectedProposal: null,
      proposalDrawerOpen: false,
      openProposalDrawer: (proposal) =>
        set({
          selectedProposal: proposal,
          proposalDrawerOpen: true,
          // Close other drawers
          selectedIssue: null,
          issueDrawerOpen: false,
        }),
      closeProposalDrawer: () => set({ selectedProposal: null, proposalDrawerOpen: false }),

      // Issue drawer
      selectedIssue: null,
      issueDrawerOpen: false,
      openIssueDrawer: (issue) =>
        set({
          selectedIssue: issue,
          issueDrawerOpen: true,
          // Close other drawers
          selectedProposal: null,
          proposalDrawerOpen: false,
        }),
      closeIssueDrawer: () => set({ selectedIssue: null, issueDrawerOpen: false }),

      // Close all
      closeAllDrawers: () =>
        set({
          selectedProposal: null,
          proposalDrawerOpen: false,
          selectedIssue: null,
          issueDrawerOpen: false,
        }),
    }),
    { name: 'drawer-store' }
  )
);

// UI preferences (persisted)
interface UIPreferences {
  // Filters
  defaultScope: 'all' | 'clients' | 'team';
  defaultDays: number;

  // Display
  compactMode: boolean;

  // Actions
  setDefaultScope: (scope: 'all' | 'clients' | 'team') => void;
  setDefaultDays: (days: number) => void;
  toggleCompactMode: () => void;
}

export const useUIPreferences = create<UIPreferences>()(
  devtools(
    persist(
      (set) => ({
        defaultScope: 'all',
        defaultDays: 7,
        compactMode: false,

        setDefaultScope: (scope) => set({ defaultScope: scope }),
        setDefaultDays: (days) => set({ defaultDays: days }),
        toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
      }),
      { name: 'time-os-preferences' }
    ),
    { name: 'ui-preferences' }
  )
);

// Mutation state (loading, optimistic updates)
interface MutationState {
  // Track pending mutations by ID
  pendingMutations: Set<string>;

  // Optimistic data
  optimisticProposals: Map<string, Partial<Proposal>>;
  optimisticIssues: Map<string, Partial<Issue>>;

  // Actions
  startMutation: (id: string) => void;
  endMutation: (id: string) => void;
  isPending: (id: string) => boolean;

  // Optimistic updates
  setOptimisticProposal: (id: string, data: Partial<Proposal>) => void;
  clearOptimisticProposal: (id: string) => void;
  setOptimisticIssue: (id: string, data: Partial<Issue>) => void;
  clearOptimisticIssue: (id: string) => void;
}

export const useMutationStore = create<MutationState>()(
  devtools(
    (set, get) => ({
      pendingMutations: new Set(),
      optimisticProposals: new Map(),
      optimisticIssues: new Map(),

      startMutation: (id) =>
        set((state) => {
          const next = new Set(state.pendingMutations);
          next.add(id);
          return { pendingMutations: next };
        }),

      endMutation: (id) =>
        set((state) => {
          const next = new Set(state.pendingMutations);
          next.delete(id);
          return { pendingMutations: next };
        }),

      isPending: (id) => get().pendingMutations.has(id),

      setOptimisticProposal: (id, data) =>
        set((state) => {
          const next = new Map(state.optimisticProposals);
          next.set(id, data);
          return { optimisticProposals: next };
        }),

      clearOptimisticProposal: (id) =>
        set((state) => {
          const next = new Map(state.optimisticProposals);
          next.delete(id);
          return { optimisticProposals: next };
        }),

      setOptimisticIssue: (id, data) =>
        set((state) => {
          const next = new Map(state.optimisticIssues);
          next.set(id, data);
          return { optimisticIssues: next };
        }),

      clearOptimisticIssue: (id) =>
        set((state) => {
          const next = new Map(state.optimisticIssues);
          next.delete(id);
          return { optimisticIssues: next };
        }),
    }),
    { name: 'mutation-store' }
  )
);

// Actor configuration
interface ActorState {
  actor: string;
  setActor: (actor: string) => void;
}

export const useActorStore = create<ActorState>()(
  devtools(
    persist(
      (set) => ({
        actor: import.meta.env.VITE_ACTOR || 'moh',
        setActor: (actor) => set({ actor }),
      }),
      { name: 'time-os-actor' }
    ),
    { name: 'actor-store' }
  )
);
