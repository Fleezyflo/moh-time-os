import { useState, type ReactNode } from 'react';

export interface DataGridColumn<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => ReactNode;
}

interface DataGridProps<T> {
  columns: DataGridColumn<T>[];
  data: T[];
  onSortChange?: (key: string, direction: 'asc' | 'desc') => void;
  className?: string;
}

type SortDirection = 'asc' | 'desc' | null;

export function DataGrid<T extends { id?: string | number }>({
  columns,
  data,
  onSortChange,
  className = '',
}: DataGridProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);

  const handleSort = (key: string) => {
    let newDir: SortDirection = null;
    if (sortKey === key && sortDir === 'asc') {
      newDir = 'desc';
    } else if (sortKey === key && sortDir === 'desc') {
      newDir = null;
    } else {
      newDir = 'asc';
    }

    setSortKey(newDir ? key : null);
    setSortDir(newDir);
    onSortChange?.(key, newDir || 'asc');
  };

  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full border-collapse font-primary">
        <thead className="border-b border-[var(--grey)] bg-transparent">
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                onClick={() => col.sortable && handleSort(String(col.key))}
                className={`px-[var(--space-md)] py-[var(--space-md)] text-left text-micro font-medium text-[var(--grey-light)] font-mono ${col.sortable ? 'cursor-pointer hover:text-[var(--white)]' : ''}`}
              >
                <div className="flex items-center gap-1">
                  {col.label}
                  {col.sortable && sortKey === String(col.key) && (
                    <span className="text-xs">{sortDir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr
              key={row.id || idx}
              className="border-b border-[var(--grey)] transition-colors hover:bg-[var(--grey-dim)]"
            >
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className="px-[var(--space-md)] py-[var(--space-md)] text-body-small text-[var(--white)]"
                >
                  {col.render ? col.render(row[col.key], row) : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
