import { useEffect } from 'react';

interface KeyboardShortcutOptions {
  onEscape?: () => void;
  onHelp?: () => void;
}

/**
 * Hook for global keyboard shortcuts
 * - Escape: closes modals/drawers
 * - ?: shows help
 */
export function useKeyboardShortcuts(options: KeyboardShortcutOptions = {}) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Escape key
      if (event.key === 'Escape') {
        options.onEscape?.();
      }

      // Help key (?)
      if (event.key === '?' && !event.shiftKey) {
        event.preventDefault();
        options.onHelp?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [options]);
}
