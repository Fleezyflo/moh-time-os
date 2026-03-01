// Search overlay — Cmd/Ctrl+K global shortcut
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import type { SearchResult } from '../../lib/api';
import { fetchSearch } from '../../lib/api';

const TYPE_ICONS: Record<string, string> = {
  task: 'T',
  project: 'P',
  client: 'C',
  issue: 'I',
  person: 'U',
};

const TYPE_ROUTES: Record<string, (id: string) => string> = {
  task: (id) => `/tasks/${id}`,
  project: (id) => `/projects/${id}`,
  client: (id) => `/clients/${id}`,
  issue: (_id) => '/issues',
  person: (id) => `/team/${id}`,
};

export function SearchOverlay() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Keyboard shortcut: Cmd/Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
    }
  }, [open]);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await fetchSearch(query.trim());
        setResults(resp.results ?? []);
        setSelectedIndex(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = useCallback(
    (result: SearchResult) => {
      const routeFn = TYPE_ROUTES[result.type];
      if (routeFn) {
        navigate({ to: routeFn(result.id) });
      }
      setOpen(false);
    },
    [navigate]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[selectedIndex]) {
        handleSelect(results[selectedIndex]);
      }
    },
    [results, selectedIndex, handleSelect]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Dialog */}
      <div
        className="relative w-full max-w-lg bg-[var(--grey-dim)] border border-[var(--grey)] rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        <div className="flex items-center border-b border-[var(--grey)] px-4">
          <svg
            className="w-5 h-5 text-[var(--grey-light)] mr-3 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search tasks, projects, clients..."
            className="flex-1 bg-transparent py-4 text-sm outline-none placeholder:text-[var(--grey-light)]"
          />
          <kbd className="hidden sm:inline text-xs text-[var(--grey-light)] border border-[var(--grey)] rounded px-1.5 py-0.5 ml-2">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto">
          {loading && (
            <div className="px-4 py-3 text-sm text-[var(--grey-light)]">Searching...</div>
          )}
          {!loading && query.trim() && results.length === 0 && (
            <div className="px-4 py-3 text-sm text-[var(--grey-light)]">No results found</div>
          )}
          {results.map((r, i) => (
            <button
              key={`${r.type}-${r.id}`}
              onClick={() => handleSelect(r)}
              className={`w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-[var(--grey)] transition-colors ${
                i === selectedIndex ? 'bg-[var(--grey)]' : ''
              }`}
            >
              <span className="w-6 h-6 rounded bg-[var(--accent)]/20 text-[var(--accent)] text-xs font-bold flex items-center justify-center flex-shrink-0">
                {TYPE_ICONS[r.type] ?? '?'}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm truncate">{r.title}</div>
                {r.subtitle && (
                  <div className="text-xs text-[var(--grey-light)] truncate">{r.subtitle}</div>
                )}
              </div>
              <span className="text-xs text-[var(--grey-light)] flex-shrink-0 capitalize">
                {r.type}
              </span>
            </button>
          ))}
        </div>

        {/* Footer hint */}
        <div className="border-t border-[var(--grey)] px-4 py-2 text-xs text-[var(--grey-light)] flex gap-4">
          <span>
            <kbd className="border border-[var(--grey)] rounded px-1 py-0.5 mr-1">&uarr;&darr;</kbd>
            Navigate
          </span>
          <span>
            <kbd className="border border-[var(--grey)] rounded px-1 py-0.5 mr-1">&crarr;</kbd>
            Open
          </span>
        </div>
      </div>
    </div>
  );
}
