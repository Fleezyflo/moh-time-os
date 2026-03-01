// PriorityFilters — Filter bar for the Priorities page
import { useState, useCallback, type ChangeEvent } from 'react';
import type { PriorityFilteredParams } from '../../lib/api';

interface PriorityFiltersProps {
  filters: PriorityFilteredParams;
  onFilterChange: (filters: PriorityFilteredParams) => void;
}

type DueOption = '' | 'today' | 'week' | 'overdue';

export function PriorityFilters({ filters, onFilterChange }: PriorityFiltersProps) {
  const [searchText, setSearchText] = useState(filters.q || '');

  const handleDueChange = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      const val = e.target.value as DueOption;
      onFilterChange({ ...filters, due: val || undefined });
    },
    [filters, onFilterChange]
  );

  const handleAssigneeChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      onFilterChange({ ...filters, assignee: e.target.value || undefined });
    },
    [filters, onFilterChange]
  );

  const handleProjectChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      onFilterChange({ ...filters, project: e.target.value || undefined });
    },
    [filters, onFilterChange]
  );

  const handleSearchSubmit = useCallback(() => {
    onFilterChange({ ...filters, q: searchText || undefined });
  }, [filters, searchText, onFilterChange]);

  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleSearchSubmit();
    },
    [handleSearchSubmit]
  );

  const handleClear = useCallback(() => {
    setSearchText('');
    onFilterChange({});
  }, [onFilterChange]);

  const hasActiveFilters = filters.due || filters.assignee || filters.project || filters.q;

  return (
    <div className="bg-[var(--grey-dim)] rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--white)]">Filters</h3>
        {hasActiveFilters && (
          <button onClick={handleClear} className="text-xs text-[var(--accent)] hover:underline">
            Clear all
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Search */}
        <div>
          <label className="block text-xs text-[var(--grey-light)] mb-1">Search</label>
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            onBlur={handleSearchSubmit}
            placeholder="Search tasks..."
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
        </div>

        {/* Due date filter */}
        <div>
          <label className="block text-xs text-[var(--grey-light)] mb-1">Due</label>
          <select
            value={filters.due || ''}
            onChange={handleDueChange}
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          >
            <option value="">All dates</option>
            <option value="overdue">Overdue</option>
            <option value="today">Due today</option>
            <option value="week">This week</option>
          </select>
        </div>

        {/* Assignee filter */}
        <div>
          <label className="block text-xs text-[var(--grey-light)] mb-1">Assignee</label>
          <input
            type="text"
            value={filters.assignee || ''}
            onChange={handleAssigneeChange}
            placeholder="Filter by assignee..."
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
        </div>

        {/* Project filter */}
        <div>
          <label className="block text-xs text-[var(--grey-light)] mb-1">Project</label>
          <input
            type="text"
            value={filters.project || ''}
            onChange={handleProjectChange}
            placeholder="Filter by project..."
            className="w-full px-3 py-1.5 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] placeholder-[var(--grey-muted)]"
          />
        </div>
      </div>
    </div>
  );
}
