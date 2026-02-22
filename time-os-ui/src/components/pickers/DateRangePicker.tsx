// Simple date range picker with from/to inputs
import { useState } from 'react';

interface DateRangePickerProps {
  onRangeChange: (from: string, to: string) => void;
  defaultFrom?: string;
  defaultTo?: string;
  disabled?: boolean;
}

export function DateRangePicker({
  onRangeChange,
  defaultFrom,
  defaultTo,
  disabled = false,
}: DateRangePickerProps) {
  const [fromDate, setFromDate] = useState(defaultFrom || '');
  const [toDate, setToDate] = useState(defaultTo || '');

  const handleFromChange = (value: string) => {
    setFromDate(value);
    onRangeChange(value, toDate);
  };

  const handleToChange = (value: string) => {
    setToDate(value);
    onRangeChange(fromDate, value);
  };

  return (
    <div className="flex gap-3 items-end">
      <div className="flex-1">
        <label htmlFor="from-date" className="block text-sm font-medium text-[var(--white)] mb-2">
          From
        </label>
        <input
          id="from-date"
          type="date"
          value={fromDate}
          onChange={(e) => handleFromChange(e.target.value)}
          disabled={disabled}
          className="w-full px-4 py-2 rounded-lg bg-[var(--grey-dim)] text-[var(--white)] border border-[var(--grey)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 outline-none transition-colors disabled:opacity-50"
        />
      </div>

      <div className="flex-1">
        <label htmlFor="to-date" className="block text-sm font-medium text-[var(--white)] mb-2">
          To
        </label>
        <input
          id="to-date"
          type="date"
          value={toDate}
          onChange={(e) => handleToChange(e.target.value)}
          disabled={disabled}
          className="w-full px-4 py-2 rounded-lg bg-[var(--grey-dim)] text-[var(--white)] border border-[var(--grey)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 outline-none transition-colors disabled:opacity-50"
        />
      </div>
    </div>
  );
}
