// Simple confirmation dialog component
import type { ReactNode } from 'react';

interface ConfirmationDialogProps {
  title: string;
  message: ReactNode;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  isDestructive?: boolean;
  isLoading?: boolean;
}

export function ConfirmationDialog({
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  isDestructive = false,
  isLoading = false,
}: ConfirmationDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-[var(--grey-dim)] rounded-lg shadow-lg max-w-sm mx-4 p-6">
        <h2 className="text-lg font-semibold text-[var(--white)] mb-3">{title}</h2>
        <div className="text-[var(--grey-light)] mb-6">{message}</div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 rounded text-sm font-medium bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] disabled:opacity-50 transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className={`px-4 py-2 rounded text-sm font-medium text-white disabled:opacity-50 transition-colors ${
              isDestructive
                ? 'bg-[var(--danger)] hover:bg-[var(--danger)]/90'
                : 'bg-[var(--accent)] hover:bg-[var(--accent)]/90'
            }`}
          >
            {isLoading ? 'Loading...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
