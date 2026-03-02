// Generic CSV export button — client-side serialization of list data
import { useCallback, useState } from 'react';

interface ExportButtonProps {
  /** Array of objects to export */
  data: object[];
  /** Filename without extension */
  filename: string;
  /** Optional column whitelist (default: all keys from first row) */
  columns?: string[];
  /** Optional label override */
  label?: string;
}

function toCsv(data: object[], columns?: string[]): string {
  if (data.length === 0) return '';
  const records = data as Record<string, unknown>[];
  const cols = columns ?? Object.keys(records[0]);
  const header = cols.map((c) => `"${c}"`).join(',');
  const lines = records.map((row) =>
    cols
      .map((c) => {
        const val = row[c];
        if (val == null) return '';
        const str = String(val).replace(/"/g, '""');
        return `"${str}"`;
      })
      .join(',')
  );
  return [header, ...lines].join('\n');
}

export default function ExportButton({
  data,
  filename,
  columns,
  label = 'Export CSV',
}: ExportButtonProps) {
  const [exporting, setExporting] = useState(false);

  const handleExport = useCallback(() => {
    if (data.length === 0) return;
    setExporting(true);
    try {
      const csv = toCsv(data, columns);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${filename}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }, [data, filename, columns]);

  return (
    <button
      onClick={handleExport}
      disabled={exporting || data.length === 0}
      className="btn btn--secondary text-xs px-3 py-1.5 disabled:opacity-40"
      aria-label={`Export ${filename} as CSV`}
    >
      {exporting ? 'Exporting...' : label}
    </button>
  );
}
