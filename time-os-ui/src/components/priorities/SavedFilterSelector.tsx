// SavedFilterSelector — Dropdown to select and apply saved filters
import { useCallback, type ChangeEvent } from 'react';
import type { SavedFilter, PriorityFilteredParams } from '../../lib/api';

interface SavedFilterSelectorProps {
  savedFilters: SavedFilter[];
  onApply: (filters: PriorityFilteredParams) => void;
  loading?: boolean;
}

export function SavedFilterSelector({ savedFilters, onApply, loading }: SavedFilterSelectorProps) {
  const handleChange = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      const filterName = e.target.value;
      if (!filterName) return;

      const found = savedFilters.find((f) => f.name === filterName);
      if (!found) return;

      // Map saved filter fields to PriorityFilteredParams
      const mapped: PriorityFilteredParams = {};
      const raw = found.filters;
      if (typeof raw.due === 'string') mapped.due = raw.due as PriorityFilteredParams['due'];
      if (typeof raw.assignee === 'string') mapped.assignee = raw.assignee;
      if (typeof raw.project === 'string') mapped.project = raw.project;
      if (typeof raw.source === 'string') mapped.source = raw.source;
      if (typeof raw.q === 'string') mapped.q = raw.q;

      onApply(mapped);
      // Reset the select so user can re-select the same filter
      e.target.value = '';
    },
    [savedFilters, onApply]
  );

  if (savedFilters.length === 0) return null;

  return (
    <select
      onChange={handleChange}
      disabled={loading}
      className="px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] disabled:opacity-50"
      defaultValue=""
      aria-label="Apply saved filter"
    >
      <option value="" disabled>
        Saved filters
      </option>
      {savedFilters.map((f) => (
        <option key={f.name} value={f.name}>
          {f.name}
        </option>
      ))}
    </select>
  );
}
